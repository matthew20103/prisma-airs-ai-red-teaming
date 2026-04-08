import os
import requests
import sys
import json
from datetime import datetime, timezone, timedelta

# Environment Variables
CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")
TARGET_NAME = os.environ.get("TARGET_NAME")

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
    """Generates OAuth 2.0 Access Token."""
    payload = {"grant_type": "client_credentials", "scope": f"tsg_id:{TSG_ID}"}
    resp = requests.post(AUTH_URL, data=payload, auth=(CLIENT_ID, CLIENT_SECRET))
    resp.raise_for_status()
    return resp.json().get("access_token")

def format_timestamp(ts):
    """Converts unix timestamp to human-readable format in HKT (UTC+8)."""
    if not ts or ts == "N/A":
        return "N/A"
    try:
        ts_float = float(ts)
        # Handle microseconds
        if ts_float > 1e14:
            ts_float /= 1000000.0
        # Handle milliseconds
        elif ts_float > 1e11:
            ts_float /= 1000.0
            
        hkt_tz = timezone(timedelta(hours=8))
        return datetime.fromtimestamp(ts_float, tz=timezone.utc).astimezone(hkt_tz).strftime('%Y-%m-%d %H:%M:%S HKT')
    except (ValueError, TypeError):
        return str(ts)

def main():
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        write_to_summary(f"### ❌ Prisma AIRS Score Trend Failed\n**Error:** Failed to authenticate: {e}")
        sys.exit(1)

    # 1. Find Target ID from Target Name (Mgmt Plane)
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", []) if list_resp.ok else []
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        write_to_summary(f"### ❌ Prisma AIRS Score Trend Failed\n**Error:** Target '{TARGET_NAME}' not found.")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")

    # 2. Fetch Score Trend (Data Plane)
    params = {"target_id": target_id}
    trend_resp = requests.get(f"{DATA_BASE_URL}/dashboard/score_trend", headers=headers, params=params)
    
    if not trend_resp.ok:
        write_to_summary(f"### ❌ Prisma AIRS Score Trend Failed\n**Error:** Failed to fetch score trend: {trend_resp.text}")
        sys.exit(1)

    trend_json = trend_resp.json()
    
    # Safely extract data depending on how the API wraps the list
    data_points = trend_json.get("data", trend_json) if isinstance(trend_json, dict) else trend_json
    if not isinstance(data_points, list):
        data_points = []

    # --- Build Summary Output ---
    summary_output = [
        f"## 📈 Prisma AIRS Score Trend: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}`",
        ""
    ]

    if data_points:
        summary_output.append("### 📊 Trend Data")
        summary_output.append("| Date / Time (HKT) | Score |")
        summary_output.append("| :--- | :--- |")
        
        for point in data_points:
            # Flexible key extraction to accommodate common API structures
            raw_time = point.get("timestamp") or point.get("time") or point.get("date") or "N/A"
            score = point.get("score") or point.get("risk_score") or point.get("value", "N/A")
            
            human_time = format_timestamp(raw_time)
            summary_output.append(f"| {human_time} | **{score}** |")
    else:
        summary_output.append("*No score trend data available for this target yet.*")
    
    summary_output.append("")

    # --- Raw API Results (Collapsible) ---
    summary_output.append("### 📦 Raw API Results")
    summary_output.append("<details><summary><b>View Raw Score Trend JSON</b></summary>\n")
    summary_output.append("```json")
    summary_output.append(json.dumps(trend_json, indent=2, ensure_ascii=False))
    summary_output.append("```\n</details>\n")

    write_to_summary("\n".join(summary_output))
    print(f"Successfully fetched score trend for {TARGET_NAME}.")

if __name__ == "__main__":
    main()
