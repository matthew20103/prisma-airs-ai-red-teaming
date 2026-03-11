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
        print(f"Warning: Failed to parse {var_name} as JSON. Error: {e}")
        return default

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
        
    target_name = os.environ.get("TARGET_NAME")

    if not target_name:
        print("Error: TARGET_NAME is required.")
        sys.exit(1)

    session_supported = os.environ.get("SESSION_SUPPORTED", "false").lower() == "true"
    
    # --- NEW: Extract the Response Key dynamically ---
    resp_json = parse_json_env("RESPONSE_JSON", {"reply": "{RESPONSE}"})
    # This grabs the first key from the dictionary (e.g., "output" from {"output": "{RESPONSE}"})
    response_key = next(iter(resp_json.keys()), "reply") if resp_json else "reply"

    # 1. Base Variables
    target_payload = {
        "name": target_name,
        "target_type": os.environ.get("TARGET_TYPE", "APPLICATION"),
        "connection_type": os.environ.get("CONNECTION_TYPE", "CUSTOM"),
        "response_mode": os.environ.get("RESPONSE_MODE", "REST"),
        "api_endpoint_type": os.environ.get("API_ENDPOINT_TYPE", "PUBLIC"),
        "session_supported": session_supported,
        "extra_info": {
            "response_key": response_key  # <-- INJECTED HERE
        },
        "connection_params": {
            "api_endpoint": os.environ.get("MODEL_ENDPOINT"),
            "request_json": parse_json_env("REQUEST_JSON", {"prompt": "{INPUT}"}),
            "response_json": resp_json,
            "response_key": response_key  # <-- AND INJECTED HERE
        }
    }

    # 2. String/Optional Fields
    description = os.environ.get("DESCRIPTION", "").strip()
    if description:
        target_payload["description"] = description

    nb_uuid = os.environ.get("NB_CHANNEL_UUID", "").strip()
    if nb_uuid and target_payload["api_endpoint_type"] == "NETWORK_BROKER":
        target_payload["network_broker_channel_uuid"] = nb_uuid

    req_headers = parse_json_env("REQUEST_HEADERS")
    if req_headers:
        target_payload["connection_params"]["request_headers"] = req_headers

    # 3. STRICT SCHEMA FIX: Only add multi_turn config if session_supported is True
    if session_supported:
        mt_config = parse_json_env("MULTI_TURN_CONFIG")
        if mt_config and "type" in mt_config:
            target_payload["multi_turn_config"] = mt_config

    # 4. STRICT SCHEMA FIX: Only add rate_limit integer if rate_limit_enabled is True
    rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "false").lower() == "true"
    target_payload["target_metadata"] = {
        "rate_limit_enabled": rate_limit_enabled
    }
    if rate_limit_enabled:
        target_rate_limit = os.environ.get("TARGET_RATE_LIMIT", "100").strip()
        target_payload["target_metadata"]["rate_limit"] = int(target_rate_limit) if target_rate_limit.isdigit() else 100

    # 5. Context blocks
    target_bg = parse_json_env("TARGET_BACKGROUND")
    if target_bg:
        target_payload["target_background"] = target_bg

    add_context = parse_json_env("ADDITIONAL_CONTEXT")
    if add_context:
        target_payload["additional_context"] = add_context

    # --- Target Management Execution ---
    print(f"Checking for existing target named '{target_name}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to fetch targets: {list_resp.text}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == target_name), None)

    # STRICT VALIDATION IS ON!
    query_params = {"validate": "true"}

    print("\n--- DEBUG: Smart Payload being sent to Prisma AIRS ---")
    print(json.dumps(target_payload, indent=2))
    print("------------------------------------------------------\n")

    if target_id:
        print(f"Updating existing target: {target_name} ({target_id})")
        resp = requests.put(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers, json=target_payload, params=query_params)
    else:
        print(f"Creating new target: {target_name}")
        resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload, params=query_params)
        
    if not resp.ok:
        print(f"Target management failed: {resp.text}")
        if "validation_error" in resp.text:
            print("\n[!] VALIDATION FAILED: Prisma AIRS rejected the payload or couldn't reach the endpoint.")
            print("[!] Check the DEBUG payload above to ensure your schema and authentication headers are correct.")
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
