import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

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

def fetch_full_report_suite(job_id, base_endpoint, title):
    """Helper to fetch the report, remediation, and runtime policy data."""
    if not job_id:
        msg = f"⚠️ Skipped {title}: No Job ID provided."
        print(msg)
        write_to_summary(f"### {title}\n{msg}")
        return

    headers = {"Authorization": f"Bearer {get_access_token()}", "Accept": "application/json"}
    base_url = f"{DATA_BASE_URL}{base_endpoint.replace(':job_id', job_id)}"
    
    write_to_summary(f"### {title}\n**Job ID:** `{job_id}`")

    # 1. Fetch the Scan Report
    print(f"\nFetching {title} (Report) using Job ID: {job_id}...")
    report_resp = requests.get(f"{base_url}/report", headers=headers)
    
    if report_resp.ok:
        print(f"✅ Successfully fetched {title} Report.")
        write_to_summary("#### 📊 Scan Report\n```json\n" + json.dumps(report_resp.json(), indent=2) + "\n```")
    else:
        print(f"❌ Failed to fetch {title} Report: {report_resp.status_code}")
        write_to_summary(f"#### ❌ Scan Report Failed\n**Status Code:** {report_resp.status_code}\n```json\n{report_resp.text}\n```")

    # 2. Fetch the Remediation Data
    print(f"Fetching {title} (Remediation) using Job ID: {job_id}...")
    rem_resp = requests.get(f"{base_url}/remediation", headers=headers)
    
    if rem_resp.ok:
        print(f"✅ Successfully fetched {title} Remediation.")
        write_to_summary("#### 🛠️ Remediation Guidelines\n```json\n" + json.dumps(rem_resp.json(), indent=2) + "\n```")
    else:
        print(f"❌ Failed to fetch {title} Remediation: {rem_resp.status_code}")
        write_to_summary(f"#### ❌ Remediation Failed\n**Status Code:** {rem_resp.status_code}\n```json\n{rem_resp.text}\n```")

    # 3. Fetch the Runtime Policy Config
    print(f"Fetching {title} (Runtime Policy) using Job ID: {job_id}...")
    policy_resp = requests.get(f"{base_url}/runtime-policy-config", headers=headers)
    
    if policy_resp.ok:
        print(f"✅ Successfully fetched {title} Runtime Policy.")
        write_to_summary("#### 🛡️ Runtime Security Profile\n```json\n" + json.dumps(policy_resp.json(), indent=2) + "\n```")
    else:
        print(f"❌ Failed to fetch {title} Runtime Policy: {policy_resp.status_code}")
        write_to_summary(f"#### ❌ Runtime Policy Failed\n**Status Code:** {policy_resp.status_code}\n```json\n{policy_resp.text}\n```")


def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        # Validate authentication works before proceeding
        get_access_token() 
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        print(error_msg)
        write_to_summary(f"## ❌ Prisma AIRS Reports Failed\n**Error:** {error_msg}")
        sys.exit(1)

    write_to_summary("## 🛡️ Prisma AIRS Security Reports Suite")

    # Fetch Attack Library Suite (Static)
    fetch_full_report_suite(ATTACK_JOB_ID, "/report/static/:job_id", "📚 Attack Library")

    # Fetch Agent Scan Suite (Dynamic)
    fetch_full_report_suite(AGENT_JOB_ID, "/report/dynamic/:job_id", "🔬 Agent Scan")

    print("\n✅ Script execution complete.")

if __name__ == "__main__":
    main()
