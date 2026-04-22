import asyncio
import logging
import itertools
from typing import Dict, List, Any, Optional

import config

logger = logging.getLogger(__name__)


class QueueManager:
    """
    In-process priority queue backed by asyncio.PriorityQueue.
    Replaces the old RabbitMQ (aio_pika) implementation so no external broker
    is needed.
    """

    def __init__(self):
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._delayed_tasks: set[asyncio.Task] = set()
        self.pending_count: int = 0
        self._counter = itertools.count()

    # ------------------------------------------------------------------
    # Connection stubs (kept for API compatibility with CrawlerWorker)
    # ------------------------------------------------------------------
    async def connect(self):
        logger.debug("QueueManager ready (in-process asyncio queue)")

    async def disconnect(self):
        for task in self._delayed_tasks.copy():
            if not task.done():
                task.cancel()
        self._delayed_tasks.clear()
        logger.debug("QueueManager disconnected")

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------
    async def add_route_to_queue(self, route_info: Dict[str, Any]) -> bool:
        try:
            item = {
                "category": route_info["category"],
                "region": route_info["region"],
                "category_name": route_info["category_name"],
                "region_name": route_info["region_name"],
                "avg_interval": route_info["avg_interval"],
                "priority": route_info["priority"],
                "page": route_info.get("page", 0),
                "retry_count": route_info.get("retry_count", 0),
            }
            # PriorityQueue is a min-heap; negate priority so highest runs first
            count = next(self._counter)
            await self.queue.put((-item["priority"], count, item))
            self.pending_count += 1
            logger.debug(
                f"Queued route: {item['category_name']} in {item['region_name']} "
                f"(priority={item['priority']}, page={item['page']})"
            )
            return True
        except Exception as e:
            logger.error(f"Error adding route to queue: {e}")
            return False

    async def add_all_routes_to_queue(self, route_priorities: List[Dict[str, Any]]) -> int:
        success = 0
        for route in route_priorities:
            if await self.add_route_to_queue(route):
                success += 1
        logger.info(f"Successfully queued {success}/{len(route_priorities)} routes")
        return success

    # ------------------------------------------------------------------
    # Dequeue
    # ------------------------------------------------------------------
    async def get_route_from_queue(self, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        try:
            _priority, _count, route_data = await asyncio.wait_for(
                self.queue.get(), timeout=timeout
            )
            self.pending_count -= 1
            required = ["category", "region", "category_name", "region_name", "avg_interval", "priority"]
            for field in required:
                if field not in route_data:
                    logger.error(f"Missing required field '{field}' in queue item")
                    return None
            route_data.setdefault("page", 0)
            route_data.setdefault("retry_count", 0)
            return route_data
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.debug(f"Queue get error: {e}")
            return None

    # ------------------------------------------------------------------
    # Requeue / schedule
    # ------------------------------------------------------------------
    async def requeue_route(
        self,
        route_data: Dict[str, Any],
        increment_page: bool = False,
        increment_retry: bool = False,
    ) -> bool:
        try:
            if increment_page:
                route_data["page"] += 1
            if increment_retry:
                route_data["retry_count"] += 1
                route_data["priority"] = max(0, route_data["priority"] - 10)
            count = next(self._counter)
            await self.queue.put((-route_data["priority"], count, route_data))
            self.pending_count += 1
            return True
        except Exception as e:
            logger.error(f"Error requeuing route: {e}")
            return False

    async def schedule_next_crawl(self, route_data: Dict[str, Any]) -> bool:
        try:
            copy = route_data.copy()
            copy["page"] = 0
            copy["retry_count"] = 0
            delay = route_data.get("avg_interval", config.MIN_INTERVAL)

            async def _delayed():
                try:
                    await asyncio.sleep(delay)
                    await self.add_route_to_queue(copy)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error in delayed requeue: {e}")
                finally:
                    self._delayed_tasks.discard(asyncio.current_task())

            task = asyncio.create_task(_delayed())
            self._delayed_tasks.add(task)
            logger.info(
                f"Scheduled next crawl for {route_data['category_name']} in "
                f"{route_data['region_name']} after {delay:.1f}s"
            )
            return True
        except Exception as e:
            logger.error(f"Error scheduling next crawl: {e}")
            return False

    # ------------------------------------------------------------------
    # Stats / purge
    # ------------------------------------------------------------------
    async def get_queue_stats(self) -> Dict[str, int]:
        return {"message_count": self.queue.qsize(), "pending": self.pending_count}

    async def purge_queue(self) -> bool:
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.pending_count = 0
        logger.info("Queue purged")
        return True
