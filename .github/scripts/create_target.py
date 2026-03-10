import os
import time
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

# Root Variables
TARGET_NAME = os.environ.get("TARGET_NAME")
DESCRIPTION = os.environ.get("DESCRIPTION", "").strip()
TARGET_TYPE = os.environ.get("TARGET_TYPE", "").strip()
CONNECTION_TYPE = os.environ.get("CONNECTION_TYPE", "").strip()
API_ENDPOINT_TYPE = os.environ.get("API_ENDPOINT_TYPE", "").strip()

# Connection Params Variables
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT")
REQUEST_JSON = json.loads(os.environ.get("REQUEST_JSON", "{}"))
RESPONSE_JSON = json.loads(os.environ.get("RESPONSE_JSON", "{}"))
REQUEST_HEADERS = json.loads(os.environ.get("REQUEST_HEADERS", '{"Content-Type": "application/json"}'))
RESPONSE_KEY = os.environ.get("RESPONSE_KEY", "").strip()

# Multi-Turn Config Variables
MULTI_TURN_TYPE = os.environ.get("MULTI_TURN_TYPE", "none").strip()
MULTI_TURN_REQ_ID = os.environ.get("MULTI_TURN_REQ_ID", "").strip()
MULTI_TURN_RESP_ID = os.environ.get("MULTI_TURN_RESP_ID", "").strip()

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}

    # 1. Build the Connection Params
    connection_params = {
        "api_endpoint": MODEL_ENDPOINT,
        "request_json": REQUEST_JSON,
        "response_json": RESPONSE_JSON,
        "request_headers": REQUEST_HEADERS
    }

    if RESPONSE_KEY:
        connection_params["response_key"] = RESPONSE_KEY

    # Build multi-turn config if the user selected stateful or stateless
    if MULTI_TURN_TYPE in ["stateful", "stateless"]:
        connection_params["multi_turn_config"] = {
            "type": MULTI_TURN_TYPE,
            "request_id_field": MULTI_TURN_REQ_ID,
            "response_id_field": MULTI_TURN_RESP_ID
        }

    # 2. Build the Root Payload
    target_payload = {
        "name": TARGET_NAME,
        "connection_params": connection_params
    }

    if DESCRIPTION: target_payload["description"] = DESCRIPTION
    if TARGET_TYPE: target_payload["target_type"] = TARGET_TYPE
    if CONNECTION_TYPE: target_payload["connection_type"] = CONNECTION_TYPE
    if API_ENDPOINT_TYPE: target_payload["api_endpoint_type"] = API_ENDPOINT_TYPE

    # 3. Check for existing Target
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == TARGET_NAME), None)

    query_params = {"validate": "true"}

    # 4. Create or Update
    if target_id:
        print(f"Updating existing target: {TARGET_NAME} ({target_id})")
        resp = requests.put(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers, json=target_payload, params=query_params)
    else:
        print(f"Creating new target: {TARGET_NAME}")
        resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload, params=query_params)
        
    if not resp.ok:
        print(f"Target management failed: {resp.text}")
        sys.exit(1)
        
    target_id = target_id or resp.json().get("id")
    print(f"Target is ready! ID: {target_id}")

    # 5. Profiling Check
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
            print(f"Profiling check returned: {prof_resp.status_code}. Assuming complete or unavailable.")
            status = "COMPLETED"
            
    print("Target setup and profiling phase completed!")

if __name__ == "__main__":
    main()
