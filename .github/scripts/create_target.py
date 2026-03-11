import os
import time
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def parse_json_env(var_name, default=None):
    val = os.environ.get(var_name, "").strip()
    if not val:
        return default
    try:
        return json.loads(val)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse {var_name} as JSON. Check your Action inputs. Error: {e}")
        return default

def parse_comma_list(var_name):
    """Parses a comma-separated environment variable into a Python list of strings."""
    val = os.environ.get(var_name, "").strip()
    if not val:
        return []
    return [item.strip() for item in val.split(",") if item.strip()]

def main():
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    target_name = os.environ.get("TARGET_NAME")

    # 1. Base Required Payload
    target_payload = {
        "name": target_name,
        "target_type": os.environ.get("TARGET_TYPE", "AGENT"),
        "connection_type": os.environ.get("CONNECTION_TYPE", "REST"),
        "api_endpoint_type": os.environ.get("API_ENDPOINT_TYPE", "PUBLIC"),
        "session_supported": os.environ.get("SESSION_SUPPORTED", "false").lower() == "true",
        "connection_params": {
            "api_endpoint": os.environ.get("MODEL_ENDPOINT"),
            "request_json": parse_json_env("REQUEST_JSON", {}),
            "response_json": parse_json_env("RESPONSE_JSON", {})
        }
    }

    # 2. String/Optional Fields
    description = os.environ.get("DESCRIPTION", "").strip()
    if description:
        target_payload["description"] = description

    nb_uuid = os.environ.get("NB_CHANNEL_UUID", "").strip()
    if nb_uuid:
        target_payload["network_broker_channel_uuid"] = nb_uuid

    req_headers = parse_json_env("REQUEST_HEADERS")
    if req_headers:
        target_payload["connection_params"]["request_headers"] = req_headers

    # 3. Multi-Turn Logic
    mt_enabled = os.environ.get("MT_ENABLED", "false").lower() == "true"
    if mt_enabled:
        target_payload["multi_turn_config"] = {
            "type": os.environ.get("MT_TYPE", "stateful"),
            "response_id_field": os.environ.get("MT_RESPONSE_ID_FIELD", "id").strip(),
            "request_id_field": os.environ.get("MT_REQUEST_ID_FIELD", "previous_response_id").strip()
        }

    # 4. Target Metadata (Rate Limiting)
    rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "false").lower() == "true"
    target_rate_limit = os.environ.get("TARGET_RATE_LIMIT", "100").strip()
    
    target_payload["target_metadata"] = {
        "rate_limit_enabled": rate_limit_enabled,
        "rate_limit": int(target_rate_limit) if target_rate_limit.isdigit() else 100
    }

    # 5. Target Background
    bg_industry = os.environ.get("BG_INDUSTRY", "").strip()
    bg_use_case = os.environ.get("BG_USE_CASE", "").strip()
    bg_competitors = parse_comma_list("BG_COMPETITORS")
    
    if bg_industry or bg_use_case or bg_competitors:
        target_payload["target_background"] = {}
        if bg_industry: target_payload["target_background"]["industry"] = bg_industry
        if bg_use_case: target_payload["target_background"]["use_case"] = bg_use_case
        if bg_competitors: target_payload["target_background"]["competitors"] = bg_competitors

    # 6. Additional Context
    ctx_base_model = os.environ.get("CTX_BASE_MODEL", "").strip()
    ctx_core_arch = os.environ.get("CTX_CORE_ARCHITECTURE", "").strip()
    ctx_sys_prompt = os.environ.get("CTX_SYSTEM_PROMPT", "").strip()
    ctx_langs = parse_comma_list("CTX_LANGUAGES_SUPPORTED")
    ctx_banned = parse_comma_list("CTX_BANNED_KEYWORDS")
    ctx_tools = parse_comma_list("CTX_TOOLS_ACCESSIBLE")

    if any([ctx_base_model, ctx_core_arch, ctx_sys_prompt, ctx_langs, ctx_banned, ctx_tools]):
        target_payload["additional_context"] = {}
        if ctx_base_model: target_payload["additional_context"]["base_model"] = ctx_base_model
        if ctx_core_arch: target_payload["additional_context"]["core_architecture"] = ctx_core_arch
        if ctx_sys_prompt: target_payload["additional_context"]["system_prompt"] = ctx_sys_prompt
        if ctx_langs: target_payload["additional_context"]["languages_supported"] = ctx_langs
        if ctx_banned: target_payload["additional_context"]["banned_keywords"] = ctx_banned
        if ctx_tools: target_payload["additional_context"]["tools_accessible"] = ctx_tools

    # --- Target Management Execution ---
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == target_name), None)

    query_params = {"validate": "true"}

    if target_id:
        print(f"Updating existing target: {target_name} ({target_id})")
        resp = requests.put(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers, json=target_payload, params=query_params)
    else:
        print(f"Creating new target: {target_name}")
        resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload, params=query_params)
        
    if not resp.ok:
        print(f"Target management failed: {resp.text}")
        sys.exit(1)
        
    target_id = target_id or resp.json().get("id")
    print(f"Target is ready! ID: {target_id}")

    # --- Profiling Check ---
    print("Triggering and checking profiling status...")
    probe_resp = requests.post(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
    if not probe_resp.ok:
        print(f"Note on profiling trigger: {probe_resp.text}")

    status = "IN_PROGRESS"
    while status in ["PENDING", "IN_PROGRESS", "RUNNING"]:
        time.sleep(10)
        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
        if prof_resp.ok:
            status = prof_resp.json().get("status", "COMPLETED").upper()
        else:
            status = "COMPLETED"
            
    print("Target setup and profiling phase completed!")

if __name__ == "__main__":
    main()
