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
    
    # 2. Fetch the Profiling Data
    print("Fetching deep profiling data from API...\n")
    prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
    
    # Fallback: Sometimes APIs use /profile instead of /profiling for GET requests
    if prof_resp.status_code == 404:
        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profile", headers=headers)
        
    prof_data = prof_resp.json() if prof_resp.ok else {}

    # Determine Status
    profiling_status = prof_data.get("status") or target_data.get("profiling_status", "UNKNOWN")
    profiling_status = str(profiling_status).upper()

    print(f"Current Profiling Status: {profiling_status}")
    print("-" * 50)

    if profiling_status == "COMPLETED":
        print("✅ Profiling is complete! Here are the learned attributes based on the API Schema:\n")
        
        # Look for the dynamic fields in both possible API responses
        other_details = prof_data.get("other_details") or target_data.get("other_details") or {}
        ai_fields = prof_data.get("ai_generated_fields") or target_data.get("ai_generated_fields") or []
        background = prof_data.get("target_background") or target_data.get("target_background") or {}
        context = prof_data.get("additional_context") or target_data.get("additional_context") or {}

        # 1. Print the "System Capabilities" (other_details)
        if other_details:
            print("--- SYSTEM CAPABILITIES (other_details) ---")
            print(json.dumps(other_details, indent=2, ensure_ascii=False))
            print("\n")
        else:
            print("--- SYSTEM CAPABILITIES ---")
            print("No 'other_details' object found in the API response.\n")

        # 2. Print AI Generated Fields list
        if ai_fields:
            print("--- AI GENERATED FIELDS ---")
            print(json.dumps(ai_fields, indent=2))
            print("\n")

        # 3. Print the Standard Contexts
        print("--- TARGET CONTEXT & BACKGROUND ---")
        print(json.dumps({"target_background": background, "additional_context": context}, indent=2, ensure_ascii=False))
        
    elif profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"]:
        print("⏳ Profiling is still running. Please check back later.")
    else:
        print(f"⚠️ Profiling ended with status: {profiling_status}")

if __name__ == "__main__":
    main()
