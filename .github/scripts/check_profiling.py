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
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    print(f"Searching for target: '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to list targets: {list_resp.text}")
        sys.exit(1)

    # Find target by name
    existing_targets = list_resp.json().get("data", [])
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        print(f"Error: Could not find a target named '{TARGET_NAME}'.")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")
    print(f"Found Target! ID: {target_id}")

    # 1. Fetch deep dive details (Base configuration)
    details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
    target_data = details_resp.json() if details_resp.ok else {}
    
    # 2. Fetch the dedicated Profiling Data
    print("Fetching deep profiling data...\n")
    prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
    prof_data = prof_resp.json() if prof_resp.ok else {}

    # Check status from either endpoint
    profiling_status = prof_data.get("status") or target_data.get("profiling_status", "UNKNOWN")
    profiling_status = profiling_status.upper()

    print(f"Current Profiling Status: {profiling_status}")
    print("-" * 50)

    if profiling_status == "COMPLETED":
        print("✅ Profiling is complete! Here is the FULL, unfiltered profiling data:\n")
        
        # Print the rich profiling data (System Capabilities, etc.)
        if prof_data:
            print("--- DEDICATED PROFILING RESULTS ---")
            print(json.dumps(prof_data, indent=2))
            print("\n")
            
        # Print the base contexts in case anything lives there
        print("--- TARGET CONTEXT & BACKGROUND ---")
        context_data = {
            "target_background": target_data.get("target_background", {}),
            "additional_context": target_data.get("additional_context", {})
        }
        print(json.dumps(context_data, indent=2))
        
    elif profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"]:
        print("⏳ Profiling is still running. Please check back later.")
    else:
        print(f"⚠️ Profiling ended with status: {profiling_status}")

if __name__ == "__main__":
    main()
