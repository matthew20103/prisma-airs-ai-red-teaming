import os
import time
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

# Required Variables
TARGET_NAME = os.environ.get("TARGET_NAME")
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT")
REQUEST_JSON = json.loads(os.environ.get("REQUEST_JSON", "{}"))
RESPONSE_JSON = json.loads(os.environ.get("RESPONSE_JSON", "{}"))

# Optional Variables
DESCRIPTION = os.environ.get("DESCRIPTION", "").strip()
TARGET_TYPE = os.environ.get("TARGET_TYPE", "").strip()
CONNECTION_TYPE = os.environ.get("CONNECTION_TYPE", "").strip()
API_ENDPOINT_TYPE = os.environ.get("API_ENDPOINT_TYPE", "").strip()

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}

    # 1. Build the dynamic payload
    target_payload = {
        "name": TARGET_NAME,
        "connection_params": {
            "api_endpoint": MODEL_ENDPOINT,
            "request_json": REQUEST_JSON,
            "response_json": RESPONSE_JSON,
            # Adding standard headers required by many AI apps
            "request_headers": {
                "Content-Type": "application/json"
            }
        }
    }

    # Inject optional fields only if they were provided in the GitHub Action UI
    if DESCRIPTION:
        target_payload["description"] = DESCRIPTION
    if TARGET_TYPE:
        target_payload["target_type"] = TARGET_TYPE
    if CONNECTION_TYPE:
        target_payload["connection_type"] = CONNECTION_TYPE
    if API_ENDPOINT_TYPE:
        target_payload["api_endpoint_type"] = API_ENDPOINT_TYPE

    # 2. Check for existing Target
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == TARGET_NAME), None)

    # Adding the validate query parameter as shown in the API doc screenshot
    query_params = {"validate": "true"}

    # 3. Create or Update
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

    # 4. Profiling Check
    print("Triggering and checking profiling status...")
    # Attempt to trigger profiling, but gracefully ignore if it says Access Denied / already running
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
