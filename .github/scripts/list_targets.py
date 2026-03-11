import os
import requests
import sys

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

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    print("Fetching all registered targets...\n")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to list targets: {list_resp.text}")
        sys.exit(1)

    targets = list_resp.json().get("data", [])
    
    if not targets:
        print("No targets found in this TSG.")
        sys.exit(0)

    # --- Print the Table Header ---
    print(f"{'NAME':<35} | {'STATUS':<10} | {'VALIDATED':<10} | {'TYPE':<15} | {'UUID'}")
    print("-" * 115)
    
    # --- Loop through and print each target ---
    for t in targets:
        # Truncate names longer than 34 chars to keep the table clean
        name = t.get("name", "Unknown")[:34]
        status = t.get("status", "N/A")
        validated = str(t.get("validated", "False"))
        t_type = t.get("target_type", "N/A")
        uuid = t.get("uuid") or t.get("id") or "N/A"
        
        print(f"{name:<35} | {status:<10} | {validated:<10} | {t_type:<15} | {uuid}")

    print("-" * 115)
    print(f"Total Targets: {len(targets)}")

if __name__ == "__main__":
    main()
