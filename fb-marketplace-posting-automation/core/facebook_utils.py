import os, logging


def load_caption(caption_path):
    try:
        if os.path.exists(caption_path):
            with open(caption_path, "r", encoding="utf-8") as caption_file:
                caption = caption_file.read().strip()
                return ''.join(c for c in caption if c <= '\uFFFF')
        else:
            logging.warning(f"Caption file does not exist: {caption_path}")
            return ""
    except Exception as e:
        logging.error(f"Error reading caption: {e}")
        return ""

    

def read_credentials(cred_path):
    credentials = []
    try:
        with open(cred_path, "r", encoding="utf-8") as cred_file:
            for line in cred_file:
                line = line.strip()
                if line and ',' in line:
                    email, password = line.split(',', 1)
                    credentials.append((email.strip(), password.strip()))
        return credentials
    except FileNotFoundError:
        logging.error(f"The file '{cred_path}' does not exist.")
        return []
    except Exception as e:
        logging.error(f"An error occurred while reading credentials: {e}")
        return []


def read_groups_url(group_path):
    try:
        with open(group_path, "r", encoding="utf-8") as group_file:
            return [line.strip() for line in group_file if line.strip()]
    except FileNotFoundError:
        print(f"The file '{group_path}' does not exist.")
        return []
    except Exception as e:
        print(f"An error occurred while reading group urls: {e}")
        return []


def failed_log(FAILED_PATH, group_url, email):
    try:
        with open(FAILED_PATH, "a", encoding="utf-8") as f:
            f.write(f"{group_url}\n")
        logging.error(f"Failed to post in group: {group_url} with account: {email}")
    except Exception as e:
        logging.error(f"Error logging failed group: {e}")



def update_failed_groups_file(FAILED_PATH, failed_group_urls):
    """
    Overwrites the failed group URL file with the updated list (after retry).
    Accepts a list of still-failing group URLs.
    """
    try:
        with open(FAILED_PATH, 'w', encoding='utf-8') as f:
            for group_url in failed_group_urls:
                f.write(group_url.strip() + '\n')
        logging.info(f"Updated failed groups file with {len(failed_group_urls)} entries.")
    except Exception as e:
        logging.error(f"Failed to update failed groups file: {e}")
