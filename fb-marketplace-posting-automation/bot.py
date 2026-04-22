from selenium import webdriver
import os, logging, time, random
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import argparse

from core.facebook_login import login_facebook, setup_driver
from core.facebook_utils import read_credentials
from core.facebook_marketplace import post_to_marketplace

# Load environment variables
load_dotenv()

# Bot configuration
MAX_POSTS_PER_ACCOUNT_SESSION = 3 # Max items to post per account in one go
INTER_ACCOUNT_DELAY_MIN_SECONDS = 50 # Min delay between account switches (e.g., 3 minutes)
INTER_ACCOUNT_DELAY_MAX_SECONDS = 180 # Max delay between account switches (e.g., 5 minutes)

# MongoDB configuration
MONGODB_URI = os.getenv('MONGODB_URI')
DB_NAME = os.getenv('DB_NAME')
COLLECTION_NAME = os.getenv('COLLECTION_NAME')

# === Configure Logging with Daily Rotating Log Files ===

# Generate log file name with current date
today = datetime.now().strftime("%Y-%m-%d")
log_filename = f"logs/automation_{today}.log"

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# File handler - rotates logs daily, keeps 7 days of backup
file_handler = TimedRotatingFileHandler(log_filename, when="midnight", interval=1, backupCount=7, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"))

# Stream handler - console output
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"))

# Add handlers to the logger
logger.handlers = [file_handler, stream_handler]

def get_marketplace_items(item_ids=None):
    """
    Get items from MongoDB.
    If item_ids is provided, fetch those specific items.
    item_ids can be a single ID or a list of IDs.
    """
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    if item_ids:
        if not isinstance(item_ids, list):
            item_ids = [item_ids]  # Convert single item_id to list
            
        logging.info(f"Attempting to fetch specific item_ids: {item_ids}")
        items = []
        
        for item_id in item_ids:
            try:
                item = collection.find_one({"_id": item_id})
                if item:
                    # Check if the specific item is already posted or not suitable
                    if item.get("marketplace_status", {}).get("posted"):
                        logging.warning(f"Item {item_id} has already been posted.")
                        continue
                    if item.get("evaluated", {}).get("type") != 1:
                        logging.warning(f"Item {item_id} is not marked as 'Should Buy' (type 1).")
                        # Allow posting anyway if specifically requested by ID
                    items.append(item)
                else:
                    logging.warning(f"Specific item_id: {item_id} not found in database.")
            except ValueError:
                logging.error(f"Invalid item_id format: {item_id}. Must be an integer.")
            except Exception as e:
                logging.error(f"Error fetching specific item_id {item_id}: {e}")
        
        return items
    else:
        # Query for items with evaluated.type = 1 and no marketplace_status
        query = {
            "evaluated.type": 1,
            "marketplace_status": {"$exists": False}
        }
        # Sort by ROI in descending order
        items = list(collection.find(query).sort("evaluated.roi", -1))
        logging.info(f"Found {len(items)} items to post based on general query.")
        return items

def update_marketplace_status(item_id):
    """Update item's marketplace status in MongoDB"""
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    
    update_data = {
        "marketplace_status": {
            "posted": True,
            "posted_at": datetime.now(),
            "status": "active"
        }
    }
    
    collection.update_one(
        # Adjust if your _id is not an int
        {"_id": item_id},
        {"$set": update_data}
    )

def run_bot(item_ids_to_post=None):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CRED_PATH = os.path.join(BASE_DIR, "data", "credentials.txt")
    
    # Get marketplace items from MongoDB
    marketplace_items = get_marketplace_items(item_ids_to_post)
    
    if not marketplace_items:
        if item_ids_to_post:
            logging.warning(f"Could not proceed with specified item_ids: {item_ids_to_post}.")
        else:
            logging.warning("No suitable marketplace items found in database for general posting.")
        return

    all_accounts = read_credentials(CRED_PATH)
    marketplace_success = 0
    marketplace_failure = 0
    # Keep track of successfully listed item IDs in the current run_bot session
    # to avoid trying to re-list if an error occurs mid-process for an account.
    # This is different from marketplace_items which is the master list of items to attempt.
    posted_item_ids_this_run = set()

    for account_idx, (email, password) in enumerate(all_accounts):
        if not marketplace_items: # Check if all items are posted before starting a new account
            logging.info("All available items have been processed. Exiting account loop early.")
            break

        logging.info(f"Processing account: {email} ({account_idx + 1}/{len(all_accounts)})")
        posts_this_session = 0
        
        # Use undetected_chromedriver instead of regular selenium webdriver
        driver = setup_driver()

        try:
            logged_msg = login_facebook(driver, email, password)
            if logged_msg:
                # Post to marketplace
                # If specific item_ids were given, marketplace_items will contain only those items.
                # Otherwise, it will take up to MAX_POSTS_PER_ACCOUNT_SESSION items from the general query.
                
                # Filter out already processed items by this bot run from the available marketplace_items
                # This is to handle cases where the list isn't modified correctly due to an error for a previous account
                items_available_for_posting = [item for item in marketplace_items if item['_id'] not in posted_item_ids_this_run]
                
                if not items_available_for_posting:
                    logging.info(f"No new items to post for account {email} from the remaining list.")
                    # No need to continue with this account if all remaining items were already processed in this run
                    # or if the marketplace_items list itself is empty (which is checked at start of loop)
                    # driver.quit() will be called in finally
                    continue # Move to the next account

                items_to_process_this_account = items_available_for_posting[:MAX_POSTS_PER_ACCOUNT_SESSION]
                logging.info(f"Account {email} will attempt to post up to {MAX_POSTS_PER_ACCOUNT_SESSION} items. Trying {len(items_to_process_this_account)} items now.")

                for item in items_to_process_this_account:
                    if item['_id'] in posted_item_ids_this_run:
                        logging.info(f"Item {item['_id']} has already been successfully posted in this bot run. Skipping.")
                        continue # Should not happen if items_available_for_posting is filtered correctly

                    image_urls = item.get("item_images", [])
                    if image_urls:
                        marketplace_result = post_to_marketplace(driver, item, image_urls)
                        if marketplace_result:
                            marketplace_success += 1
                            posts_this_session += 1
                            logging.info(f"Successfully posted item: {item.get('_id')} with account {email}")
                            update_marketplace_status(item["_id"]) # Update DB
                            posted_item_ids_this_run.add(item["_id"]) # Mark as posted in this run
                            
                            # Critical: Remove the item from the main marketplace_items list 
                            # so it's not picked up by subsequent accounts or retries within this run.
                            try:
                                marketplace_items.remove(item)
                                logging.info(f"Item {item['_id']} removed from the main list for this bot session.")
                            except ValueError:
                                logging.warning(f"Item {item['_id']} was already removed or not found in marketplace_items. This might be okay if handled.")
                        else:
                            marketplace_failure += 1
                if not marketplace_items:
                    logging.info("All requested items have been posted. Exiting account loop.")
                    break
                # Add a small delay even if login failed or no items were posted by this account
                time.sleep(random.uniform(5, 10))
            else:
                logging.info(f"Login Failed for {email}")
                # Consider adding a longer penalty delay for accounts that fail to log in
                # or a mechanism to temporarily disable them.

        finally:
            logging.info(f"Logging out and closing browser for {email}. Posted {posts_this_session} items this session.")
            driver.quit()
            # Inter-account delay only if there are more accounts to process
            if account_idx < len(all_accounts) - 1 and marketplace_items:
                delay = random.uniform(INTER_ACCOUNT_DELAY_MIN_SECONDS, INTER_ACCOUNT_DELAY_MAX_SECONDS)
                logging.info(f"Waiting for {delay:.2f} seconds before switching to the next account...")
                time.sleep(delay)
            elif not marketplace_items:
                logging.info("All items processed, no further inter-account delay needed.")
            else:
                logging.info("Last account processed.")

    # Final Summary
    logging.info("=" * 50)
    logging.info(f"🛍️ Total Marketplace Items Successfully Posted: {marketplace_success}")
    logging.info(f"❌ Total Marketplace Items Failed: {marketplace_failure}")
    logging.info("=" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Marketplace Posting Automation Script.")
    parser.add_argument("--item", dest="item_ids", nargs='*', type=int,
                        help="Optional: The specific _id(s) of the items to post. Separate with spaces: --item 123456 789012")
    args = parser.parse_args()

    logging.info("=" * 50)
    logging.info("🚀 Starting Facebook Marketplace Posting Automation Script")
    
    item_ids_to_post = args.item_ids if args.item_ids else None
    if item_ids_to_post:
        logging.info(f"Targeting specific item_ids: {item_ids_to_post}")
        
    logging.info(f"🕒 Run started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 50)
    
    run_bot(item_ids_to_post=item_ids_to_post)
