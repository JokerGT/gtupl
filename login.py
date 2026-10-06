import json
import re
import sys
import time
from curl_cffi import requests as cffi_requests
import keyring
from seleniumbase import SB

# Configuration Constants
SERVICE_NAME = "gaytor_app"
KEYRING_USERNAME = "session_cookies"  # Restored to original key name for compatibility

LOGIN_URL = "https://www.gaytor.rent/login.php"
USERDETAILS_URL = "https://www.gaytor.rent/userdetails.php"
TARGET_DOMAIN = "https://www.gaytor.rent"

# Fixed User-Agent so HTTP requests and browser sessions match exactly
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def get_stored_session() -> dict | None:
  """Pure retrieval function: Fetches and deserializes session data from Keyring

  without side effects or logging.
  """
  try:
    data_str = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
    if data_str:
      parsed = json.loads(data_str)
      if isinstance(parsed, list):
        # Backward compatibility for older plain cookie lists
        return {"cookies": parsed, "username": None}
      elif isinstance(parsed, dict):
        return parsed
  except Exception as e:
    print(f"[Keyring Error] Failed to read session data: {e}")
  return None


def save_session_to_keyring(cookies: list, username: str | None) -> bool:
  """Serialize and save cookies and username securely to System Keyring."""
  try:
    payload = {"cookies": cookies, "username": username}
    data_str = json.dumps(payload)
    keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, data_str)
    print(
        "[Keyring] Successfully stored updated session data (cookies +"
        f" username: {username}) in Keyring"
    )
    return True
  except Exception as e:
    print(f"[Keyring Error] Failed to save session data: {e}")
    return False


def validate_session(cookies: list) -> bool:
  """Sends an HTTP GET request to login.php.

  If cookies are valid, the server redirects to index.php.
  """
  print("[LOGIN] Validating session...")

  cookie_dict = {
      cookie["name"]: cookie["value"]
      for cookie in cookies
      if "name" in cookie and "value" in cookie
  }

  headers = {"User-Agent": USER_AGENT}

  try:
    # Disable automatic redirects to catch the 302 redirect to index.php
    response = cffi_requests.get(
        LOGIN_URL,
        cookies=cookie_dict,
        headers=headers,
        impersonate="chrome",
        allow_redirects=False,
        timeout=10,
    )

    # 301 or 302 redirect means the server processed our cookies and sent us away from login.php
    if response.status_code in (301, 302):
      location = response.headers.get("Location", "")
      if "index.php" in location:
        print(
            "[LOGIN] LOGIN SUCCESS"
        )
        return True
      else:
        print(
            f"[LOGIN] Web Page returned a Redirection: {location}"
        )
        return False
    elif response.status_code == 200:
      print(
          "[LOGIN] EXPIRED SESSION"
      )
      return False
    else:
      print(f"[LOGIN ERROR] Failed with HTTP response: {response.status_code}")
      return False

  except Exception as e:
    print(f"[LOGIN ERROR] Request failed: {e}")
    return False


def fetch_username_via_curl(cookies: list) -> str | None:
  print("[LOGIN] Fetching username...")
  cookie_dict = {
      cookie["name"]: cookie["value"]
      for cookie in cookies
      if "name" in cookie and "value" in cookie
  }
  headers = {"User-Agent": USER_AGENT}

  try:
    response = cffi_requests.get(
        USERDETAILS_URL,
        cookies=cookie_dict,
        headers=headers,
        impersonate="chrome",
        timeout=10,
    )
    if response.status_code == 200:
      html_content = response.text
      match = re.search(
          r'<div class="ud-profile-name">(.*?)</div>', html_content, re.DOTALL
      )
      if match:
        inner_html = match.group(1)
        clean_text = re.sub(r"<[^>]+>", "", inner_html)
        lines = [
            line.strip() for line in clean_text.splitlines() if line.strip()
        ]
        if lines:
          username = lines[0]
          print(f"[LOGIN] Successfully retrieved username: '{username}'")
          return username
    print(
        "[WARNING] Could not extract username from page response"
    )
  except Exception as e:
    print(f"[WARNING] Request failed: {e}")
  return None


def acquire_cookies_via_browser() -> list | None:
  """Launches SeleniumBase in UC mode, lets user log in, and closes immediately upon redirect."""

  captured_cookies = None

  with SB(uc=True, headless=False) as sb:
    # Open login page and handle initial load
    sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=4)
    sb.driver.switch_to.default_content()

    print("\n" + "=" * 60)
    print("[SELENIUM] ACTION REQUIRED: Log in using the browser window")
    print("=" * 60 + "\n")

    # Poll current URL until user logs in and gets redirected
    timeout = 120  # 2 minutes
    start_time = time.time()

    while True:
      current_url = sb.get_current_url()

      if (
          current_url.startswith(TARGET_DOMAIN)
          and "login.php" not in current_url
      ):
        print(f"[SELENIUM] Redirect detected! Target URL reached: {current_url}")
        break

      if time.time() - start_time > timeout:
        print("[SELENIUM] Timed out waiting for login redirect")
        return None

      time.sleep(1)

    # Ensure focus is on top-level frame before grabbing cookies
    sb.driver.switch_to.default_content()

    # Capture authenticated cookie snapshot
    captured_cookies = sb.driver.get_cookies()
    print(f"[SELENIUM] Captured session data")

  # Browser closes immediately here upon exiting the 'with' block
  return captured_cookies


def ensure_logged_in() -> bool:
  """Main entry point: Checks stored cookies without opening browser.

  If valid, ensures username is present (fetching via curl if missing). If
  invalid/missing, runs browser login.
  """
  # Step 1: Retrieve stored session data from keyring
  session_data = get_stored_session()

  # Step 2: Check if session data exists and validate cookies via HTTP request
  if session_data:
    print("[LOGIN] Session data found in Keyring")
    cookies = session_data.get("cookies", [])
    
    if validate_session(cookies):
      username = session_data.get("username")

      # Step 3: If cookies are valid but username is missing, fetch it via curl
      if not username:
        print(
            "[LOGIN] Session is valid, but username is missing. Fetching username..."
        )
        username = fetch_username_via_curl(cookies)
        if username:
          save_session_to_keyring(cookies, username)

      print(
          f"[LOGIN] Session is valid and ready to use! Username: {username}"
      )
      return True

  # Step 4: If no session exists or validation failed, run Selenium fallback workflow
  print("[LOGIN] No valid session found. Opening browser for login...")
  fresh_cookies = acquire_cookies_via_browser()

  if fresh_cookies:
    # Step 5: Use curl to fetch the username post-login without disrupting app flow
    username = fetch_username_via_curl(fresh_cookies)

    # Step 6: Persist fresh cookies and username to keyring
    save_session_to_keyring(fresh_cookies, username)
    print("[LOGIN] Session saved to Keyring")
    return True
  else:
    print("[LOGIN ERROR] Failed to acquire fresh cookies")
    return False


if __name__ == "__main__":
  # Allows testing login.py directly as a standalone script
  success = ensure_logged_in()
  sys.exit(0 if success else 1)