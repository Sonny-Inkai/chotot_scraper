#!/usr/bin/env python3
"""
Monitor script to watch continuous crawling system
"""

import asyncio
import time
from queue_manager import QueueManager
from database import DatabaseManager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def monitor_system():
    """Monitor the crawling system"""
    queue_manager = QueueManager()
    db_manager = DatabaseManager()
    
    try:
        await queue_manager.connect()
        await db_manager.connect()
        
        logger.info("=== Monitoring Continuous Crawling System ===")
        
        start_time = time.time()
        last_stats = {"routes_processed": 0, "items_saved": 0}
        
        while True:
            try:
                # Get queue stats
                queue_stats = await queue_manager.get_queue_stats()
                
                # Get database stats
                total_items = await db_manager.items_collection.count_documents({})
                total_crawled_ids = await db_manager.crawled_items_collection.count_documents({})
                
                # Calculate runtime
                runtime = time.time() - start_time
                
                print(f"\n=== System Status (Runtime: {runtime:.1f}s) ===")
                print(f"Queue: {queue_stats['message_count']} messages, {queue_stats['consumer_count']} consumers")
                print(f"Database: {total_items} items saved, {total_crawled_ids} IDs tracked")
                print(f"Rate: {total_items/runtime*60:.1f} items/minute")
                
                # Check for new activity
                if total_items > last_stats["items_saved"]:
                    new_items = total_items - last_stats["items_saved"]
                    print(f"✅ NEW: {new_items} items saved since last check")
                    last_stats["items_saved"] = total_items
                
                # Show recent activity from logs
                print("\n=== Recent Activity ===")
                try:
                    with open('crawler.log', 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        recent_lines = [line.strip() for line in lines[-10:] 
                                      if 'Completed route' in line or 'Processed page' in line]
                        for line in recent_lines[-5:]:
                            print(f"  {line}")
                except:
                    print("  Could not read recent logs")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(10)
    
    finally:
        await queue_manager.disconnect()
        await db_manager.disconnect()
        print("\n=== Monitoring stopped ===")

if __name__ == "__main__":
    asyncio.run(monitor_system()) 