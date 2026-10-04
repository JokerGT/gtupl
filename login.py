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
  """Retrieve and deserialize session data from Keyring.

  Supports backward compatibility if only a raw list of cookies was previously
  stored.
  """
  try:
    data_str = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
    if data_str:
      print("[Keyring] Found stored session data.")
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
        f" username: {username}) in Keyring."
    )
    return True
  except Exception as e:
    print(f"[Keyring Error] Failed to save session data: {e}")
    return False


def validate_session(cookies: list) -> bool:
  """Sends an HTTP GET request to login.php.

  If cookies are valid, the server redirects to index.php.
  """
  print("[Session Check] Testing stored cookies against login.php...")

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
            "[Session Check] SUCCESS! Session cookies are valid (redirected"
            f" to {location})."
        )
        return True
      else:
        print(
            f"[Session Check] Redirected elsewhere instead of index: {location}"
        )
        return False
    elif response.status_code == 200:
      # Staying on 200 OK means we weren't logged in, so we just loaded the login form page
      print(
          "[Session Check] EXPIRED. Server returned 200 OK on login.php (not"
          " logged in)."
      )
      return False
    else:
      print(f"[Session Check] Failed with status code: {response.status_code}")
      return False

  except Exception as e:
    print(f"[Session Check Error] Request failed: {e}")
    return False

  except Exception as e:
    print(f"[Session Check Error] Request failed: {e}")
    return False


def fetch_username_via_curl(cookies: list) -> str | None:
  """Fetches the username from userdetails.php using curl_cffi with existing cookies."""
  print("[Username Fetch] Fetching username from userdetails.php via curl...")
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
      # Locate the username inside <div class="ud-profile-name">
      match = re.search(
          r'<div class="ud-profile-name">(.*?)</div>', html_content, re.DOTALL
      )
      if match:
        inner_html = match.group(1)
        # Strip HTML tags like <img>
        clean_text = re.sub(r"<[^>]+>", "", inner_html)
        lines = [
            line.strip() for line in clean_text.splitlines() if line.strip()
        ]
        if lines:
          username = lines[0]
          print(f"[Username Fetch] Successfully retrieved username: '{username}'")
          return username
    print(
        "[Username Fetch Warning] Could not extract username from page response."
    )
  except Exception as e:
    print(f"[Username Fetch Error] Request failed: {e}")
  return None


def acquire_cookies_via_browser() -> list | None:
  """Launches SeleniumBase in UC mode, lets user log in, and closes immediately upon redirect."""
  print("\n[Browser] Launching browser to capture fresh session cookies...")


  captured_cookies = None

  with SB(uc=True, headless=False) as sb:
    # Open login page and handle initial load
    sb.uc_open_with_reconnect(LOGIN_URL, reconnect_time=4)
    sb.driver.switch_to.default_content()

    print("\n" + "=" * 60)
    print("ACTION REQUIRED: Log in on the browser window.")
    print("Waiting for redirection to gaytor.rent index page...")
    print("=" * 60 + "\n")

    # Poll current URL until user logs in and gets redirected
    timeout = 300  # 5 minutes
    start_time = time.time()

    while True:
      current_url = sb.get_current_url()

      # Check if landed on index.php or redirected away from login.php to main domain
      if (
          current_url.startswith(TARGET_DOMAIN)
          and "login.php" not in current_url
      ):
        print(f"[Browser] Redirect detected! Target URL reached: {current_url}")
        break

      if time.time() - start_time > timeout:
        print("[Browser] Timed out waiting for login redirect.")
        return None

      time.sleep(1)

    # Ensure focus is on top-level frame before grabbing cookies
    sb.driver.switch_to.default_content()

    # Capture authenticated cookie snapshot
    captured_cookies = sb.driver.get_cookies()
    print(f"[Browser] Captured {len(captured_cookies)} cookies.")

  # Browser closes immediately here upon exiting the 'with' block
  return captured_cookies


def ensure_logged_in() -> bool:
  """Main entry point: Checks stored cookies without opening browser.

  If valid, ensures username is present (fetching via curl if missing). If
  invalid/missing, runs browser login.
  """
  session_data = get_stored_session()

  # Step 1: If session data exists, validate the cookies via HTTP request (No browser opened)
  if session_data and validate_session(session_data.get("cookies", [])):
    cookies = session_data.get("cookies")
    username = session_data.get("username")

    # Step 2: If cookies are valid but username is missing, fetch it via curl
    if not username:
      print(
          "[Main] Session is valid, but username is missing. Fetching username"
          " via curl..."
      )
      username = fetch_username_via_curl(cookies)
      if username:
        save_session_to_keyring(cookies, username)

    print(
        f"\n[Main] Session is valid and ready to use! Username: {username}."
        " Proceeding with app tasks..."
    )
    return True

  # Step 3: If no valid session, run Selenium fallback workflow
  print("\n[Main] No valid session found. Opening browser for login...")
  fresh_cookies = acquire_cookies_via_browser()

  if fresh_cookies:
    # Step 4: Use curl to fetch the username post-login without disrupting app flow
    username = fetch_username_via_curl(fresh_cookies)

    # Step 5: Persist fresh cookies and username to keyring
    save_session_to_keyring(fresh_cookies, username)
    print("\n[Main] Setup completed successfully! Session saved to Keyring.")
    return True
  else:
    print("\n[Main] Failed to acquire fresh cookies.")
    return False


if __name__ == "__main__":
  # Allows testing login.py directly as a standalone script
  success = ensure_logged_in()
  sys.exit(0 if success else 1)