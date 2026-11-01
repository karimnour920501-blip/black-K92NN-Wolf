"""One-request OpenAI Responses API connectivity probe.

Reads OPENAI_API_KEY from the trusted backend environment. Does not print
credentials, provider error bodies, request prompts, or model-generated text.
No network call is made unless invoked explicitly.
"""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server import MODEL_DEFAULT

EXPECTED = "BLACKWOLF_OPENAI_OK"
ENDPOINT = "https://api.openai.com/v1/responses"


def probe(api_key, model=MODEL_DEFAULT, project_id=None, opener=urlopen):
    if not api_key or not isinstance(api_key, str):
        return False, "key_missing"
    if not isinstance(model, str) or not model or len(model) > 120:
        return False, "invalid_model"

    payload = {
        "model": model,
        "input": "Reply with exactly BLACKWOLF_OPENAI_OK and no other characters.",
        "reasoning": {"effort": "none"},
        "max_output_tokens": 64,
        "store": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if project_id:
        headers["OpenAI-Project"] = project_id

    request = Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"),
                      headers=headers, method="POST")
    try:
        with opener(request, timeout=30) as response:
            data = json.load(response)
    except HTTPError as exc:
        # Never expose provider response body or exception text to workflow logs.
        return False, f"http_{exc.code}"
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        return False, "transport_or_response_error"

    if not isinstance(data, dict):
        return False, "invalid_response"
    texts = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                value = part.get("text")
                if isinstance(value, str):
                    texts.append(value)
    return ("\n".join(texts).strip() == EXPECTED,
            "verified" if "\n".join(texts).strip() == EXPECTED else "unexpected_output")


def main():
    key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", MODEL_DEFAULT)
    project_id = os.environ.get("OPENAI_PROJECT_ID")
    if not key:
        print("OpenAI connection NOT VERIFIED: OPENAI_API_KEY is not configured.")
        return 2
    ok, reason = probe(key, model=model, project_id=project_id)
    if ok:
        print("OpenAI connection VERIFIED: one Responses API request returned the expected token.")
        return 0
    print(f"OpenAI connection NOT VERIFIED: {reason}. No secret or provider response was logged.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
