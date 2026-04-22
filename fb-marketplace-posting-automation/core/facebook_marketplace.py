import os
import json
import requests
import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Helper function to simulate typing
def simulate_typing(element, text):
    for character in text:
        element.send_keys(character)
        time.sleep(random.uniform(0.05, 0.2)) # Short delay between keystrokes

def download_image(url, save_path):
    """Download image from URL to local path"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"Error downloading image: {e}")
    return False

def post_to_marketplace(driver, item_data, image_urls):
    """Post item to Facebook Marketplace"""
    try:
        # Navigate to marketplace create page
        driver.get("https://www.facebook.com/marketplace/create/item")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        time.sleep(random.uniform(5, 8)) # Increased base delay

        # Download and prepare images
        temp_images = []
        for idx, img_url in enumerate(image_urls):
            # Get absolute path for temp image
            temp_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", f"temp_image_{idx}.jpg"))
            if download_image(img_url, temp_path):
                temp_images.append(temp_path)

        if not temp_images:
            print("No images downloaded successfully")
            return False

        # Upload images
        upload_input = driver.find_element(By.XPATH, "//input[@type='file']")
        # Join paths with newlines and ensure they're absolute
        upload_input.send_keys("\n".join(temp_images))
        time.sleep(random.uniform(10, 15)) # Increased delay after image upload

        # Fill in item details
        # Wait for title input to be present
        title_input_xpath = "(//input[@type='text'])[1]"
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, title_input_xpath))
        )
        text_inputs = driver.find_elements(By.XPATH, "//input[@type='text']")
        
        if text_inputs:
            # Use new_title if available, otherwise use original title
            title = item_data.get("evaluated", {}).get("new_title", item_data.get("title", "No Title"))
            simulate_typing(text_inputs[0], title)
            time.sleep(random.uniform(2, 4))
            
            # Use sell_price if available, otherwise use original price
            price = item_data.get("evaluated", {}).get("sell_price", item_data.get("price", "0"))
            # Price input is usually the second text input, adjust if Facebook changes layout
            if len(text_inputs) > 1:
                simulate_typing(text_inputs[1], str(price))
                time.sleep(random.uniform(2, 4))
            else:
                print("Could not find price input field based on current selectors.")

        # Select category and condition
        dropdowns = driver.find_elements(By.XPATH, "//label[@aria-labelledby]")
        if len(dropdowns) >= 2:
            # Category
            dropdowns[0].click()
            time.sleep(random.uniform(1.5, 3))
            category = item_data.get("evaluated", {}).get("category", "Electronics & computers")
            driver.find_element(By.XPATH, f"//span[text()='{category}']").click()
            time.sleep(random.uniform(1.5, 3))

            # Condition
            dropdowns[1].click()
            time.sleep(random.uniform(1.5, 3))
            condition = "Used - Good"
            driver.find_element(By.XPATH, f"//span[text()='{condition}']/ancestor::div[@role='option']").click()
            time.sleep(random.uniform(1.5, 3))

        # Description
        description_xpath = "//span[text()='Description']/following::textarea[1]" # More robust description selector
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, description_xpath))
        )
        description_text = item_data.get("detailed_description", "No description provided.")
        simulate_typing(driver.find_element(By.XPATH, description_xpath), description_text)
        time.sleep(random.uniform(2, 4))
        
        # Tags - Facebook UI for tags can be tricky, ensure XPATH is correct if re-enabling
        # tags = item_data.get("evaluated", {}).get("tags", [])
        # if tags:
        #     tag_input_xpath = "//textarea[@aria-label='Product tags']" # Example XPATH
        #     try:
        #         WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, tag_input_xpath)))
        #         tag_input_element = driver.find_element(By.XPATH, tag_input_xpath)
        #         for tag in tags:
        #             simulate_typing(tag_input_element, tag)
        #             time.sleep(random.uniform(1.5, 3))
        #             tag_input_element.send_keys(Keys.ENTER)
        #             time.sleep(random.uniform(1.5, 3))
        #     except Exception as e:
        #         print(f"Could not add tags: {e}")

        # Location
        location = random.choice(["Xa Trang Bom, Vietnam", "Biên Hòa", "Ho Nai, Vietnam", "Thủ Đức, Ho Chi Minh City, Vietnam", "Tỉnh Đồng Nai", "quan 12", "quan 9", "da kao" ])
        location_input = driver.find_element(By.XPATH, "//input[@aria-label='Location']")
        location_input.send_keys(Keys.CONTROL + "a")
        location_input.send_keys(Keys.DELETE)
        time.sleep(random.uniform(1.5, 3))
        location_input.send_keys(location)
        time.sleep(random.uniform(1.5, 3))
        driver.find_element(By.XPATH, "//ul[@role='listbox']/li[1]").click()
        time.sleep(random.uniform(1.5, 3))

        switches = driver.find_elements(By.XPATH, '//input[@role="switch" and @type="checkbox"]')
        switches[0].click()  # Button 1
        time.sleep(random.uniform(1.5, 3))
        switches[1].click()  # Button 2
        time.sleep(random.uniform(1.5, 3))

        # Publish
        driver.find_element(By.CSS_SELECTOR, "[aria-label='Next']").click()
        time.sleep(random.uniform(8, 12))

        publish_button_css = "[aria-label='Publish']"
        WebDriverWait(driver, 20).until( # Increased wait for publish button
            EC.element_to_be_clickable((By.CSS_SELECTOR, publish_button_css))
        )
        driver.find_element(By.CSS_SELECTOR, publish_button_css).click()
        time.sleep(random.uniform(35, 50)) # Increased delay after publishing

        # Clean up temp images
        for img_path in temp_images:
            try:
                os.remove(img_path)
            except OSError as e: # Catch specific os error for file removal
                print(f"Error removing temp image {img_path}: {e}")
            except Exception as e:
                print(f"General error removing temp image {img_path}: {e}")
        return True

    except Exception as e:
        print(f"Error posting to marketplace: {e}")
        # Consider taking a screenshot on error for debugging
        # driver.save_screenshot(f"error_screenshot_{time.time()}.png")
        return False 