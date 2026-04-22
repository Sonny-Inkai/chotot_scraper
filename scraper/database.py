import asyncio
import logging
import time
from typing import List, Dict, Any, Set
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError, DuplicateKeyError
import aiohttp
import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.crawled_items_collection = None
        self.items_collection = None
        self.session = None
    
    async def connect(self):
        """Connect to MongoDB"""
        try:
            self.client = AsyncIOMotorClient(config.MONGODB_URI)
            self.db = self.client[config.DB_NAME]
            self.crawled_items_collection = self.db[config.MONGO_CRAWLED_ITEMS_COLLECTION]
            self.items_collection = self.db[config.COLLECTION_NAME]
            
            # Create indexes for better performance
            # Note: _id field is already unique by default, no need to specify unique=True
            await self.items_collection.create_index("list_id", unique=True)
            await self.items_collection.create_index("category")
            await self.items_collection.create_index("region")
            await self.items_collection.create_index("list_time")
            
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=getattr(config, 'REQUEST_TIMEOUT', 10)),
                headers=getattr(config, 'DEFAULT_HEADERS', {})
            )
            
            logger.info(f"Connected to MongoDB successfully: {config.MONGODB_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.session:
            await self.session.close()
            
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    async def batch_check_existing_items(self, list_ids: List[int]) -> Set[int]:
        """
        Batch check which items already exist in crawled_items_collection
        Returns set of existing list_ids
        """
        try:
            cursor = self.crawled_items_collection.find(
                {"_id": {"$in": list_ids}},
                {"_id": 1}
            )
            existing_ids = set()
            async for doc in cursor:
                existing_ids.add(doc["_id"])
            
            logger.debug(f"Found {len(existing_ids)} existing items out of {len(list_ids)}")
            return existing_ids
        except Exception as e:
            logger.error(f"Error checking existing items: {e}")
            return set()
    
    async def save_crawled_item_ids(self, list_ids: List[int]) -> int:
        """
        Save list_ids to crawled_items_collection
        Returns number of successfully saved items
        """
        if not list_ids:
            return 0
        
        try:
            documents = [{"_id": list_id} for list_id in list_ids]
            result = await self.crawled_items_collection.insert_many(
                documents, 
                ordered=False  # Continue even if some inserts fail due to duplicates
            )
            saved_count = len(result.inserted_ids)
            logger.info(f"Saved {saved_count} new crawled item IDs")
            return saved_count
        except BulkWriteError as e:
            # Some items might already exist, that's okay
            saved_count = len(e.details.get('writeErrors', []))
            successful_count = len(list_ids) - saved_count
            logger.info(f"Saved {successful_count} new crawled item IDs (some already existed)")
            return successful_count
        except Exception as e:
            logger.error(f"Error saving crawled item IDs: {e}")
            return 0
    
    def _filter_item(self, item: Dict[str, Any]) -> bool:
        """
        Check if item meets filtering criteria
        """
        try:
            # Filter company ads
            if item.get("company_ad") is True:
                return False

            # Check sold_ads
            sold_ads = item.get("sold_ads", 0)
            if sold_ads >= config.MAX_SOLD_ADS:
                return False
            
            # Check total_rating if present
            total_rating = item.get("total_rating")
            if total_rating is not None and total_rating >= config.MAX_TOTAL_RATING:
                return False
            
            # Check average_rating if present
            average_rating = item.get("average_rating")
            if average_rating is not None and average_rating <= config.MIN_AVERAGE_RATING:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error filtering item {item.get('list_id', 'unknown')}: {e}")
            return False
    
    async def _is_account_valid(self, account_oid: str) -> bool:
        """Check if account is at least 15 months old."""
        if not account_oid:
            return False
        
        try:
            # Small delay to avoid aggressive rate limiting
            await asyncio.sleep(0.9)
            url = f"https://gateway.chotot.com/v1/public/profile/{account_oid}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    start_time = data.get("start_time")
                    if start_time is None:
                        is_valid = False
                    else:
                        current_time = int(time.time())
                        start_time_sec = start_time
                        account_age_months = (current_time - start_time_sec) / (30 * 24 * 60 * 60)
                        is_valid = account_age_months >= config.ACCOUNT_AGE_MONTHS # I wanna all accounts to be at least 15 months old
                elif response.status == 429:
                    logger.warning(f"Rate limited while checking account {account_oid}")
                    is_valid = True  # Don't delete if we're just rate limited
                else:
                    is_valid = False
                
                return is_valid
        except Exception as e:
            logger.error(f"Error checking account {account_oid}: {e}")
            return True  # Default to True on error to prevent accidental deletion

    async def save_items(self, items: List[Dict[str, Any]]) -> int:
        """
        Save filtered items to items_collection
        Returns number of successfully saved items
        """
        if not items:
            return 0
        
        # 1. Filter items based on basic criteria
        basic_filtered_items = []
        for item in items:
            if self._filter_item(item):
                item["_id"] = item["list_id"]
                basic_filtered_items.append(item)
        
        if not basic_filtered_items:
            return 0

        # 2. Check for scam accounts (async)
        filtered_items = []
        scam_count = 0
        
        # Process concurrently to avoid bottleneck
        tasks = [self._is_account_valid(item.get("account_oid")) for item in basic_filtered_items]
        results = await asyncio.gather(*tasks)
        
        for item, is_valid in zip(basic_filtered_items, results):
            if is_valid:
                filtered_items.append(item)
            else:
                logger.debug(f"Filtered out potential scam item {item.get('list_id')} (account: {item.get('account_oid')})")
                scam_count += 1
                
        if scam_count > 0:
            logger.info(f"Đã lọc bỏ {scam_count} items lừa đảo/rác trong mẻ này.")

        if not filtered_items:
            logger.info("No items passed the filtering criteria and scam check")
            return 0
        
        try:
            result = await self.items_collection.insert_many(
                filtered_items,
                ordered=False  # Continue even if some inserts fail due to duplicates
            )
            saved_count = len(result.inserted_ids)
            logger.info(f"Saved {saved_count} new items to database")
            return saved_count
        except BulkWriteError as e:
            # Some items might already exist, that's okay
            duplicate_count = len([err for err in e.details.get('writeErrors', []) 
                                 if err.get('code') == 11000])  # Duplicate key error code
            successful_count = len(filtered_items) - duplicate_count
            logger.info(f"Saved {successful_count} new items (some already existed)")
            return successful_count
        except Exception as e:
            logger.error(f"Error saving items: {e}")
            return 0
    
    async def get_route_stats(self, category: int, region: int) -> Dict[str, Any]:
        """
        Get statistics for a specific route
        """
        try:
            total_items = await self.items_collection.count_documents({
                "category": category,
                "region": region
            })
            
            latest_item = await self.items_collection.find_one(
                {"category": category, "region": region},
                sort=[("list_time", -1)]
            )
            
            return {
                "total_items": total_items,
                "latest_list_time": latest_item.get("list_time") if latest_item else None
            }
        except Exception as e:
            logger.error(f"Error getting route stats for category {category}, region {region}: {e}")
            return {"total_items": 0, "latest_list_time": None} 