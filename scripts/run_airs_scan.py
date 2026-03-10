import os
import time
import requests
import sys
import json

# Fetch credentials from GitHub Secrets
CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")
MODEL_ENDPOINT = os.environ.get("MODEL_ENDPOINT")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming"

def get_access_token():
    print("Generating OAuth 2.0 Access Token...")
    payload = {
        "grant_type": "client_credentials",
        "scope": f"tsg_id:{TSG_ID}"
    }
    
    # Palo Alto Networks requires Basic Auth for token generation
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    
    token = resp.json().get("access_token")
    return token

def main():
    print(f"Starting AI Red Teaming scan for target: {MODEL_ENDPOINT}")

    # 1. Authenticate
    access_token = get_access_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # 2. Create a Scan Target (Management Plane API)
    target_payload = {"endpoint": MODEL_ENDPOINT, "name": "CI-CD-Lab-Target"}
    target_resp = requests.post(f"{BASE_URL}/v1/target", headers=headers, json=target_payload)
    target_resp.raise_for_status()
    target_id = target_resp.json().get("id")

    # 3. Trigger the Scan (Data Plane API)
    scan_payload = {"target_id": target_id, "scan_type": "automated"}
    scan_resp = requests.post(f"{BASE_URL}/v1/scan", headers=headers, json=scan_payload)
    scan_resp.raise_for_status()
    job_id = scan_resp.json().get("job_id")
    print(f"Scan triggered successfully. Job ID: {job_id}")

    # 4. Poll for Scan Completion
    status = "PENDING"
    while status in ["PENDING", "IN_PROGRESS"]:
        time.sleep(15) 
        poll_resp = requests.get(f"{BASE_URL}/v1/scan/{job_id}", headers=headers)
        status = poll_resp.json().get("status")
        print(f"Current scan status: {status}")

    if status in ["FAILED", "ABORTED"]:
        print("Scan failed to complete.")
        sys.exit(1)

    # 5. Fetch the Report (Data Plane API)
    print("Scan completed. Fetching report...")
    report_resp = requests.get(f"{BASE_URL}/v1/report/dynamic/{job_id}/report", headers=headers)
    report_data = report_resp.json()

    with open("airs_report.json", "w") as f:
        json.dump(report_data, f, indent=4)

    # 6. Evaluate Results
    risk_score = report_data.get("risk_score", 0)
    print(f"Final Risk Score: {risk_score}")
    
    if risk_score > 70: 
        print("Critical vulnerabilities found! Failing the build.")
        sys.exit(1)
    else:
        print("Model passed AI Red Teaming checks.")

if __name__ == "__main__":
    main()
