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

def find_keys(obj, target_key, results=None):
    """Recursively search for all values associated with a specific key in a JSON object."""
    if results is None:
        results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == target_key:
                results.append(v)
            else:
                find_keys(v, target_key, results)
    elif isinstance(obj, list):
        for item in obj:
            find_keys(item, target_key, results)
    return results

def escape_md_table(text):
    """Escapes characters that would break a Markdown table cell."""
    if isinstance(text, (dict, list)):
        text = json.dumps(text)
    return str(text).replace('\n', '<br>').replace('\r', '').replace('|', '&#124;')

def fetch_full_report_suite(job_id, base_endpoint, title, scan_type):
    """Helper to fetch the report, remediation, runtime policy, or goals data."""
    if not job_id:
        msg = f"⚠️ Skipped {title}: No Job ID provided."
        print(msg)
        write_to_summary(f"### {title}\n{msg}")
        return

    headers = {"Authorization": f"Bearer {get_access_token()}", "Accept": "application/json"}
    base_url = f"{DATA_BASE_URL}{base_endpoint.replace(':job_id', job_id)}"
    
    write_to_summary(f"### {title}\n**Job ID:** `{job_id}`\n")

    report_data, rem_data, policy_data, goals_data = None, None, None, None

    # 1. Fetch the Scan Report (Done for both)
    print(f"\nFetching {title} (Report) using Job ID: {job_id}...")
    report_resp = requests.get(f"{base_url}/report", headers=headers)
    if report_resp.ok:
        print(f"✅ Successfully fetched {title} Report.")
        report_data = report_resp.json()
    else:
        print(f"❌ Failed to fetch {title} Report: {report_resp.status_code}")
        write_to_summary(f"#### ❌ Scan Report Failed\n**Status Code:** {report_resp.status_code}\n```json\n{report_resp.text}\n```")

    # 2. Fetch the Remediation Data (Done for both so raw JSON is available)
    print(f"Fetching {title} (Remediation) using Job ID: {job_id}...")
    rem_resp = requests.get(f"{base_url}/remediation", headers=headers)
    if rem_resp.ok:
        print(f"✅ Successfully fetched {title} Remediation.")
        rem_data = rem_resp.json()
    else:
        print(f"❌ Failed to fetch {title} Remediation: {rem_resp.status_code}")
        # Only log error to console to keep summary clean if endpoint isn't supported for dynamic
        print(f"Response: {rem_resp.text}")

    # 3. Fetch the Runtime Policy Config (Done for both so raw JSON is available)
    print(f"Fetching {title} (Runtime Policy) using Job ID: {job_id}...")
    policy_resp = requests.get(f"{base_url}/runtime-policy-config", headers=headers)
    if policy_resp.ok:
        print(f"✅ Successfully fetched {title} Runtime Policy.")
        policy_data = policy_resp.json()
    else:
        print(f"❌ Failed to fetch {title} Runtime Policy: {policy_resp.status_code}")
        print(f"Response: {policy_resp.text}")
            
    # 4. Fetch Agent Scan Goals List (Only for dynamic)
    if scan_type == "dynamic":
        print(f"Fetching {title} (Goals List) using Job ID: {job_id}...")
        # FIXED: Updated endpoint to /list-goals
        list_resp = requests.get(f"{base_url}/list-goals", headers=headers)
        if list_resp.ok:
            print(f"✅ Successfully fetched {title} Goals List.")
            goals_data = list_resp.json()
        else:
            print(f"❌ Failed to fetch {title} Goals: {list_resp.status_code}")
            write_to_summary(f"#### ❌ Goals List Failed\n**Status Code:** {list_resp.status_code}\n```json\n{list_resp.text}\n```")


    # --- RENDER VISUALIZATIONS ---

    if report_data:
        # Pie Chart Generation
        severity_report = report_data.get("severity_report", {})
        if severity_report:
            severity_stats = severity_report.get("stats", [])
            total_successful = severity_report.get("successful", 0)
            
            if severity_stats:
                mermaid_chart = [
                    "#### 🎯 Successful Attacks by Severity",
                    f"**Total Successful Attacks:** {total_successful}\n",
                    "```mermaid",
                    "pie title Severity of Successful Attacks"
                ]
                
                for stat in severity_stats:
                    severity = stat.get("severity", "UNKNOWN")
                    successful_count = stat.get("successful", 0)
                    if successful_count > 0:
                        mermaid_chart.append(f'    "{severity} ({successful_count})" : {successful_count}')
                
                mermaid_chart.append("```\n")
                write_to_summary("\n".join(mermaid_chart))

        # Successful Attacks Distribution Table
        all_sub_categories = []
        for report_key in ["security_report", "safety_report", "brand_report", "compliance_report"]:
            rep = report_data.get(report_key)
            if rep and isinstance(rep, dict):
                sub_cats = rep.get("sub_categories", [])
                if sub_cats:
                    for sc in sub_cats:
                        name = sc.get("display_name", "Unknown")
                        successful = sc.get("successful", 0)
                        all_sub_categories.append({"name": name, "successful": successful})
        
        sorted_sub_categories = sorted(all_sub_categories, key=lambda x: x["successful"], reverse=True)
        if sorted_sub_categories:
            table_md = [
                "#### 📊 Successful Attacks Distribution",
                "| Attack Category | Total Successful |",
                "|-----------------|------------------|"
            ]
            for item in sorted_sub_categories:
                table_md.append(f"| {item['name']} | {item['successful']} |")
            
            table_md.append("\n")
            write_to_summary("\n".join(table_md))

    # --- DYNAMIC TABLES BASED ON SCAN TYPE ---

    if scan_type == "static" and (rem_data or policy_data):
        mitigation_table = [
            "#### 🛡️ Recommendation to Mitigate Risks",
            "| Mitigation Type | Details |",
            "|-----------------|---------|"
        ]

        policy_ids = []
        if policy_data:
            for p in find_keys(policy_data, "policy_id"):
                if str(p) not in policy_ids:
                    policy_ids.append(str(p))
        
        policy_str = "<br>".join([f"<code>{escape_md_table(p)}</code>" for p in policy_ids]) if policy_ids else "None found"
        mitigation_table.append(f"| **Prisma AIRS AI Runtime Security** | {policy_str} |")

        remediations = []
        if rem_data:
            for r in find_keys(rem_data, "remediation"):
                safe_r = escape_md_table(r)
                if safe_r not in remediations:
                    remediations.append(safe_r)
        
        rem_str = "<br>".join([f"<code>{r}</code>" for r in remediations]) if remediations else "None found"
        mitigation_table.append(f"| **Other Remediation Guidelines** | {rem_str} |")
        
        write_to_summary("\n".join(mitigation_table) + "\n\n")

    elif scan_type == "dynamic" and goals_data:
        goals_list = goals_data.get("data", [])
        if goals_list:
            goals_table = [
                "#### 📋 Agent Scan Goals",
                "| Scan Goal | Status |",
                "|-----------|--------|"
            ]
            
            for goal in goals_list:
                goal_name = goal.get("goal", goal.get("name", goal.get("goal_type", "Unknown Goal")))
                goal_status = str(goal.get("status", goal.get("successful", "Unknown"))).upper()
                
                if goal_status in ["SUCCESS", "PASSED", "TRUE", "COMPLETED"]:
                    goal_status = f"✅ {goal_status}"
                elif goal_status in ["FAILED", "FALSE", "ERROR"]:
                    goal_status = f"❌ {goal_status}"
                elif goal_status in ["PENDING", "IN_PROGRESS"]:
                    goal_status = f"⏳ {goal_status}"
                    
                goals_table.append(f"| {escape_md_table(goal_name)} | {goal_status} |")
                
            write_to_summary("\n".join(goals_table) + "\n\n")


    # --- COLLAPSIBLE RAW JSON SECTIONS ---
    # FIXED: Re-enabled raw outputs for both static and dynamic scans

    if report_data:
        write_to_summary(
            "<details>\n"
            "<summary>📊 View Raw Scan Report</summary>\n\n"
            "```json\n" + json.dumps(report_data, indent=2) + "\n```\n\n"
            "</details>\n"
        )
    if rem_data:
        write_to_summary(
            "<details>\n"
            "<summary>🛠️ View Remediation Guidelines</summary>\n\n"
            "```json\n" + json.dumps(rem_data, indent=2) + "\n```\n\n"
            "</details>\n"
        )
    if policy_data:
        write_to_summary(
            "<details>\n"
            "<summary>🛡️ View Runtime Security Profile</summary>\n\n"
            "```json\n" + json.dumps(policy_data, indent=2) + "\n```\n\n"
            "</details>\n"
        )
    if scan_type == "dynamic" and goals_data:
        write_to_summary(
            "<details>\n"
            "<summary>📋 View Raw Scan Goals</summary>\n\n"
            "```json\n" + json.dumps(goals_data, indent=2) + "\n```\n\n"
            "</details>\n"
        )

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
    fetch_full_report_suite(ATTACK_JOB_ID, "/report/static/:job_id", "📚 Attack Library", "static")

    # Fetch Agent Scan Suite (Dynamic)
    fetch_full_report_suite(AGENT_JOB_ID, "/report/dynamic/:job_id", "🔬 Agent Scan", "dynamic")

    print("\n✅ Script execution complete.")

if __name__ == "__main__":
    main()
