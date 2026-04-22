from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging, time, json, os, random, re
import undetected_chromedriver as uc

def get_cookie_filename(email, data_dir="browser_data"):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    # Làm sạch email để đặt tên file an toàn
    safe_email = re.sub(r'[^a-zA-Z0-9_.@-]', '_', email)
    return os.path.join(data_dir, f"browser_data_{safe_email}.json")

def save_browser_data(driver, email):
    filename = get_cookie_filename(email)
    data = {
        "cookies": driver.get_cookies(),
        "user_agent": driver.execute_script("return navigator.userAgent;"),
        "headers": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    logging.info(f"Browser data saved to {filename}")

def load_browser_data(driver, email):
    filename = get_cookie_filename(email)
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        for cookie in data.get("cookies", []):
            driver.add_cookie(cookie)
        logging.info(f"Browser data loaded from {filename}")
        return True
    return False

def setup_driver():
    """Setup undetected_chromedriver with anti-detection measures"""
    chrome_options = uc.ChromeOptions()
    
    # Disable automation-controlled features
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Disable sandbox and GPU features
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--disable-infobars")
    
    # Set natural user agent
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Run in non-headless mode
    chrome_options.headless = False
    
    driver = uc.Chrome(options=chrome_options)
    
    # Inject anti-detection JavaScript
    driver.execute_script("""
        (function() {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            if (window.chrome && window.chrome.runtime) {
                Object.defineProperty(window.chrome, 'runtime', { get: () => undefined });
            }
            for (let key in window) {
                if (key.startsWith('cdc_')) {
                    try {
                        delete window[key];
                    } catch(e) {}
                }
            }
            Object.defineProperty(window, 'devtools', { get: () => undefined });
            const originalConsoleLog = console.log;
            console.log = function(...args) {
                if (!args.some(arg => typeof arg === 'string' && arg.includes('undetected chromedriver 1337!'))) {
                    originalConsoleLog.apply(console, args);
                }
            };
            console.debug = function() {};
            Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
            Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight });
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) return 'Intel Inc.';
                if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                return getParameter.apply(this, arguments);
            };
            if (navigator.mediaDevices) {
                Object.defineProperty(navigator, 'mediaDevices', { get: () => undefined });
            }
            window.addEventListener('devtoolschange', function(event) {
                event.stopPropagation();
                event.preventDefault();
            }, true);
        })();
    """)
    
    return driver

def login_facebook(driver, email, password):
    """Login to Facebook with anti-detection measures"""
    logging.info(f"🔐 Logging in as {email}")
    
    driver.get("https://www.facebook.com/")
    time.sleep(5)

    try:
        # Check if browser data exists and load it
        data_loaded = load_browser_data(driver, email)
        
        if not data_loaded:
            # Enter credentials with natural typing delays
            email_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "email")))
            for char in email:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            time.sleep(random.uniform(1, 2))
            
            pass_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "pass")))
            for char in password:
                pass_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            time.sleep(random.uniform(1, 2))
            driver.find_element(By.NAME, "login").click()
            
            # Wait for page transition
            time.sleep(5)
            
            # Save browser data after successful login
            save_browser_data(driver, email)
        else:
            # If we have saved data, still need to enter credentials but with cookies
            email_input = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "email")))
            for char in email:
                email_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            time.sleep(random.uniform(1, 2))
            
            pass_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "pass")))
            for char in password:
                pass_input.send_keys(char)
                time.sleep(random.uniform(0.1, 0.3))
            
            time.sleep(random.uniform(1, 2))
            driver.find_element(By.NAME, "login").click()
            
            time.sleep(5)
            logging.info("Logged in using saved browser data.")

        # Check if login was successful
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search Facebook']"))
            )
            logging.info(f"✅ Successfully logged in as {email}")
            return True
        except:
            try:
                error_div = driver.find_element(By.XPATH, "//div[contains(text(), 'The email or mobile number you entered')]")
                logging.error(f"❌ Login failed: {error_div.text}")
                return False
            except:
                logging.error("❌ Login failed: Incorrect credentials or unknown error.")
                return False

    except Exception as e:
        logging.error(f"❌ Unexpected error logging in: {e}")
        return False
