import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")
TARGET_NAME = os.environ.get("TARGET_NAME")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    print(f"Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # 1. List targets
    print(f"Searching for target: '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to list targets: {list_resp.text}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    
    # 2. Find the target object by name
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        print(f"Error: Could not find a target named '{TARGET_NAME}'.")
        print("Available targets are:")
        for t in existing_targets:
            print(f" - {t.get('name')}")
        sys.exit(1)

    print("\n✅ Found the target in the list! Here is the raw configuration data:")
    print("--------------------------------------------------")
    print(json.dumps(target_obj, indent=2))
    print("--------------------------------------------------")

    # 3. Try to get deep-dive details (checking common ID fields)
    target_id = target_obj.get("target_id") or target_obj.get("uuid") or target_obj.get("id")

    if target_id:
        print(f"\nFetching deep-dive details using ID: {target_id}...\n")
        details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
        
        if details_resp.ok:
            print("==================================================")
            print(f" FULL DEEP-DIVE CONFIGURATION FOR: {TARGET_NAME}")
            print("==================================================")
            print(json.dumps(details_resp.json(), indent=2))
            print("==================================================")
        else:
            print(f"Failed to fetch details: {details_resp.text}")
    else:
        print("\n⚠️ Warning: Could not find an ID field to fetch deeper details, but the list data above should have what we need!")

if __name__ == "__main__":
    main()
