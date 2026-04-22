from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, logging

def post_in_facebook_group(driver, group_url, media_files, caption):
    try:
        driver.get(group_url)
        logging.info(f"🌐 Navigated to group: {group_url}")

        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//span[contains(text(), 'Write something...')]"
            ))
        ).click()
        logging.info("📝 Clicked 'Write something...'")

        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Add to your post')]"))
        ).click()
        logging.info("➕ Clicked 'Add to your post'")

        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Photo/video')]"))
        ).click()
        logging.info("🖼️ Clicked 'Photo/video'")

        post_area = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@role='textbox' and contains(@aria-label, 'Write something') or contains(@aria-label, 'Create a public post')]")
            )
        )
        if caption:
            post_area.send_keys(caption)
            logging.info("✍️ Added 'Added Caption to the Post'")
        else:
            logging.info("⚠️ No caption provided.")
        time.sleep(2)

        try:
            file_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "(//input[@type='file' and @class='x1s85apg'])[2]"))
            )
            file_input.send_keys("\n".join(media_files))
            logging.info("Uploaded 'Media files'")
            
            # ✅ Wait for the media preview to appear
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'scontent')]"))
            )
            logging.info("✅ Media preview loaded successfully")
            time.sleep(2)
        except Exception as e:
            logging.error(f"❌ File input error for media: {e}")
            return False

        # Click Post button
        try:
            post_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Post' and @role='button']"))
            )
            post_button.click()
            logging.info("🚀 Post submitted successfully.")
            time.sleep(5)
        except Exception as e:
            logging.error(f"❌ Could not click the Post button: {e}")
            return False

        return True

    except Exception as e:
        logging.error(f"💥 Error posting in group {group_url} | \n Error: {e}")
        return False
