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

    # Fetch Data
    details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
    target_data = details_resp.json() if details_resp.ok else {}
    
    prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)
    if prof_resp.status_code == 404:
        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profile", headers=headers)
    prof_data = prof_resp.json() if prof_resp.ok else {}

    # Extract Fields
    profiling_status = str(prof_data.get("status") or target_data.get("profiling_status", "UNKNOWN")).upper()
    other_details = prof_data.get("other_details") or target_data.get("other_details") or {}
    ai_fields = prof_data.get("ai_generated_fields") or target_data.get("ai_generated_fields") or []
    background = prof_data.get("target_background") or target_data.get("target_background") or {}
    context = prof_data.get("additional_context") or target_data.get("additional_context") or {}

    # --- Build Summary Output ---
    summary_output = [
        f"## 🔍 Prisma AIRS Profiling Report: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}`",
        ""
    ]

    # Status Row
    status_emoji = "✅" if profiling_status == "COMPLETED" else "⏳" if profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"] else "⚠️"
    summary_output.append(f"### Status: {status_emoji} {profiling_status}")
    summary_output.append("The profiling process has successfully mapped the following attributes:\n")

    # --- 1. NEW: Target Profiling Summary Table ---
    summary_output.append("### 📊 Target Profiling Summary")
    summary_output.append("| Metric | Value |")
    summary_output.append("| :--- | :--- |")
    summary_output.append(f"| **Status** | {status_emoji} {profiling_status} |")
    summary_output.append(f"| **System Capabilities Found** | {len(other_details)} |")
    summary_output.append(f"| **AI Generated Fields** | {len(ai_fields)} |")
    summary_output.append(f"| **Target Name** | `{TARGET_NAME}` |")
    summary_output.append("")

    # --- 2. System Capabilities Section ---
    summary_output.append("### ⚙️ System Capabilities")
    if other_details:
        summary_output.append("```json\n" + json.dumps(other_details, indent=2, ensure_ascii=False) + "\n```")
    else:
        summary_output.append("*No 'other_details' object found.*")
    summary_output.append("")

    # --- 3. Restored: Target Context & Background Section ---
    summary_output.append("### 📂 Target Context & Background")
    context_json = json.dumps({"target_background": background, "additional_context": context}, indent=2, ensure_ascii=False)
    summary_output.append("```json\n" + context_json + "\n```")

    # --- 4. Raw API Response (Dropdown) ---
    summary_output.append("---")
    summary_output.append("### 📄 Raw API Response Output")
    summary_output.append("<details><summary>Click to view full JSON</summary>")
    summary_output.append("\n```json\n" + json.dumps(prof_data, indent=2, ensure_ascii=False) + "\n```\n")
    summary_output.append("</details>")

    # Console output (as requested)
    print(f"Current Profiling Status: {profiling_status}")
    print(context_json)

    write_to_summary("\n".join(summary_output))

if __name__ == "__main__":
    main()
