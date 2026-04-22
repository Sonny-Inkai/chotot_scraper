import asyncio
import logging
import statistics
from typing import Dict, List, Tuple, Optional
import aiohttp
import yaml
import json
import config

logger = logging.getLogger(__name__)

class PriorityCalculator:
    def __init__(self):
        self.session = None
        self.regions = {}
        self.categories = {}
        self._load_regions_and_categories()
    
    def _load_regions_and_categories(self):
        """Load regions and categories from files"""
        try:
            # Load regions
            with open('regions_and_areas.yml', 'r', encoding='utf-8') as f:
                regions_data = yaml.safe_load(f)
                for region_id, region_info in regions_data.items():
                    self.regions[int(region_id)] = region_info['name']
            
            # Load categories
            with open('chotot_categories.json', 'r', encoding='utf-8') as f:
                categories_data = json.load(f)
                for category_name, category_id in categories_data.items():
                    self.categories[category_id] = category_name
            
            logger.info(f"Loaded {len(self.regions)} regions and {len(self.categories)} categories")
        except Exception as e:
            logger.error(f"Error loading regions/categories: {e}")
            raise
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT),
            headers=config.DEFAULT_HEADERS
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.250)
    
    async def _fetch_sample_data(self, category: int, region: int) -> Optional[List[Dict]]:
        """
        Fetch sample data to calculate average list time interval
        """
        url = config.CHOTOT_API_BASE
        params = {
            "limit": config.PRIORITY_CHECK_LIMIT,
            "st": "s,k",
            "f": "p",
            "sp": "0",
            "cg": category,
            "region": region,
            "page": 0,
            "o": 0,
            "key_param_included": "true"
        }
        
        for attempt in range(config.MAX_RETRIES):
            try:
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        ads = data.get("ads", [])
                        if ads:
                            logger.debug(f"Fetched {len(ads)} ads for category {category}, region {region}")
                            return ads
                        else:
                            logger.warning(f"No ads found for category {category}, region {region}")
                            return []
                    else:
                        logger.warning(f"HTTP {response.status} for category {category}, region {region}")
                        
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for category {category}, region {region}: {e}")
                if attempt < config.MAX_RETRIES - 1:
                    await asyncio.sleep(config.BACKOFF_FACTOR ** attempt)
        
        return None
    
    def _calculate_average_interval(self, ads: List[Dict]) -> float:
        """
        Calculate average time interval between list_time values
        """
        try:
            if len(ads) < 2:
                return config.MAX_INTERVAL
            
            # Extract and sort list_time values
            list_times = [ad.get("list_time", 0) for ad in ads if ad.get("list_time")]
            if len(list_times) < 2:
                return config.MAX_INTERVAL
            
            list_times.sort()
            
            # Calculate intervals between consecutive list_times
            intervals = []
            for i in range(1, len(list_times)):
                interval = (list_times[i] - list_times[i-1]) / 1000  # Convert to seconds
                intervals.append(interval)
            
            if not intervals:
                return config.MAX_INTERVAL
            
            # Calculate average interval
            avg_interval = statistics.median(intervals)
            
            # Apply constraints
            if avg_interval < config.MIN_INTERVAL:
                avg_interval = config.MIN_INTERVAL
            elif avg_interval > config.ONE_HOUR:
                avg_interval = config.MAX_INTERVAL
            
            logger.debug(f"Calculated average interval: {avg_interval:.2f}s")
            return avg_interval
            
        except Exception as e:
            logger.error(f"Error calculating average interval: {e}")
            return config.MAX_INTERVAL
    
    def _calculate_priority(self, avg_interval: float) -> int:
        """
        Calculate priority based on average interval
        Lower interval = Higher priority (0-255, where 255 is highest)
        """
        try:
            # Normalize interval to priority scale (0-255)
            # MIN_INTERVAL gets highest priority (255)
            # MAX_INTERVAL gets lowest priority (0)
            if avg_interval <= config.MIN_INTERVAL:
                return config.MAX_PRIORITY
            elif avg_interval >= config.MAX_INTERVAL:
                return 0
            else:
                # Linear interpolation
                ratio = (config.MAX_INTERVAL - avg_interval) / (config.MAX_INTERVAL - config.MIN_INTERVAL)
                priority = int(ratio * config.MAX_PRIORITY)
                return max(0, min(config.MAX_PRIORITY, priority))
        except Exception as e:
            logger.error(f"Error calculating priority: {e}")
            return 0
    
    async def calculate_route_priority(self, category: int, region: int) -> Tuple[float, int]:
        """
        Calculate priority for a specific route
        Returns (average_interval, priority)
        """
        try:
            ads = await self._fetch_sample_data(category, region)
            if ads is None:
                logger.warning(f"Failed to fetch data for category {category}, region {region}")
                return config.MAX_INTERVAL, 0
            
            if not ads:
                logger.info(f"No ads available for category {category}, region {region}")
                return config.MAX_INTERVAL, 0
            
            avg_interval = self._calculate_average_interval(ads)
            priority = self._calculate_priority(avg_interval)
            
            category_name = self.categories.get(category, f"Unknown({category})")
            region_name = self.regions.get(region, f"Unknown({region})")
            
            logger.info(f"Route {category_name} in {region_name}: "
                       f"avg_interval={avg_interval:.2f}s, priority={priority}")
            
            return avg_interval, priority
            
        except Exception as e:
            logger.error(f"Error calculating route priority for category {category}, region {region}: {e}")
            return config.MAX_INTERVAL, 0
    
    async def calculate_all_routes_priority(self, routes: List[Tuple[int, int]]) -> List[Dict]:
        """
        Calculate priority for all routes concurrently
        Returns list of route info with priorities
        """
        logger.info(f"Calculating priority for {len(routes)} routes...")
        
        # Create concurrent tasks
        tasks = []
        for category, region in routes:
            task = self.calculate_route_priority(category, region)
            tasks.append((category, region, task))
        
        # Execute all tasks concurrently
        route_priorities = []
        completed_tasks = await asyncio.gather(*[task for _, _, task in tasks], return_exceptions=True)
        
        for i, (category, region, _) in enumerate(tasks):
            result = completed_tasks[i]
            if isinstance(result, Exception):
                logger.error(f"Error processing route {category}, {region}: {result}")
                avg_interval, priority = config.MAX_INTERVAL, 0
            else:
                avg_interval, priority = result
            
            route_info = {
                "category": category,
                "region": region,
                "category_name": self.categories.get(category, f"Unknown({category})"),
                "region_name": self.regions.get(region, f"Unknown({region})"),
                "avg_interval": avg_interval,
                "priority": priority
            }
            route_priorities.append(route_info)
        
        # Sort by priority (highest first) and then by avg_interval (lowest first) for ties
        route_priorities.sort(key=lambda x: (-x["priority"], x["avg_interval"]))
        
        logger.info(f"Priority calculation completed. Top route: "
                   f"{route_priorities[0]['category_name']} in {route_priorities[0]['region_name']} "
                   f"(priority={route_priorities[0]['priority']})")
        
        return route_priorities 