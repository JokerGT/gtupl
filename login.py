import json
import re
import sys
import keyring
import requests

# Configuration Constants
SERVICE_NAME = "gaytor_app"
KEYRING_USERNAME = "api_key"

API_BASE = "https://www.gaytor.rent/api/v1"
API_KEY_PATTERN = re.compile(r"gtk_[A-Za-z0-9]+")

# Sent as the User-Agent of every request the uploader makes
CLIENT_NAME = "gtupl"


def _read_stored_entry() -> dict:
  """Pure retrieval function: Fetches and deserializes the stored API key entry

  from Keyring. Returns an empty dict when nothing usable is stored.
  """
  try:
    data_str = keyring.get_password(SERVICE_NAME, KEYRING_USERNAME)
    if data_str:
      parsed = json.loads(data_str)
      if isinstance(parsed, dict):
        return parsed
  except Exception as e:
    print(f"[Keyring Error] Failed to read the stored API key: {e}")
  return {}


def get_api_key() -> str | None:
  """Returns the stored personal API key, or None."""
  return _read_stored_entry().get("api_key") or None


def get_stored_username() -> str | None:
  """Returns the username the stored API key belongs to, or None."""
  return _read_stored_entry().get("username") or None


def save_api_key(api_key: str, username: str | None) -> bool:
  """Serialize and save the API key and username securely to System Keyring."""
  try:
    data_str = json.dumps({"api_key": api_key, "username": username})
    keyring.set_password(SERVICE_NAME, KEYRING_USERNAME, data_str)
    print(
        "[Keyring] Successfully stored the API key"
        f" (username: {username}) in Keyring"
    )
    return True
  except Exception as e:
    print(f"[Keyring Error] Failed to save the API key: {e}")
    return False


def clear_api_key() -> bool:
  """Removes the stored API key from Keyring.

  The key itself keeps working on the site until it is revoked there.
  """
  try:
    if keyring.get_password(SERVICE_NAME, KEYRING_USERNAME) is not None:
      keyring.delete_password(SERVICE_NAME, KEYRING_USERNAME)
      print("[Keyring] Removed the stored API key from Keyring")
    return True
  except Exception as e:
    print(f"[Keyring Error] Failed to remove the API key: {e}")
    return False


def auth_headers(api_key: str | None = None) -> dict:
  """Returns the headers that authenticate an API request.

  Uses the stored key unless one is passed in.
  """
  key = api_key or get_api_key()
  return {"Authorization": f"Bearer {key}"} if key else {}


def _check_api_key(api_key: str) -> tuple[dict | None, str]:
  """Asks the site who the key belongs to.

  Returns (data, "") when the key works, where data looks like
  {"username": ..., "via": "apikey", "key_label": ..., "scope": "upload"}.
  Otherwise returns (None, reason) with a short, user-facing reason.
  """
  if not API_KEY_PATTERN.fullmatch(api_key or ""):
    return None, "That does not look like an API key (keys start with gtk_)."

  print("[LOGIN] Validating API key...")
  headers = auth_headers(api_key)
  headers.update({"User-Agent": CLIENT_NAME, "Accept": "application/json"})

  try:
    response = requests.get(
        f"{API_BASE}/api-key/self", headers=headers, timeout=15
    )
  except requests.RequestException as e:
    print(f"[LOGIN ERROR] Request failed: {e}")
    return None, (
        "Could not reach gaytor.rent. Check your internet connection and try"
        " again."
    )

  try:
    body = response.json()
  except ValueError:
    body = None
  if not isinstance(body, dict):
    body = {}

  data = body.get("data")
  if (
      response.status_code == 200
      and body.get("ok")
      and isinstance(data, dict)
      and data.get("via") == "apikey"
  ):
    print(f"[LOGIN] LOGIN SUCCESS (username: {data.get('username')})")
    return data, ""

  error = body.get("error")
  error_code = error.get("code") if isinstance(error, dict) else None
  print(
      f"[LOGIN ERROR] API key check failed with HTTP {response.status_code}"
      f" ({error_code or 'unexpected response'})"
  )
  if response.status_code in (200, 401, 403):
    return None, (
        "The key was not accepted. It may have been revoked, or not copied"
        " completely."
    )
  return None, (
      f"gaytor.rent answered with an error (HTTP {response.status_code})."
      " Please try again in a moment."
  )


def validate_api_key(api_key: str) -> dict | None:
  """Sends an HTTP GET request to the api-key/self endpoint.

  Returns the account data ({"username": ..., "key_label": ..., ...}) when the
  key is accepted, or None on any failure.
  """
  data, _ = _check_api_key(api_key)
  return data


def _prompt_for_api_key(notice: str = "", prefill: str | None = None) -> bool:
  """Shows the API key dialog until a working key is saved or the user cancels."""
  # Imported here so this module also works without a GUI (e.g. from scripts)
  from dialogs import ApiKeyDialog

  def verify(api_key: str) -> str | None:
    data, reason = _check_api_key(api_key)
    if not data:
      return reason
    if not save_api_key(api_key, data.get("username")):
      return "The key works, but it could not be saved in the system keyring."
    return None

  dialog = ApiKeyDialog(verify, notice=notice, prefill=prefill)
  return bool(dialog.exec())


def ensure_logged_in() -> bool:
  """Main entry point: Checks the stored API key without bothering the user.

  If there is no key, or the site no longer accepts it, a dialog asks for one.
  Returns False if the user cancels.
  """
  # Step 1: Retrieve the stored API key from keyring
  entry = _read_stored_entry()
  api_key = entry.get("api_key")
  notice = ""

  # Step 2: Check if a key exists and validate it via HTTP request
  if api_key:
    print("[LOGIN] API key found in Keyring")
    data, reason = _check_api_key(api_key)
    if data:
      username = data.get("username")

      # Step 3: Keep the stored username current (e.g. after a rename)
      if username and username != entry.get("username"):
        save_api_key(api_key, username)

      print(f"[LOGIN] API key is valid and ready to use! Username: {username}")
      return True
    notice = f"Your saved API key could not be verified. {reason}"

  # Step 4: If no key exists or validation failed, ask for one
  print("[LOGIN] No valid API key found. Asking for one...")
  if _prompt_for_api_key(notice, prefill=api_key):
    print("[LOGIN] API key saved to Keyring")
    return True
  print("[LOGIN ERROR] No API key was entered")
  return False


if __name__ == "__main__":
  # Allows testing login.py directly as a standalone script
  from PyQt6.QtWidgets import QApplication

  app = QApplication(sys.argv)
  success = ensure_logged_in()
  sys.exit(0 if success else 1)