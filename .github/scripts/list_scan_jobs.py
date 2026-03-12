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
# Depending on the API, jobs might be on the data plane instead. 
# DATA_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/data-plane/v1"

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
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Job List Failed\n**Error:** {error_msg}")
        sys.exit(1)

    # 1. Resolve Target ID
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

    # 2. Fetch the Scan Jobs
    # NOTE: Adjust this endpoint according to your API reference. 
    # It might be /job?target_id={target_id} or on the data-plane instead.
    jobs_endpoint = f"{MGMT_BASE_URL}/target/{target_id}/job" 
    print(f"\nFetching scan jobs from {jobs_endpoint}...")
    
    jobs_resp = requests.get(jobs_endpoint, headers=headers)

    if jobs_resp.ok:
        jobs_data = jobs_resp.json().get("data", [])
        
        # Fallback if the API returns a direct list instead of wrapping in "data"
        if not isinstance(jobs_data, list):
            jobs_data = jobs_resp.json() if isinstance(jobs_resp.json(), list) else [jobs_resp.json()]

        if not jobs_data:
            print("No jobs found for this target.")
            summary_output.append("⚠️ *No scan jobs found for this target.*")
        else:
            print(f"Found {len(jobs_data)} jobs. Building summary table...")
            
            # Build a Markdown Table for the GitHub Summary
            summary_output.append("| Job ID | Type / Category | Status | Date Created |")
            summary_output.append("|---|---|---|---|")
            
            for job in jobs_data:
                j_id = job.get("job_id") or job.get("uuid") or job.get("id") or "N/A"
                j_type = job.get("job_type") or job.get("type") or job.get("category") or "Unknown"
                j_status = job.get("status") or job.get("state") or "Unknown"
                j_date = job.get("created_at") or job.get("timestamp") or "N/A"
                
                # Add status emojis for visual flair
                status_icon = "🟢" if "COMPLETED" in str(j_status).upper() else ("⏳" if "RUNNING" in str(j_status).upper() else "🔴")
                
                summary_output.append(f"| `{j_id}` | {j_type} | {status_icon} {j_status} | {j_date} |")
                print(f" - [{j_status}] {j_type}: {j_id}")

            # Also output raw JSON for deep debugging
            summary_output.append("\n<details><summary><b>Show Raw JSON Output</b></summary>\n")
            summary_output.append("```json\n" + json.dumps(jobs_data, indent=2) + "\n```\n</details>")

    else:
        error_msg = f"Failed to fetch scan jobs: {jobs_resp.status_code} - {jobs_resp.text}"
        print(f"⚠️ {error_msg}")
        summary_output.append(f"### ❌ Job Fetch Failed\n**Error:** {error_msg}")

    # Write the compiled summary out to GitHub Actions
    write_to_summary("\n".join(summary_output))
    print("\n✅ Job list processed and written to GitHub Job Summary.")

if __name__ == "__main__":
    main()
