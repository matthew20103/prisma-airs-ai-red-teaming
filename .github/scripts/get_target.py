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
        print("Available targets are:")
        
        # Build a list of available targets for both console and summary
        available_list = [f"* {t.get('name')}" for t in existing_targets]
        for t in available_list:
            print(f" - {t.replace('* ', '')}")
            
        summary_error = [
            f"### ❌ Target Not Found: `{TARGET_NAME}`",
            "**Available targets are:**",
            "\n".join(available_list)
        ]
        write_to_summary("\n".join(summary_error))
        sys.exit(1)

    print("\n✅ Found the target in the list! Here is the raw configuration data:")
    print("--------------------------------------------------")
    raw_config_json = json.dumps(target_obj, indent=2)
    print(raw_config_json)
    print("--------------------------------------------------")

    # --- Initialize GitHub Job Summary Output for Success ---
    summary_output = [
        f"## 🎯 Prisma AIRS Target Details: `{TARGET_NAME}`",
        "### ✅ Target Found",
        "#### Raw Configuration Data",
        "```json\n" + raw_config_json + "\n```"
    ]

    # 3. Try to get deep-dive details (checking common ID fields)
    target_id = target_obj.get("target_id") or target_obj.get("uuid") or target_obj.get("id")

    if target_id:
        print(f"\nFetching deep-dive details using ID: {target_id}...\n")
        details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)
        
        if details_resp.ok:
            print("==================================================")
            print(f" FULL DEEP-DIVE CONFIGURATION FOR: {TARGET_NAME}")
            print("==================================================")
            deep_dive_json = json.dumps(details_resp.json(), indent=2)
            print(deep_dive_json)
            print("==================================================")
            
            # Append deep-dive data to the summary
            summary_output.append("#### 🔎 Full Deep-Dive Configuration")
            summary_output.append("```json\n" + deep_dive_json + "\n```")
        else:
            error_msg = f"Failed to fetch details: {details_resp.text}"
            print(error_msg)
            summary_output.append("#### ⚠️ Deep-Dive Fetch Failed")
            summary_output.append(f"**Error:** {error_msg}")
    else:
        warning_msg = "Could not find an ID field to fetch deeper details, but the list data above should have what we need!"
        print(f"\n⚠️ Warning: {warning_msg}")
        summary_output.append(f"#### ⚠️ Warning\n{warning_msg}")

    # Write the compiled success summary out to GitHub Actions
    write_to_summary("\n".join(summary_output))

if __name__ == "__main__":
    main()
