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
    """Safely parse JSON strings from GitHub Action environment variables."""
    val = os.environ.get(var_name, "").strip()
    if not val:
        return default
    try:
        return json.loads(val)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse {var_name} as JSON. Check your Action inputs. Error: {e}")
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

    # 1. Base Required Payload
    target_payload = {
        "name": target_name,
        "target_type": os.environ.get("TARGET_TYPE", "AGENT"),
        "connection_type": os.environ.get("CONNECTION_TYPE", "REST"),
        "api_endpoint_type": os.environ.get("API_ENDPOINT_TYPE", "PUBLIC"),
        "session_supported": os.environ.get("SESSION_SUPPORTED", "false").lower() == "true",
        "connection_params": {
            "api_endpoint": os.environ.get("MODEL_ENDPOINT"),
            "request_json": parse_json_env("REQUEST_JSON", {"prompt": "{INPUT}"}),
            "response_json": parse_json_env("RESPONSE_JSON", {"reply": "{RESPONSE}"})
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

    # 3. JSON Configuration Blocks
    mt_config = parse_json_env("MULTI_TURN_CONFIG")
    if mt_config and "type" in mt_config:
        target_payload["multi_turn_config"] = mt_config
    else:
        target_payload["multi_turn_config"] = None

    target_meta = parse_json_env("TARGET_METADATA")
    if target_meta:
        target_payload["target_metadata"] = target_meta

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

    # Validate flag ensures the Prisma AIRS API tests the connection
    query_params = {"validate": "true"}

    # ==========================================
    # DEBUG OUTPUT: Print the exact payload
    # ==========================================
    print("\n--- DEBUG: Payload being sent to Prisma AIRS ---")
    print(json.dumps(target_payload, indent=2))
    print("------------------------------------------------\n")

    if target_id:
        print(f"Updating existing target: {target_name} ({target_id})")
        resp = requests.put(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers, json=target_payload, params=query_params)
    else:
        print(f"Creating new target: {target_name}")
        resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload, params=query_params)
        
    if not resp.ok:
        print(f"Target management failed: {resp.text}")
        
        # Add a helpful hint to the logs if validation fails
        if "validation_error" in resp.text:
            print("\n[!] VALIDATION FAILED: Check the DEBUG payload printed above.")
            print("[!] 1. Does your `request_headers` JSON include the correct Authentication token for Deepseek?")
            print("[!] 2. Do your `request_json` and `response_json` schemas exactly match the Deepseek API docs?")
        
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
