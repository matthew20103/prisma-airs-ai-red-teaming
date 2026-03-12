import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

TARGET_NAME = os.environ.get("TARGET_NAME")
TARGET_URL = os.environ.get("TARGET_URL")
AUTH_HEADER = os.environ.get("AUTH_HEADER", "") # Optional authentication for the target

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

def write_summary(markdown_text):
    """Writes output directly to the GitHub Actions Summary UI page."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write(markdown_text + "\n")

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {
            "Authorization": f"Bearer {get_access_token()}", 
            "Content-Type": "application/json"
        }
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # --- 1. Check if Target Already Exists ---
    print(f"Checking if target '{TARGET_NAME}' already exists...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to list targets: {list_resp.text}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if target_obj:
        target_id = target_obj.get("uuid") or target_obj.get("id")
        print(f"✅ Target '{TARGET_NAME}' already exists! ID: {target_id}")
        
        # Write Summary for Existing Target
        write_summary(f"## 🎯 Prisma AIRS Target Discovered")
        write_summary(f"**Status:** `Already Exists` (No new target created)")
        write_summary(f"**Target Name:** `{TARGET_NAME}`")
        write_summary(f"**Target ID:** `{target_id}`")
        sys.exit(0)

    # --- 2. Create New Target ---
    print(f"Creating new target '{TARGET_NAME}'...")
    
    # Build the target payload
    target_payload = {
        "name": TARGET_NAME,
        "endpoint": TARGET_URL,
        "method": "POST"
    }
    
    # Inject optional auth headers if the app team provided them
    if AUTH_HEADER:
        target_payload["headers"] = {"Authorization": AUTH_HEADER}

    create_resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload)

    if not create_resp.ok:
        print(f"Failed to create target: {create_resp.text}")
        sys.exit(1)

    new_target_data = create_resp.json()
    new_target_id = new_target_data.get("uuid") or new_target_data.get("id", "UNKNOWN")
    print(f"✅ Successfully created target! ID: {new_target_id}")

    # --- 3. Write Beautiful Summary to GitHub UI ---
    write_summary(f"## 🎯 Prisma AIRS Target Created")
    write_summary(f"**Status:** `Successfully Registered` ✅")
    write_summary(f"**Target Name:** `{TARGET_NAME}`")
    write_summary(f"**Endpoint URL:** `{TARGET_URL}`")
    write_summary(f"**Target ID:** `{new_target_id}`")
    write_summary(f"\n*This AI agent is now registered in Prisma AIRS and is ready for Automated Red Team Profiling and Scanning!*")

if __name__ == "__main__":
    main()
