import os
import time
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

TARGET_NAME = os.environ.get("TARGET_NAME")
SCAN_TYPE = os.environ.get("SCAN_TYPE")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"
DATA_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/data-plane/v1"

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    return resp.json().get("access_token")

def main():
    headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}

    # 1. Lookup Target ID by Name
    print(f"Looking up target ID for '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_id:
        print(f"Error: Could not find a target named {TARGET_NAME}. Run the Create Target workflow first.")
        sys.exit(1)

    # 2. Trigger Scan
    print(f"Triggering {SCAN_TYPE} scan...")
    # NOTE: If this throws a validation error, you may need to add "categories" to this payload based on the API docs!
    scan_payload = {"target_id": target_id, "scan_type": SCAN_TYPE}
    scan_resp = requests.post(f"{DATA_BASE_URL}/scan", headers=headers, json=scan_payload)
    
    if not scan_resp.ok:
        print(f"Scan trigger failed: {scan_resp.text}")
        sys.exit(1)
        
    job_id = scan_resp.json().get("job_id")
    print(f"Scan started! Job ID: {job_id}")

    # 3. Poll for Completion
    status = "PENDING"
    while status in ["PENDING", "IN_PROGRESS", "RUNNING"]:
        time.sleep(15)
        poll_resp = requests.get(f"{DATA_BASE_URL}/scan/{job_id}", headers=headers)
        status = poll_resp.json().get("status", "").upper()
        print(f"Scan Status: {status}")

    if status in ["FAILED", "ABORTED"]:
        print("Scan failed to complete.")
        sys.exit(1)

    # 4. Download Report
    print("Downloading report...")
    report_resp = requests.get(f"{DATA_BASE_URL}/report/dynamic/{job_id}/report", headers=headers)
    with open("scan_report.json", "w") as f:
        json.dump(report_resp.json(), f, indent=4)
        
    risk_score = report_resp.json().get("risk_score", 0)
    print(f"Final Risk Score: {risk_score}")
    
    if risk_score > 70:
        print("CRITICAL RISK. Failing build.")
        sys.exit(1)

if __name__ == "__main__":
    main()
