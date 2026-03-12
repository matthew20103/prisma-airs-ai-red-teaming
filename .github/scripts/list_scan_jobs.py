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
DATA_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/data-plane/v1"

def write_to_summary(markdown_text):
    """Appends Markdown content to the GitHub Actions Job Summary."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(markdown_text + "\n")

def get_access_token():
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Accept": "application/json"}
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Job List Failed\n**Error:** {error_msg}")
        sys.exit(1)

    # 1. Resolve Target ID using the Management Plane
    print(f"Searching for target: '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        error_msg = f"Failed to list targets: {list_resp.text}"
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Job List Failed\n**Error:** {error_msg}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        error_msg = f"Error: Could not find a target named '{TARGET_NAME}'."
        print(error_msg)
        write_to_summary(f"### ❌ Target Not Found\n**Error:** {error_msg}")
        sys.exit(1)

    target_id = target_obj.get("target_id") or target_obj.get("uuid") or target_obj.get("id")
    print(f"✅ Found Target! ID: {target_id}")

    # --- Initialize GitHub Job Summary Output ---
    summary_output = [
        f"## 📋 Prisma AIRS Scan Jobs: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}`",
        ""
    ]

    # 2. Fetch the Scan Jobs from the Data Plane
    scan_endpoint = f"{DATA_BASE_URL}/scan"
    print(f"\nFetching scan jobs from {scan_endpoint}...")
    
    scans_resp = requests.get(scan_endpoint, headers=headers)

    if scans_resp.ok:
        # Extract the list of scans (handling both wrapped and direct array responses)
        raw_scans_data = scans_resp.json()
        all_scans = raw_scans_data.get("data", []) if isinstance(raw_scans_data, dict) else raw_scans_data
        
        # Filter scans to only include those matching our specific target_id
        target_scans = [s for s in all_scans if s.get("target_id") == target_id]

        if not target_scans:
            print(f"No scan jobs found for target {TARGET_NAME}.")
            summary_output.append("⚠️ *No scan jobs found for this target.*")
        else:
            print(f"Found {len(target_scans)} jobs for this target. Building summary table...")
            
            # Build a Markdown Table for the GitHub Summary
            summary_output.append("| Scan / Job ID | Type | Status | Date |")
            summary_output.append("|---|---|---|---|")
            
            for scan in target_scans:
                # Map fields dynamically based on common Prisma AIRS JSON structures
                s_id = scan.get("job_id") or scan.get("scan_id") or scan.get("id") or scan.get("uuid") or "N/A"
                s_type = scan.get("scan_type") or scan.get("type") or "Unknown"
                s_status = scan.get("status") or scan.get("state") or "Unknown"
                s_date = scan.get("created_at") or scan.get("start_time") or scan.get("timestamp") or "N/A"
                
                # Add status emojis for visual flair
                status_icon = "🟢" if "COMPLETED" in str(s_status).upper() else ("⏳" if "RUNNING" in str(s_status).upper() else "🔴")
                
                summary_output.append(f"| `{s_id}` | {s_type} | {status_icon} {s_status} | {s_date} |")
                print(f" - [{s_status}] {s_type}: {s_id}")

            # Also output raw JSON for deep debugging
            summary_output.append("\n<details><summary><b>Show Raw JSON Output</b></summary>\n")
            summary_output.append("```json\n" + json.dumps(target_scans, indent=2) + "\n```\n</details>")

    else:
        error_msg = f"Failed to fetch scan jobs: {scans_resp.status_code} - {scans_resp.text}"
        print(f"⚠️ {error_msg}")
        summary_output.append(f"### ❌ Scan Fetch Failed\n**Error:** {error_msg}")

    # Write the compiled summary out to GitHub Actions
    write_to_summary("\n".join(summary_output))
    print("\n✅ Scan list processed and written to GitHub Job Summary.")

if __name__ == "__main__":
    main()
