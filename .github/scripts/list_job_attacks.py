import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

JOB_ID = os.environ.get("JOB_ID")
SCAN_TYPE = os.environ.get("SCAN_TYPE")

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

def escape_md(text):
    if not text:
        return "N/A"
    return str(text).replace('\n', '<br>').replace('\r', '').replace('|', '&#124;')

def main():
    if not JOB_ID or not SCAN_TYPE:
        write_to_summary("## ❌ Error\nMissing Job ID or Scan Type.")
        sys.exit(1)

    print("Generating OAuth 2.0 Access Token...")
    try:
        access_token = get_access_token() 
    except Exception as e:
        write_to_summary(f"## ❌ Prisma AIRS Auth Failed\n**Error:** {e}")
        sys.exit(1)

    write_to_summary(f"## 📋 List of Attacks for Job\n**Job ID:** `{JOB_ID}` | **Scan Type:** `{SCAN_TYPE}`\n")

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    
    # Using the exact endpoint from the official documentation, adding limit=100
    endpoint = f"/report/{SCAN_TYPE}/{JOB_ID}/list-attacks?limit=100"
    url = f"{DATA_BASE_URL}{endpoint}"
    
    print(f"Fetching attacks from {url} ...")
    response = requests.get(url, headers=headers)
    
    if not response.ok:
        print(f"❌ Failed to fetch attacks: {response.status_code}")
        write_to_summary(f"#### ❌ API Request Failed\n**Status Code:** {response.status_code}\n```json\n{response.text}\n```")
        sys.exit(1)

    data = response.json()
    
    # Handle the array whether it's wrapped in a "data" key or returned directly
    attacks_list = data.get("data", []) if isinstance(data, dict) else data

    if not attacks_list:
        write_to_summary("✅ **No attacks found** for this scan job.")
        sys.exit(0)

    # Build a Markdown Table
    table_md = [
        "| Attack ID (Copy this!) | Category / Sub-Category | Severity | Status | Multi-Turn |",
        "|------------------------|-------------------------|----------|--------|------------|"
    ]
    
    for attack in attacks_list:
        # Extract the ID
        attack_id = attack.get("id", attack.get("attack_id", attack.get("uuid", "UNKNOWN_ID")))
        
        # Extract naming
        category = attack.get("category", attack.get("sub_category", "Unknown Category"))
        
        # Extract severity
        severity = attack.get("severity", "Unknown")

        # Status
        is_successful = attack.get("successful", False)
        status = "❌ Bypassed" if is_successful else "✅ Blocked"
        
        # Multi-turn check
        is_multi_turn = attack.get("multi_turn", False)
        multi_turn_status = "Yes" if is_multi_turn else "No"

        table_md.append(f"| `{(attack_id)}` | {escape_md(category)} | {escape_md(severity)} | {status} | {multi_turn_status} |")

    write_to_summary("\n".join(table_md) + "\n")

    # Add Raw JSON section just in case
    write_to_summary(
        "<details>\n"
        "<summary>🔍 View Raw JSON Response</summary>\n\n"
        "```json\n" + json.dumps(data, indent=2) + "\n```\n\n"
        "</details>\n"
    )

    print("✅ Successfully generated attack list table.")

if __name__ == "__main__":
    main()
