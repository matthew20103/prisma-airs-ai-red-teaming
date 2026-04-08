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

def main():
    try:
        headers = {
            "Authorization": f"Bearer {get_access_token()}", 
            "Content-Type": "application/json",
            "prisma-tenant": TSG_ID
        }
    except Exception as e:
        write_to_summary(f"### ❌ Prisma AIRS Score Trend Failed\n**Error:** Failed to authenticate: {e}")
        sys.exit(1)

    # 1. Find Target ID from Target Name (Mgmt Plane)
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", []) if list_resp.ok else []
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        write_to_summary(f"### ❌ Prisma AIRS Score Trend Failed\n**Error:** Target '{TARGET_NAME}' not found.")
        print(f"Error: Target '{TARGET_NAME}' not found.")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")

    # 2. Fetch Score Trend (Data Plane)
    params = {
        "target_id": target_id,
        "date_range": DATE_RANGE
    }

    trend_resp = requests.get(f"{DATA_BASE_URL}/dashboard/score-trend", headers=headers, params=params)
    
    if not trend_resp.ok:
        err_summary = (
            f"### ❌ Prisma AIRS Score Trend Failed\n"
            f"**HTTP {trend_resp.status_code}**\n\n"
            f"**URL Attempted:** `{trend_resp.url}`\n"
            f"**Raw Error Response:**\n```json\n{trend_resp.text}\n```"
        )
        write_to_summary(err_summary)
        print(f"ERROR: HTTP {trend_resp.status_code}")
        print(f"URL: {trend_resp.url}")
        print(f"Response: {trend_resp.text}")
        sys.exit(1)

    trend_json = trend_resp.json()
    labels = trend_json.get("labels", [])
    series = trend_json.get("series", [])

    # --- Build Summary Output ---
    summary_output = [
        f"## 📈 Prisma AIRS Score Trend: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}` &nbsp;&nbsp;|&nbsp;&nbsp; **Date Range:** `{DATE_RANGE}`",
        ""
    ]

    # Generate the 3-column table
    if labels and series:
        table_lines = [
            "### 📊 Trend Data",
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

    # --- Raw API Results (Collapsible) ---
    summary_output.append("### 📦 Raw API Results")
    summary_output.append("<details><summary><b>View Raw Score Trend JSON</b></summary>\n")
    summary_output.append("```json")
    summary_output.append(json.dumps(trend_json, indent=2, ensure_ascii=False))
    summary_output.append("```\n</details>\n")

    write_to_summary("\n".join(summary_output))
    print(f"Successfully fetched score trend for {TARGET_NAME} (Range: {DATE_RANGE}).")

if __name__ == "__main__":
    main()
