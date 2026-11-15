"""One-request OpenAI Responses API connectivity probe.

Backend-only credentials. No provider bodies, prompts, generated replies,
keys, or exception text are written to logs. A --preflight call is offline;
the default invocation makes at most one explicitly authorized API request.
"""
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from server import MODEL_DEFAULT

EXPECTED = "BLACKWOLF_OPENAI_OK"
ENDPOINT = "https://api.openai.com/v1/responses"


def check_configuration(api_key, model, project_id):
    """Validate local shapes only; never claim that OpenAI accepted the key."""
    if not isinstance(api_key, str) or not api_key:
        return "key_missing"
    if (not api_key.startswith("sk-") or len(api_key) < 20
            or "..." in api_key
            or any(not (33 <= ord(char) <= 126) for char in api_key)):
        return "invalid_api_key_format"
    if not isinstance(model, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", model):
        return "invalid_model"
    if project_id is not None and project_id != "" and (
            not isinstance(project_id, str)
            or not re.fullmatch(r"proj_[A-Za-z0-9]+", project_id)):
        return "invalid_project_id"
    return None


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
        # HTTP status only; never expose response body, headers or exception text.
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
    combined = "\n".join(texts).strip()
    return combined == EXPECTED, (
        "verified" if combined == EXPECTED else "unexpected_output")


def main(argv=None):
    args = tuple(sys.argv[1:] if argv is None else argv)
    if args not in ((), ("--preflight",)):
        print("Usage: python -B verify_openai.py [--preflight]")
        return 2

    key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", MODEL_DEFAULT)
    project_id = os.environ.get("OPENAI_PROJECT_ID")
    error = check_configuration(key, model, project_id)
    if error:
        print(f"OpenAI configuration NOT VERIFIED: {error}. No credential was logged.")
        return 2

    if args == ("--preflight",):
        print("OpenAI local preflight PASSED; API key authenticity NOT VERIFIED.")
        return 0

    ok, reason = probe(key, model=model, project_id=project_id)
    if ok:
        print("OpenAI connection VERIFIED: one Responses API request returned the expected token.")
        return 0

    print(f"OpenAI connection NOT VERIFIED: {reason}. No secret or provider response was logged.")
    if reason == "http_401":
        print("Action: replace OPENAI_API_KEY in the openai-live-test environment "
              "with the full key from the selected project; do not use a tracking ID, "
              "owner ID, masked screenshot, or another project's key.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
