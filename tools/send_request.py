from langchain_core.tools import tool
from shared_store import BASE64_STORE, url_time
import time
import os
import requests
import json
from collections import defaultdict
from typing import Any, Dict, Optional

cache = defaultdict(int)
retry_limit = 4


@tool
def post_request(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Any:
    """
    FIXED VERSION —
    Sends a POST request with the correct schema required by the quiz evaluator.

    Automatically injects:
        - email
        - secret
        - correct submit URL

    Prevents:
        - missing `secret`
        - missing `url`
        - empty payload due to LLM mistakes
        - incorrect answer stripping
    """

    # Load environment secrets every call (safe for tools)
    from dotenv import load_dotenv
    load_dotenv()

    EMAIL = os.getenv("EMAIL")
    SECRET = os.getenv("SECRET")

    # Handle base64 lookup (unchanged)
    ans = payload.get("answer")
    if isinstance(ans, str) and ans.startswith("BASE64_KEY:"):
        key = ans.split(":", 1)[1]
        payload["answer"] = BASE64_STORE[key]

    # -------------------------
    # PAYLOAD FIX STARTS HERE
    # -------------------------

    # Ensure submit URL is NEVER empty
    submit_url = payload.get("url") or url

    corrected_payload = {
        "answer": payload.get("answer"),
        "email": EMAIL,
        "secret": SECRET,
        "url": submit_url
    }

    # -------------------------
    # DEBUG PRINT
    # -------------------------
    print("\n=== SENDING CORRECTED PAYLOAD ===")
    print(json.dumps(corrected_payload, indent=4))
    print(f"→ POST to: {url}")

    headers = headers or {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=corrected_payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        print("\n=== RESPONSE RECEIVED ===")
        print(json.dumps(data, indent=4), "\n")

        # Track timing for retries
        cur_url = os.getenv("url")
        delay = time.time() - url_time.get(cur_url, time.time())
        print(f"Delay: {delay}")

        next_url = data.get("url")

        # If no next URL → finished step
        if not next_url:
            return {"status": "completed"}

        # Register time for next URL
        url_time[next_url] = time.time()
        os.environ["url"] = next_url

        # Reset offset
        os.environ["offset"] = "0"

        return data

    except requests.HTTPError as e:
        print("\n=== HTTP ERROR ===")
        try:
            print(e.response.json())
            return e.response.json()
        except:
            print(str(e))
            return {"error": str(e)}

    except Exception as e:
        print("\n=== UNEXPECTED ERROR ===")
        print(str(e))
        return {"error": str(e)}
