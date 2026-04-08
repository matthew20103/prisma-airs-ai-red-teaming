import os
import requests
import sys
import json

# Environment Variables
CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")
TARGET_NAME = os.environ.get("TARGET_NAME")
DATE_RANGE = os.environ.get("DATE_RANGE", "ALL")

# API Endpoints
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
    """Generates OAuth 2.0 Access Token (This must be a POST request)."""
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def fetch_data_plane_api(endpoint, headers, params):
    """Helper to fetch Data Plane APIs and handle errors gracefully."""
    resp = requests.get(endpoint, headers=headers, params=params)
    if not resp.ok:
        err_summary = (
            f"### ❌ Prisma AIRS Data Fetch Failed\n"
            f"**HTTP {resp.status_code}**\n\n"
            f"**URL Attempted:** `{resp.url}`\n"
            f"**Raw Error Response:**\n```json\n{resp.text}\n```"
        )
        write_to_summary(err_summary)
        print(f"ERROR: HTTP {resp.status_code} for {resp.url}")
        print(f"Response: {resp.text}")
        sys.exit(1)
    return resp.json()

def main():
    try:
        headers = {
            "Authorization": f"Bearer {get_access_token()}", 
            "Content-Type": "application/json",
            "prisma-tenant": TSG_ID
        }
    except Exception as e:
        write_to_summary(f"### ❌ Prisma AIRS Dashboard Failed\n**Error:** Failed to authenticate: {e}")
        sys.exit(1)

    # 1. Find Target ID from Target Name (Mgmt Plane)
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", []) if list_resp.ok else []
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        write_to_summary(f"### ❌ Prisma AIRS Dashboard Failed\n**Error:** Target '{TARGET_NAME}' not found.")
        print(f"Error: Target '{TARGET_NAME}' not found.")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")

    # Base parameters for Data Plane APIs
    params = {
        "target_id": target_id,
        "date_range": DATE_RANGE
    }

    # 2. Fetch Scan Statistics & Risk Profile
    stats_json = fetch_data_plane_api(f"{DATA_BASE_URL}/dashboard/scan-statistics", headers, params)
    
    # 3. Fetch Score Trend
    trend_json = fetch_data_plane_api(f"{DATA_BASE_URL}/dashboard/score-trend", headers, params)
    
    # --- Data Extraction ---
    # Stats
    total_scans = stats_json.get("total_scans", 0)
    scan_status_list = stats_json.get("scan_status", [])
    risk_profile_list = stats_json.get("risk_profile", [])
    
    # Trend
    labels = trend_json.get("labels", [])
    series = trend_json.get("series", [])

    # --- Build Summary Output ---
    summary_output = [
        f"## 📊 Prisma AIRS Target Dashboard: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}` &nbsp;&nbsp;|&nbsp;&nbsp; **Date Range:** `{DATE_RANGE}`",
        ""
    ]

    # --- Section A: Overview & Risk Profile ---
    summary_output.append("### 🛡️ Scan Statistics & Risk Profile")
    summary_output.append(f"**Total Scans in Period:** `{total_scans}`\n")
    
    summary_output.append("<table style='width:100%; border:none;'><tr><td valign='top' style='width:50%;'>")
    
    # Scan Status Mini-Table
    summary_output.append("**Scan Status Breakdown**")
    summary_output.append("| Status | Count |")
    summary_output.append("| :--- | :--- |")
    if scan_status_list:
        for status in scan_status_list:
            lbl = status.get("label", "Unknown")
            val = status.get("value", 0)
            summary_output.append(f"| {lbl} | **{val}** |")
    else:
        summary_output.append("| N/A | 0 |")

    summary_output.append("</td><td valign='top' style='width:50%;'>")

    # Risk Profile Mini-Table
    summary_output.append("**Risk Profile Breakdown**")
    summary_output.append("| Risk Level | Count |")
    summary_output.append("| :--- | :--- |")
    if risk_profile_list:
        for risk in risk_profile_list:
            lbl = risk.get("label", "Unknown")
            val = risk.get("value", 0)
            summary_output.append(f"| {lbl} | **{val}** |")
    else:
        summary_output.append("| N/A | 0 |")

    summary_output.append("</td></tr></table>\n")

    # --- Section B: Score Trend Data ---
    summary_output.append("### 📈 Score Trend Data")
    if labels and series:
        table_lines = [
            "| Date | Type | Risk Score |",
            "| :--- | :--- | :--- |"
        ]
        
        has_data = False
        for i, date_label in enumerate(labels):
            for s in series:
                job_type = s.get("label", "Unknown")
                data_array = s.get("data", [])
                
                # Retrieve the score for this specific date and job type
                val = data_array[i] if i < len(data_array) else None
                
                # Only add rows to the table if a score exists (ignores null days)
                if val is not None:
                    table_lines.append(f"| {date_label} | {job_type} | **{val}** |")
                    has_data = True
        
        if has_data:
            summary_output.extend(table_lines)
        else:
            summary_output.append("*No completed scans with risk scores found for this date range.*")
    else:
        summary_output.append("*No score trend data available for this target in the selected date range.*")
    
    summary_output.append("")

    # --- Section C: Raw API Results (Collapsible) ---
    summary_output.append("### 📦 Raw API Results")
    
    summary_output.append("<details><summary><b>View Raw Scan Statistics JSON</b></summary>\n")
    summary_output.append("```json\n" + json.dumps(stats_json, indent=2, ensure_ascii=False) + "\n```\n</details>")

    summary_output.append("<details><summary><b>View Raw Score Trend JSON</b></summary>\n")
    summary_output.append("```json\n" + json.dumps(trend_json, indent=2, ensure_ascii=False) + "\n```\n</details>\n")

    write_to_summary("\n".join(summary_output))
    print(f"Successfully fetched dashboard data for {TARGET_NAME} (Range: {DATE_RANGE}).")

if __name__ == "__main__":
    main()
