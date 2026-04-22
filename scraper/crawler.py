import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

import aiohttp

import config
from database import DatabaseManager
from queue_manager import QueueManager

logger = logging.getLogger(__name__)

# Type alias for the broadcast callback injected from api.py
BroadcastFn = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


async def _noop_broadcast(_: dict):
    """Default no-op when no broadcast function is provided."""


class CrawlerWorker:
    def __init__(
        self,
        worker_id: int,
        queue_manager: QueueManager,
        session: aiohttp.ClientSession,
        db_manager: DatabaseManager,
        broadcast_fn: BroadcastFn = _noop_broadcast,
    ):
        self.worker_id = worker_id
        self.session = session
        self.db_manager = db_manager
        self.queue_manager = queue_manager
        self.broadcast = broadcast_fn
        self.running = False
        self.stats = {
            "routes_processed": 0,
            "pages_crawled": 0,
            "items_found": 0,
            "items_saved": 0,
            "errors": 0,
        }

    async def _fetch_page_data(
        self, category: int, region: int, page: int
    ) -> Optional[Dict[str, Any]]:
        url = config.CHOTOT_API_BASE
        offset = page * config.CRAWL_LIMIT
        params = {
            "limit": config.CRAWL_LIMIT,
            "st": "s,k",
            "f": "p",
            "sp": "0",
            "cg": category,
            "region": region,
            "page": page,
            "o": offset,
            "key_param_included": "true",
        }

        for attempt in range(config.MAX_RETRIES):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 429:
                        wait = config.BACKOFF_FACTOR**attempt * 10
                        logger.warning(f"Worker {self.worker_id}: Rate limited, waiting {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        logger.warning(
                            f"Worker {self.worker_id}: HTTP {response.status} "
                            f"for cg={category} region={region} page={page}"
                        )
            except Exception as e:
                logger.error(
                    f"Worker {self.worker_id}: Attempt {attempt + 1} failed "
                    f"for cg={category} region={region} page={page}: {e}"
                )
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(config.BACKOFF_FACTOR**attempt)
        return None

    async def _process_page_items(
        self, items: List[Dict[str, Any]]
    ) -> tuple[Set[int], List[Dict[str, Any]], List[int]]:
        if not items:
            return set(), [], []
        
        # BƯỚC 1: Lấy TOÀN BỘ ID của trang để check DB
        all_list_ids = [i.get("list_id") for i in items if i.get("list_id")]
        existing = await self.db_manager.batch_check_existing_items(all_list_ids)
        
        new_unfiltered_ids = []
        final_new_items = []
        
        for i in items:
            list_id = i.get("list_id")
            if list_id and list_id not in existing:
                new_unfiltered_ids.append(list_id)
                # BƯỚC 3: BỘ LỌC ĐẦU VÀO - Chỉ giữ lại những bài MỚI có giá <= 2 triệu VNĐ
                if i.get("price", 0) <= config.MAX_PRICE:
                    final_new_items.append(i)
                    
        return existing, final_new_items, new_unfiltered_ids

    async def _crawl_route_pages(self, route_data: Dict[str, Any]) -> bool:
        category = route_data["category"]
        region = route_data["region"]
        start_page = route_data["page"]
        max_pages = 3

        for page in range(start_page, start_page + max_pages):
            if not self.running:
                break
            try:
                page_data = await self._fetch_page_data(category, region, page)
                if not page_data:
                    self.stats["errors"] += 1
                    break

                ads = page_data.get("ads", [])
                self.stats["pages_crawled"] += 1
                self.stats["items_found"] += len(ads)

                if not ads:
                    break

                existing, new_items, new_unfiltered_ids = await self._process_page_items(ads)

                if new_unfiltered_ids:
                    await self.db_manager.save_crawled_item_ids(new_unfiltered_ids)

                # Chỉ lưu vào DB chính những bài thỏa điều kiện giá
                if new_items:
                    saved = await self.db_manager.save_items(new_items)
                    self.stats["items_saved"] += saved

                # Ngắt trang thông minh: 
                # Ngắt trang khi phần lớn các bài trên trang đều là bài cũ (để tránh lặp do tin đẩy)
                # Nếu số lượng bài cũ chiếm quá nửa, hoặc không còn bài thật sự mới nào, thì ngắt.
                if page > start_page and existing and (len(new_unfiltered_ids) == 0 or len(existing) > len(ads) * 0.5):
                    break  # ← đây là điểm ngắt trang mới!

                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Error on page {page}: {e}")
                self.stats["errors"] += 1
                if route_data.get("retry_count", 0) < config.MAX_RETRIES:
                    route_data["page"] = page
                    await self.queue_manager.requeue_route(route_data, increment_retry=True)
                break
        return True

    async def _process_route(self, route_data: Dict[str, Any]) -> bool:
        try:
            cat_name = route_data["category_name"]
            reg_name = route_data["region_name"]
            logger.info(
                f"Worker {self.worker_id}: Processing {cat_name} in {reg_name} "
                f"(page={route_data['page']}, priority={route_data['priority']})"
            )
            t0 = time.time()
            success = await self._crawl_route_pages(route_data)
            elapsed = time.time() - t0
            self.stats["routes_processed"] += 1

            logger.info(
                f"Worker {self.worker_id}: Completed route {cat_name} in {reg_name} "
                f"in {elapsed:.2f}s"
            )

            await self.broadcast({
                "type": "ROUTE_COMPLETED",
                "workerId": self.worker_id,
                "route": f"{cat_name} in {reg_name}",
                "time": round(elapsed, 2),
            })
            await self._broadcast_progress()

            if success:
                await self.queue_manager.schedule_next_crawl(route_data)
            return success
        except Exception as e:
            logger.error(f"Worker {self.worker_id}: Error processing route: {e}")
            self.stats["errors"] += 1
            return False

    async def _broadcast_progress(self):
        """Push per-worker stats to all WS clients."""
        await self.broadcast({
            "type": "CRAWL_PROGRESS",
            "workerId": self.worker_id,
            "processed": self.stats["routes_processed"],
            "saved": self.stats["items_saved"],
        })

    async def run(self):
        self.running = True
        logger.info(f"Worker {self.worker_id}: Started")
        while self.running:
            try:
                route_data = await self.queue_manager.get_route_from_queue(timeout=10.0)
                if route_data is None:
                    await asyncio.sleep(2)
                    continue
                await self._process_route(route_data)
                
                # --- THÊM ĐOẠN NÀY ĐỂ BẢO VỆ IP CỦA BẠN ---
                # Nghỉ ngơi 3 giây trước khi nhận nhiệm vụ mới
                # Nó giúp "tản nhiệt" cho IP, tránh bị hệ thống Anti-bot của Chợ Tốt quét
                logger.debug(f"Worker {self.worker_id} cooldown...")
                await asyncio.sleep(3) 
                # ------------------------------------------
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Unexpected error: {e}")
                self.stats["errors"] += 1
                await asyncio.sleep(5)
        logger.info(f"Worker {self.worker_id}: Stopped. Stats: {self.stats}")

    def stop(self):
        self.running = False


class CrawlerManager:
    def __init__(
        self,
        num_workers: int = config.MAX_WORKERS,
        broadcast_fn: BroadcastFn = _noop_broadcast,
        queue_manager: Optional[QueueManager] = None,
    ):
        self.num_workers = num_workers
        self.broadcast = broadcast_fn
        self.workers: list[CrawlerWorker] = []
        self.worker_tasks: list[asyncio.Task] = []
        self._queue_manager = queue_manager or QueueManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self.db_manager: Optional[DatabaseManager] = None

    async def start_workers(self):
        logger.info(f"Starting {self.num_workers} crawler workers...")
        
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
            headers=config.DEFAULT_HEADERS,
        )
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()

        for wid in range(self.num_workers):
            worker = CrawlerWorker(
                worker_id=wid,
                queue_manager=self._queue_manager,
                session=self.session,
                db_manager=self.db_manager,
                broadcast_fn=self.broadcast,
            )

            async def _run(w=worker):
                await w.run()

            task = asyncio.create_task(_run())
            self.workers.append(worker)
            self.worker_tasks.append(task)
        logger.info(f"All {self.num_workers} workers started")

    async def stop_workers(self):
        logger.info("Stopping all workers...")
        for w in self.workers:
            w.stop()
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.250)
        if self.db_manager:
            await self.db_manager.disconnect()
            
        logger.info("All workers stopped")

    def get_combined_stats(self) -> Dict[str, int]:
        combined = {
            "routes_processed": 0,
            "pages_crawled": 0,
            "items_found": 0,
            "items_saved": 0,
            "errors": 0,
        }
        for w in self.workers:
            for k in combined:
                combined[k] += w.stats[k]
        return combined
