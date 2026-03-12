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
        write_to_summary(f"### ❌ Prisma AIRS Reports Failed\n**Error:** {error_msg}")
        sys.exit(1)

    # 1. Resolve Target ID
    print(f"Searching for target: '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        error_msg = f"Failed to list targets: {list_resp.text}"
        print(error_msg)
        write_to_summary(f"### ❌ Prisma AIRS Reports Failed\n**Error:** {error_msg}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        error_msg = f"Error: Could not find a target named '{TARGET_NAME}'."
        print(error_msg)
        write_to_summary(f"### ❌ Target Not Found\n**Error:** {error_msg}")
        sys.exit(1)

    target_id = target_obj.get("target_id") or target_obj.get("uuid") or target_obj.get("id")
    print(f"✅ Found Target! ID: {target_id}")

    # --- Initialize GitHub Job Summary Output ---
    summary_output = [
        f"## 🛡️ Prisma AIRS Security Reports: `{TARGET_NAME}`",
        f"**Target ID:** `{target_id}`",
        ""
    ]

    # 2. Feature: Get Attack Library Report
    # NOTE: Adjust this endpoint if the Prisma AIRS API uses a different path for the attack library
    attack_lib_endpoint = f"{MGMT_BASE_URL}/target/{target_id}/attack-library"
    print(f"\nFetching Attack Library Report from {attack_lib_endpoint}...")
    attack_resp = requests.get(attack_lib_endpoint, headers=headers)

    summary_output.append("### 📚 Attack Library Report")
    if attack_resp.ok:
        attack_data = attack_resp.json()
        print("Successfully fetched Attack Library.")
        summary_output.append("```json\n" + json.dumps(attack_data, indent=2) + "\n```")
    else:
        print(f"⚠️ Failed to fetch Attack Library: {attack_resp.status_code} - {attack_resp.text}")
        summary_output.append(f"**Status:** ⚠️ Failed ({attack_resp.status_code})\n```text\n{attack_resp.text}\n```")

    # 3. Feature: Get Agent Scan Report
    # NOTE: Adjust this endpoint if the Prisma AIRS API uses a different path for agent scans
    scan_endpoint = f"{MGMT_BASE_URL}/target/{target_id}/agent-scan"
    print(f"\nFetching Agent Scan Report from {scan_endpoint}...")
    scan_resp = requests.get(scan_endpoint, headers=headers)

    summary_output.append("### 🔬 Agent Scan Report")
    if scan_resp.ok:
        scan_data = scan_resp.json()
        print("Successfully fetched Agent Scan Report.")
        summary_output.append("```json\n" + json.dumps(scan_data, indent=2) + "\n```")
    else:
        print(f"⚠️ Failed to fetch Agent Scan Report: {scan_resp.status_code} - {scan_resp.text}")
        summary_output.append(f"**Status:** ⚠️ Failed ({scan_resp.status_code})\n```text\n{scan_resp.text}\n```")

    # Write the compiled summary out to GitHub Actions
    write_to_summary("\n".join(summary_output))
    print("\n✅ Reports processed and written to GitHub Job Summary.")

if __name__ == "__main__":
    main()
