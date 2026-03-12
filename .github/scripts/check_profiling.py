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
        write_to_summary(f"### ❌ Prisma AIRS Profiling Failed\n**Error:** {error_msg}")
        sys.exit(1)

    print(f"Searching for target: '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        error_msg = f"Failed to list targets: {list_resp.text}"
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Profiling Failed\n**Error:** {error_msg}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        error_msg = f"Error: Could not find a target named '{TARGET_NAME}'."
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Profiling Failed\n**Error:** {error_msg}")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")
    print(f"Found Target! ID: {target_id}")

    details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
    target_data = details_resp.json() if details_resp.ok else {}
    
    print("Fetching deep profiling data from API...\n")
    prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
    
    if prof_resp.status_code == 404:
        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profile", headers=headers)
        
    prof_data = prof_resp.json() if prof_resp.ok else {}

    profiling_status = str(prof_data.get("status") or target_data.get("profiling_status", "UNKNOWN")).upper()

    # --- Prepare Markdown Summary ---
    summary_output = [
        f"## 🔍 Prisma AIRS Profiling Report: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}`",
        ""
    ]

    # Status Emoji mapping
    status_emoji = "✅" if profiling_status == "COMPLETED" else "⏳" if profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"] else "⚠️"

    # --- 1. Summary Table Section ---
    other_details = prof_data.get("other_details") or target_data.get("other_details") or {}
    ai_fields = prof_data.get("ai_generated_fields") or target_data.get("ai_generated_fields") or []
    
    summary_output.append("### 📊 Workflow Execution Summary")
    summary_output.append("| Metric | Value |")
    summary_output.append("| :--- | :--- |")
    summary_output.append(f"| **Status** | {status_emoji} {profiling_status} |")
    summary_output.append(f"| **System Capabilities Found** | {len(other_details)} |")
    summary_output.append(f"| **AI Generated Fields** | {len(ai_fields)} |")
    summary_output.append(f"| **Target Name** | `{TARGET_NAME}` |")
    summary_output.append("")

    # --- 2. Detailed Breakdown ---
    if profiling_status == "COMPLETED":
        summary_output.append("### 🛠️ Detailed Profiling Attributes")
        
        # System Capabilities
        summary_output.append("#### ⚙️ System Capabilities")
        if other_details:
            summary_output.append("```json\n" + json.dumps(other_details, indent=2, ensure_ascii=False) + "\n```")
        else:
            summary_output.append("*No capabilities found.*")

        # AI Fields
        if ai_fields:
            summary_output.append("#### 🧠 AI Generated Fields")
            summary_output.append("```json\n" + json.dumps(ai_fields, indent=2) + "\n```")

    elif profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"]:
        summary_output.append("> ⏳ **Notice:** Profiling is currently in progress. Detailed attributes will be available once the scan completes.")
    else:
        summary_output.append(f"> ⚠️ **Warning:** Profiling ended with an unexpected status: {profiling_status}")

    # Write to GitHub
    write_to_summary("\n".join(summary_output))

if __name__ == "__main__":
    main()
