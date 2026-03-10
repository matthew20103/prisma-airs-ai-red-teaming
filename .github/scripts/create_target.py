import os
import time
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

TARGET_NAME = os.environ.get("TARGET_NAME")
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT")
REQUEST_JSON = json.loads(os.environ.get("REQUEST_JSON"))
RESPONSE_JSON = json.loads(os.environ.get("RESPONSE_JSON"))

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}

    # 1. Check for Target
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == TARGET_NAME), None)

    target_payload = {
        "name": TARGET_NAME,
        "connection_params": {
            "api_endpoint": MODEL_ENDPOINT,
            "request_json": REQUEST_JSON,
            "response_json": RESPONSE_JSON
        }
    }

    # 2. Create or Update
    if target_id:
        print(f"Updating existing target: {TARGET_NAME} ({target_id})")
        resp = requests.put(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers, json=target_payload)
    else:
        print(f"Creating new target: {TARGET_NAME}")
        resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload)
        
    if not resp.ok:
        print(f"Target management failed: {resp.text}")
        sys.exit(1)
        
    target_id = target_id or resp.json().get("id")
    print(f"Target is ready! ID: {target_id}")

    # 3. Profiling
    print("Checking profiling status...")
    status = "IN_PROGRESS"
    while status in ["PENDING", "IN_PROGRESS", "RUNNING"]:
        time.sleep(10)
        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
        if prof_resp.ok:
            status = prof_resp.json().get("status", "COMPLETED").upper()
        else:
            status = "COMPLETED"
    print("Profiling complete. The target is ready for scanning!")

if __name__ == "__main__":
    main()
