import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

# We now need the specific Job IDs from the previous scan steps
ATTACK_JOB_ID = os.environ.get("ATTACK_JOB_ID")
AGENT_JOB_ID = os.environ.get("AGENT_JOB_ID")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
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

def fetch_report(job_id, endpoint_path, report_title):
    """Helper function to fetch a report and append it to the summary."""
    if not job_id:
        msg = f"⚠️ Skipped {report_title}: No Job ID provided."
        print(msg)
        write_to_summary(f"### {report_title}\n{msg}")
        return

    print(f"\nFetching {report_title} using Job ID: {job_id}...")
    headers = {"Authorization": f"Bearer {get_access_token()}", "Accept": "application/json"}
    url = f"{DATA_BASE_URL}{endpoint_path.replace(':job_id', job_id)}"
    
    resp = requests.get(url, headers=headers)
    
    if resp.ok:
        report_data = resp.json()
        print(f"✅ Successfully fetched {report_title}.")
        write_to_summary(f"### ✅ {report_title}\n**Job ID:** `{job_id}`")
        write_to_summary("```json\n" + json.dumps(report_data, indent=2) + "\n```")
    else:
        print(f"❌ Failed to fetch {report_title}: {resp.status_code} - {resp.text}")
        write_to_summary(f"### ❌ {report_title} Failed\n**Job ID:** `{job_id}`\n**Status Code:** {resp.status_code}\n```json\n{resp.text}\n```")

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        # Just validating authentication works before proceeding
        get_access_token() 
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        print(error_msg)
        write_to_summary(f"## ❌ Prisma AIRS Reports Failed\n**Error:** {error_msg}")
        sys.exit(1)

    write_to_summary("## 🛡️ Prisma AIRS Security Reports")

    # 1. Fetch Attack Library Report (Static)
    # Using the exact endpoint path you provided
    fetch_report(ATTACK_JOB_ID, "/report/static/:job_id/report", "📚 Attack Library Report")

    # 2. Fetch Agent Scan Report
    # NOTE: You will need to verify the exact path for the agent scan in your API docs
    # I am using "/report/dynamic/:job_id/report" as an educated placeholder
    fetch_report(AGENT_JOB_ID, "/report/dynamic/:job_id/report", "🔬 Agent Scan Report")

    print("\n✅ Script execution complete.")

if __name__ == "__main__":
    main()
