#!/usr/bin/env python3
"""
FastAPI server for the Chotot Crawler microservice.
Replaces the old Node.js child_process + regex stdout parsing approach.
"""

import asyncio
import logging
from logging.handlers import RotatingFileHandler
import sys
import os
from typing import List, Set, Optional, Dict, Any
import math
import aiohttp
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from priority_calculator import PriorityCalculator
from queue_manager import QueueManager
from crawler import CrawlerManager
import config
from motor.motor_asyncio import AsyncIOMotorClient
from ai_worker import run_ai_worker, AI_ITEM_TIMEOUT_MINUTES
import time

log_handlers = [
    RotatingFileHandler("crawler.log", maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
    logging.StreamHandler(sys.stdout),
]
for h in log_handlers:
    h.setFormatter(logging.Formatter(config.LOG_FORMAT))

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    handlers=log_handlers,
    force=True,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared application state (single-process; no external broker needed)
# ---------------------------------------------------------------------------
class CrawlState:
    def __init__(self):
        self.is_crawling: bool = False
        self.queue_manager: QueueManager | None = None
        self.crawler_manager: CrawlerManager | None = None
        self.crawl_task: asyncio.Task | None = None
        self.shutdown_event: asyncio.Event = asyncio.Event()
        self.ws_clients: Set[WebSocket] = set()

    def reset(self):
        self.is_crawling = False
        self.queue_manager = None
        self.crawler_manager = None
        self.crawl_task = None
        self.shutdown_event = asyncio.Event()


state = CrawlState()


# ---------------------------------------------------------------------------
# WebSocket broadcast helper
# ---------------------------------------------------------------------------
async def broadcast(data: dict):
    """Send a JSON message to every connected WebSocket client."""
    dead: list[WebSocket] = []
    for ws in state.ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state.ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# Core crawl orchestration (runs as a background asyncio task)
# ---------------------------------------------------------------------------
async def run_crawl(routes: List[dict], num_workers: int):
    """
    Full crawl lifecycle:
    1. Calculate priorities
    2. Populate the in-process asyncio queue
    3. Start N workers
    4. Wait until queue is drained or stop is requested
    5. Broadcast final stats
    """
    try:
        state.is_crawling = True
        await broadcast({"type": "CRAWL_STARTING"})

        route_tuples = [(r["category"], r["region"]) for r in routes]
        await broadcast({"type": "TOTAL_ROUTES", "count": len(route_tuples)})

        # --- Priority calculation ---
        async with PriorityCalculator() as calc:
            route_priorities = await calc.calculate_all_routes_priority(route_tuples)

        # --- Queue setup ---
        state.queue_manager = QueueManager()
        queued = await state.queue_manager.add_all_routes_to_queue(route_priorities)
        logger.info(f"Queued {queued} routes")
        await broadcast({"type": "ROUTES_QUEUED"})

        # --- Start workers (share the same queue_manager instance) ---
        config.MAX_WORKERS = num_workers
        state.crawler_manager = CrawlerManager(
            num_workers=num_workers,
            broadcast_fn=broadcast,
            queue_manager=state.queue_manager,
        )
        await state.crawler_manager.start_workers()
        await broadcast({"type": "WORKERS_STARTED", "workerCount": num_workers})

        # --- Wait until all initial routes are processed or stop requested ---
        while not state.shutdown_event.is_set():
            await asyncio.sleep(5)  # Check every 5 seconds if stop is requested

        # --- Shutdown workers ---
        await state.crawler_manager.stop_workers()

        combined = state.crawler_manager.get_combined_stats()
        worker_stats = {
            str(w.worker_id): {"processed": w.stats["routes_processed"], "saved": w.stats["items_saved"]}
            for w in state.crawler_manager.workers
        }

        status = "Stopped" if state.shutdown_event.is_set() else "Completed"
        await broadcast({
            "type": "CRAWL_FINISHED",
            "status": status,
            "totalSaved": combined["items_saved"],
            "totalProcessed": combined["routes_processed"],
            "workerStats": worker_stats,
        })

    except Exception as e:
        logger.error(f"Crawl failed: {e}", exc_info=True)
        await broadcast({"type": "CRAWL_ERROR", "error": str(e)})
    finally:
        state.reset()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("FastAPI crawler service starting")
    
    # Init MongoDB
    mongo_client = AsyncIOMotorClient(config.MONGODB_URI)
    db = mongo_client[config.DB_NAME]
    collection = db[config.COLLECTION_NAME]
    
    # Store in app.state for routes
    _app.state.mongo_client = mongo_client
    _app.state.db = db
    _app.state.collection = collection
    
    # Start AI Worker background task
    ai_task = asyncio.create_task(run_ai_worker(collection, broadcast_func=broadcast))
    
    yield
    
    # Shutdown
    ai_task.cancel()
    mongo_client.close()
    
    if state.crawler_manager:
        await state.crawler_manager.stop_workers()
    logger.info("FastAPI crawler service stopped")


app = FastAPI(title="Chotot Crawler API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request models ---
class CrawlRequest(BaseModel):
    categories: List[int]
    provinces: List[int]
    workers: int = 5


# --- REST endpoints ---
@app.post("/api/crawl")
async def start_crawl(req: CrawlRequest):
    if state.is_crawling:
        raise HTTPException(status_code=400, detail="Crawler is already running")

    routes = [
        {"category": cat, "region": prov}
        for cat in req.categories
        for prov in req.provinces
    ]
    if not routes:
        raise HTTPException(status_code=400, detail="No valid routes found")

    state.crawl_task = asyncio.create_task(run_crawl(routes, req.workers))
    return {"success": True, "message": "Crawler process initiated"}


@app.post("/api/crawl/stop")
async def stop_crawl():
    if not state.is_crawling:
        raise HTTPException(status_code=400, detail="No crawler is running")
    state.shutdown_event.set()
    return {"success": True, "message": "Crawler stop request received"}


@app.get("/api/items")
async def get_items(
    request: Request,
    category: Optional[int] = None,
    province: Optional[int] = None,
    minPrice: Optional[int] = None,
    maxPrice: Optional[int] = None,
    evaluatedType: Optional[int] = None,
    marketplace: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    sortBy: str = 'newest',
    itemIds: Optional[str] = None
):
    collection = request.app.state.collection
    
    filter_query = {}
    if category is not None: filter_query["category"] = category
    if province is not None: filter_query["region"] = province
    
    if minPrice is not None or maxPrice is not None:
        filter_query["price"] = {}
        if minPrice is not None: filter_query["price"]["$gte"] = minPrice
        if maxPrice is not None: filter_query["price"]["$lte"] = maxPrice
        
    if evaluatedType is not None:
        if evaluatedType == 0:
            filter_query["evaluated"] = {"$exists": False}
        elif evaluatedType in [1, 2]:
            filter_query["evaluated.type"] = evaluatedType
    else:
        # Mặc định (khi chưa lọc type) chỉ hiển thị type 1 hoặc type chưa evaluate
        # Điều này giúp ẩn đi các item type 2 ở Frontend (soft delete)
        filter_query["$or"] = [
            {"evaluated": {"$exists": False}},
            {"evaluated.type": 1}
        ]
            
    if marketplace == 'marketplace':
        filter_query["marketplace_status.posted"] = True
        
    if itemIds:
        try:
            id_list = [int(id_str.strip()) for id_str in itemIds.split(',') if id_str.strip().isdigit()]
            if id_list:
                filter_query["_id"] = {"$in": id_list}
        except ValueError:
            pass
            
    skip = (page - 1) * limit
    
    sort_options = [("list_time", -1)]
    if sortBy == 'price-high': sort_options = [("price", -1)]
    elif sortBy == 'price-low': sort_options = [("price", 1)]
    elif sortBy == 'roi-high': 
        sort_options = [("evaluated.type", 1), ("evaluated.roi", -1)]
        
    total = await collection.count_documents(filter_query)
    
    cursor = collection.find(filter_query).sort(sort_options).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    
    total_pages = math.ceil(total / limit) if limit > 0 else 0
    
    return {
        "items": items,
        "pagination": {
            "total": total,
            "totalPages": total_pages,
            "currentPage": page,
            "limit": limit
        }
    }

@app.get("/api/ai-pending-count")
async def get_ai_pending_count(request: Request):
    collection = request.app.state.collection
    now_ms = int(time.time() * 1000)
    timeout_ms = AI_ITEM_TIMEOUT_MINUTES * 60 * 1000
    cutoff_time = now_ms - timeout_ms
    
    count = await collection.count_documents({
        "$or": [{"ai_evaluated": False}, {"ai_evaluated": {"$exists": False}}],
        "list_time": {"$gte": cutoff_time}
    })
    return {"count": count}

@app.get("/api/filters")
async def get_filters(request: Request):
    collection = request.app.state.collection
    categories = await collection.distinct("category")
    regions = await collection.distinct("region")
    return {"categories": categories, "provinces": regions}

async def validate_user_categories(account_oid: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://gateway.chotot.com/v1/public/theia/{account_oid}?limit=10") as resp:
                data = await resp.json()
                ads = data.get("ads", [])
                
                category_count = {}
                for ad in ads:
                    cat = ad.get("info", {}).get("category")
                    if cat:
                        category_count[cat] = category_count.get(cat, 0) + 1
                        
                for count in category_count.values():
                    if count >= 2:
                        return False
                return True
    except Exception as e:
        logger.error(f"Error validating user categories: {e}")
        return False

class BulkEvaluatePayload(BaseModel):
    evaluations: List[dict]

@app.put("/api/items/bulk-evaluate")
async def bulk_evaluate(payload: BulkEvaluatePayload, request: Request):
    collection = request.app.state.collection
    results = []
    
    for ev in payload.evaluations:
        try:
            item_id = int(ev.get("_id"))
            type_num = int(ev.get("type"))
            
            if type_num not in [0, 1, 2, 3]:
                raise ValueError("Invalid evaluation type")
                
            item = await collection.find_one({"_id": item_id})
            if not item:
                raise ValueError("Item not found")
                
            if type_num == 1:
                account_oid = item.get("account_oid")
                if account_oid:
                    is_valid = await validate_user_categories(account_oid)
                    if not is_valid:
                        await collection.delete_one({"_id": item_id})
                        results.append({"_id": item_id, "success": False, "error": "Item deleted: User has too many items in same category"})
                        continue
                        
            evaluation_data = {
                "type": type_num,
                "note": ev.get("note", "")
            }
            
            if type_num == 1:
                if "buy_price" in ev: evaluation_data["buy_price"] = int(ev["buy_price"])
                if "sell_price" in ev: evaluation_data["sell_price"] = int(ev["sell_price"])
                if "new_title" in ev: evaluation_data["new_title"] = ev["new_title"]
                
                bp = evaluation_data.get("buy_price")
                sp = evaluation_data.get("sell_price")
                if bp and sp and bp > 0:
                    evaluation_data["roi"] = ((sp - bp) / bp) * 100
                    
            res = await collection.update_one({"_id": item_id}, {"$set": {"evaluated": evaluation_data}})
            results.append({"_id": item_id, "success": res.matched_count > 0, "error": None if res.matched_count > 0 else "Item not found"})
        except Exception as e:
            results.append({"_id": ev.get("_id"), "success": False, "error": str(e)})
            
    return {"success": True, "results": results, "message": f"Processed {len(results)} evaluations"}

class EvaluatePayload(BaseModel):
    type: int
    note: str = ""

@app.put("/api/items/{item_id}/evaluate")
async def evaluate_item(item_id: int, payload: EvaluatePayload, request: Request):
    collection = request.app.state.collection
    try:
        res = await collection.update_one(
            {"_id": item_id},
            {"$set": {"evaluated": {"type": payload.type, "note": payload.note}}}
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteItemsPayload(BaseModel):
    itemIds: List[int]

@app.delete("/api/items")
async def delete_items(payload: DeleteItemsPayload, request: Request):
    collection = request.app.state.collection
    if not payload.itemIds:
        raise HTTPException(status_code=400, detail="itemIds must be a non-empty array")
        
    res = await collection.delete_many({"_id": {"$in": payload.itemIds}})
    return {"success": True, "deletedCount": res.deleted_count, "message": f"Successfully deleted {res.deleted_count} items"}

@app.delete("/api/items/by-type/{type_num}")
async def delete_items_by_type(type_num: int, request: Request):
    collection = request.app.state.collection
    if type_num not in [2, 3]:
        raise HTTPException(status_code=400, detail="Invalid type. Only types 2 or 3 can be bulk deleted.")
        
    res = await collection.delete_many({"evaluated.type": type_num})
    return {"success": True, "deletedCount": res.deleted_count, "message": f"Successfully deleted {res.deleted_count} items with type {type_num}"}

@app.delete("/api/items/filtered")
async def delete_items_filtered(
    request: Request,
    category: Optional[int] = None,
    province: Optional[int] = None,
    minPrice: Optional[int] = None,
    maxPrice: Optional[int] = None,
    evaluatedType: Optional[int] = None,
    marketplace: Optional[str] = None,
    itemIds: Optional[str] = None
):
    collection = request.app.state.collection
    filter_query = {}
    
    if category is not None: filter_query["category"] = category
    if province is not None: filter_query["region"] = province
    
    if minPrice is not None or maxPrice is not None:
        filter_query["price"] = {}
        if minPrice is not None: filter_query["price"]["$gte"] = minPrice
        if maxPrice is not None: filter_query["price"]["$lte"] = maxPrice
        
    if evaluatedType is not None:
        if evaluatedType == 0:
            filter_query["evaluated"] = {"$exists": False}
        elif evaluatedType in [1, 2]:
            filter_query["evaluated.type"] = evaluatedType
    else:
        # Mặc định (khi chưa lọc type) chỉ hiển thị type 1 hoặc type chưa evaluate
        # Điều này giúp ẩn đi các item type 2 ở Frontend (soft delete)
        filter_query["$or"] = [
            {"evaluated": {"$exists": False}},
            {"evaluated.type": 1}
        ]
            
    if marketplace == 'marketplace':
        filter_query["marketplace_status.posted"] = True
        
    if itemIds:
        try:
            id_list = [int(id_str.strip()) for id_str in itemIds.split(',') if id_str.strip().isdigit()]
            if id_list:
                filter_query["_id"] = {"$in": id_list}
        except ValueError:
            pass
            
    if not filter_query:
        raise HTTPException(status_code=400, detail="Cannot delete with empty filter. Please specify at least one filter criteria.")
        
    res = await collection.delete_many(filter_query)
    return {"success": True, "deletedCount": res.deleted_count, "message": f"Successfully deleted {res.deleted_count} items matching filter criteria"}


# --- WebSocket endpoint ---
@app.websocket("/ws/crawl-status")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        state.ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
