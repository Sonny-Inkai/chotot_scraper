import os
from typing import Dict, Any

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # override=True ensures .env values take precedence over shell exports
    load_dotenv(override=True)
except ImportError:
    # dotenv not installed, skip
    pass

# API Configuration
CHOTOT_API_BASE = "https://gateway.chotot.com/v1/public/ad-listing"
ACCOUNT_AGE_MONTHS = 15
PRIORITY_CHECK_LIMIT = 5
CRAWL_LIMIT = 20

# Timing Configuration (in seconds)
MIN_INTERVAL = 30  # 30 seconds for hot routes
MAX_INTERVAL = 1800  # 30 minutes for cold routes
ONE_HOUR = 3600

# Price Configuration
MAX_PRICE = 2000000

# Crawling Configuration
MAX_PAGES_PER_ROUTE = 3  # Maximum pages to crawl if no items found
MAX_WORKERS = 10
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_FACTOR = 2

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "chotot_crawler"
MONGO_CRAWLED_ITEMS_COLLECTION = "crawled_item_ids"
COLLECTION_NAME="chotot_items"

# Queue Configuration (in-process asyncio priority queue)
MAX_PRIORITY = 255

# Item Filtering Criteria
MAX_SOLD_ADS = 3
MAX_TOTAL_RATING = 3
MIN_AVERAGE_RATING = 3.5

# Request Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache"
}

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" 