import os
import requests
import sys
import json
from datetime import datetime

# Environment Variables
CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")
TARGET_NAME = os.environ.get("TARGET_NAME")

# API Endpoints
AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

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

def format_val(v):
    """Formats values for Markdown tables, escaping newlines and pipes."""
    if isinstance(v, list):
        return ", ".join([str(x).replace("\n", " ").replace("|", "\\|") for x in v]) if v else "None"
    if isinstance(v, dict):
        return json.dumps(v).replace("\n", " ").replace("|", "\\|")
    if v is not None and str(v).strip() != "":
        # Replace newlines with HTML breaks to keep table intact
        return str(v).replace("\n", "<br>").replace("|", "\\|")
    return "N/A"

def format_timestamp(ts):
    """Converts unix timestamp to human-readable format, handling seconds, ms, and μs."""
    if not ts or ts == "N/A":
        return "N/A"
    try:
        ts_float = float(ts)
        # Handle microseconds (16+ digits)
        if ts_float > 1e14:
            ts_float /= 1000000.0
        # Handle milliseconds (13 digits)
        elif ts_float > 1e11:
            ts_float /= 1000.0
            
        return datetime.utcfromtimestamp(ts_float).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError, TypeError):
        # If it is already a string or format is unknown, return as-is
        return str(ts)

def main():
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        write_to_summary(f"### ❌ Prisma AIRS Profiling Failed\n**Error:** {e}")
        sys.exit(1)

    # Find Target
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    existing_targets = list_resp.json().get("data", []) if list_resp.ok else []
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        write_to_summary(f"### ❌ Prisma AIRS Profiling Failed\n**Error:** Target '{TARGET_NAME}' not found.")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")
    
    # Fetch Version & format timestamp
    raw_version = target_obj.get("version") or target_obj.get("target_version") or "N/A"
    target_version = format_timestamp(raw_version)

    # Fetch Data
    details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
    target_data = details_resp.json() if details_resp.ok else {}
    
    prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
    if prof_resp.status_code == 404:
        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profile", headers=headers)
    prof_data = prof_resp.json() if prof_resp.ok else {}

    # Extract Status
    profiling_status = str(prof_data.get("status") or target_data.get("profiling_status", "UNKNOWN")).upper()
    status_emoji = "✅" if profiling_status == "COMPLETED" else "⏳" if profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"] else "⚠️"
    
    # Extract Sections
    other_details = prof_data.get("other_details") or target_data.get("other_details") or {}
    background = prof_data.get("target_background") or target_data.get("target_background") or {}
    context = prof_data.get("additional_context") or target_data.get("additional_context") or {}

    # AI Generated Fields Extraction
    ai_fields = prof_data.get("ai_generated_fields", []) or target_data.get("ai_generated_fields", [])
    if not isinstance(ai_fields, list):
        ai_fields = []
        
    def is_ai(key):
        return "🤖 Yes" if key in ai_fields else "No"

    # Field Extraction 
    industry = background.get("industry")
    use_cases = background.get("use_case")
    competitors = background.get("competitors")
    
    # Check context first, fallback to other_details if necessary
    base_model = context.get("base_model") or other_details.get("base_model")
    core_architecture = context.get("core_architecture") or other_details.get("core_architecture")
    system_prompt = context.get("system_prompt") or other_details.get("system_prompt")
    languages = context.get("languages_supported")
    banned_keywords = context.get("banned_keywords")
    tools = context.get("tools_accessible")

    # Keys to exclude from the "Other Details" loop so they don't duplicate
    extracted_keys = ['base_model', 'core_architecture', 'system_prompt']

    # --- Build Summary Output ---
    summary_output = [
        f"## 🔍 Prisma AIRS Profiling Report: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}` &nbsp;&nbsp;|&nbsp;&nbsp; **Target Version:** `{target_version}`",
        ""
    ]

    # --- 1. Target Background Table ---
    summary_output.append("### 📊 Target Background")
    summary_output.append("| Metric | Value | AI Generated |")
    summary_output.append("| :--- | :--- | :--- |")
    summary_output.append(f"| **Profiling Status** | {status_emoji} {profiling_status} | {is_ai('status')} |")
    summary_output.append(f"| **Industry** | {format_val(industry)} | {is_ai('industry')} |")
    summary_output.append(f"| **Use Cases** | {format_val(use_cases)} | {is_ai('use_case')} |")
    summary_output.append(f"| **Known Competitors** | {format_val(competitors)} | {is_ai('competitors')} |")
    summary_output.append("")

    # --- 2. Additional Context Table ---
    summary_output.append("### ⚙️ Additional Context")
    summary_output.append("| Metric | Value | AI Generated |")
    summary_output.append("| :--- | :--- | :--- |")
    summary_output.append(f"| **Base Model** | {format_val(base_model)} | {is_ai('base_model')} |")
    summary_output.append(f"| **Core Architecture** | {format_val(core_architecture)} | {is_ai('core_architecture')} |")
    summary_output.append(f"| **System Prompt** | {format_val(system_prompt)} | {is_ai('system_prompt')} |")
    summary_output.append(f"| **Languages Supported** | {format_val(languages)} | {is_ai('languages_supported')} |")
    summary_output.append(f"| **Banned Keywords** | {format_val(banned_keywords)} | {is_ai('banned_keywords')} |")
    summary_output.append(f"| **Tools Accessible** | {format_val(tools)} | {is_ai('tools_accessible')} |")
    summary_output.append("")

    # --- 3. Other Details Table ---
    summary_output.append("### 📂 Other Details")
    # Check if there are keys in other_details beyond the ones we already extracted manually
    if other_details and any(k not in extracted_keys for k in other_details.keys()):
        summary_output.append("| Key | Value | AI Generated |")
        summary_output.append("| :--- | :--- | :--- |")
        for k, v in other_details.items():
            if k in extracted_keys:
                continue
            summary_output.append(f"| **{k}** | {format_val(v)} | {is_ai(k)} |")
    else:
        summary_output.append("*No additional 'other_details' found.*")
    summary_output.append("")

    # --- 4. Raw API Results (Collapsibles) ---
    summary_output.append("### 📦 Raw API Results")
    
    def add_collapsible_json(title, data):
        summary_output.append(f"<details><summary><b>{title}</b></summary>\n")
        summary_output.append("```json")
        summary_output.append(json.dumps(data, indent=2, ensure_ascii=False))
        summary_output.append("```\n</details>\n")

    add_collapsible_json("Raw Target Background", background)
    add_collapsible_json("Raw Additional Context", context)
    add_collapsible_json("Raw Other Details", other_details)
    add_collapsible_json("Raw AI Generated Fields", ai_fields)
    summary_output.append("")

    # Console output for logs
    print(f"Current Profiling Status: {profiling_status}")

    write_to_summary("\n".join(summary_output))

if __name__ == "__main__":
    main()
