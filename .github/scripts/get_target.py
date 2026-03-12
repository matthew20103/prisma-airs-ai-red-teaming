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
        write_to_summary(f"### ❌ Prisma AIRS Target Check Failed\n**Error:** {error_msg}")
        sys.exit(1)

    # 1. List targets
    print(f"Searching for target: '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        error_msg = f"Failed to list targets: {list_resp.text}"
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Target Check Failed\n**Error:** {error_msg}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    
    # 2. Find the target object by name
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        print(f"Error: Could not find a target named '{TARGET_NAME}'.")
        available_list = [f"* {t.get('name')}" for t in existing_targets]
        summary_error = [
            f"### ❌ Target Not Found: `{TARGET_NAME}`",
            "**Available targets are:**",
            "\n".join(available_list)
        ]
        write_to_summary("\n".join(summary_error))
        sys.exit(1)

    # Prepare data for the table
    uuid = target_obj.get("uuid") or "N/A"
    status = target_obj.get("status") or "UNKNOWN"
    t_type = target_obj.get("target_type") or "N/A"
    endpoint_type = target_obj.get("api_endpoint_type") or "N/A"
    created_at = target_obj.get("created_at") or "N/A"
    
    # Choose a status icon
    status_icon = "🟢" if status.upper() == "ACTIVE" else "🟡"

    raw_config_json = json.dumps(target_obj, indent=2)

    # --- Initialize GitHub Job Summary Output ---
    summary_output = [
        f"## 🎯 Prisma AIRS Target Details: `{TARGET_NAME}`",
        "### ✅ Target Found",
        "#### 📊 Target Overview",
        "| Property | Value |",
        "| :--- | :--- |",
        f"| **UUID** | `{uuid}` |",
        f"| **Status** | {status_icon} {status} |",
        f"| **Target Type** | {t_type} |",
        f"| **Endpoint Type** | {endpoint_type} |",
        f"| **Created At** | {created_at} |",
        "",
        "#### 📄 Raw Configuration Data",
        "<details><summary>Click to expand raw JSON</summary>",
        "",
        "```json\n" + raw_config_json + "\n```",
        "</details>",
        ""
    ]

    # 3. Try to get deep-dive details
    target_id = target_obj.get("target_id") or target_obj.get("uuid") or target_obj.get("id")

    if target_id:
        print(f"\nFetching deep-dive details using ID: {target_id}...\n")
        details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
        
        if details_resp.ok:
            deep_dive_json = json.dumps(details_resp.json(), indent=2)
            summary_output.append("#### 🔎 Full Deep-Dive Configuration")
            summary_output.append("<details><summary>Click to expand deep-dive JSON</summary>")
            summary_output.append("\n```json\n" + deep_dive_json + "\n```")
            summary_output.append("</details>")
        else:
            summary_output.append(f"#### ⚠️ Deep-Dive Fetch Failed\n**Error:** {details_resp.text}")
    else:
        summary_output.append(f"#### ⚠️ Warning\nCould not find a unique ID for deep-dive fetch.")

    # Write the compiled success summary
    write_to_summary("\n".join(summary_output))

if __name__ == "__main__":
    main()
