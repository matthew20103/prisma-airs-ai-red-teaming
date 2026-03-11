import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

TARGET_NAME = os.environ.get("TARGET_NAME")
SCAN_NAME = os.environ.get("SCAN_NAME", "Automated CI/CD Scan")
CATEGORIES_INPUT = os.environ.get("CATEGORIES", "PROMPT_INJECTION, HATE_TOXIC_ABUSE")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"
DATA_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/data-plane/v1"

def write_summary(markdown_text):
    """Writes output directly to the GitHub Actions Summary UI page."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
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
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # --- 1. MGMT-PLANE: Lookup Target ID ---
    print(f"Looking up target ID for '{TARGET_NAME}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to list targets: {list_resp.text}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_obj = next((t for t in existing_targets if t.get("name") == TARGET_NAME), None)

    if not target_obj:
        print(f"Error: Could not find a target named '{TARGET_NAME}'. Run the Create Target workflow first.")
        sys.exit(1)

    target_id = target_obj.get("uuid") or target_obj.get("target_id") or target_obj.get("id")
    print(f"✅ Found Target! ID: {target_id}")

    # --- 2. Smart Category Mapper ---
    SECURITY = ["ADVERSARIAL_SUFFIX", "EVASION", "INDIRECT_PROMPT_INJECTION", "JAILBREAK", "MULTI_TURN", "PROMPT_INJECTION", "REMOTE_CODE_EXECUTION", "SYSTEM_PROMPT_LEAK", "TOOL_LEAK", "MALWARE_GENERATION"]
    SAFETY = ["BIAS", "CBRN", "CYBERCRIME", "DRUGS", "HATE_TOXIC_ABUSE", "NON_VIOLENT_CRIMES", "POLITICAL", "SELF_HARM", "SEXUAL", "VIOLENT_CRIMES_WEAPONS"]
    BRAND = ["COMPETITOR_ENDORSEMENTS", "BRAND_TARNISHING_SELF_CRITICISM", "DISCRIMINATING_CLAIMS", "POLITICAL_ENDORSEMENTS"]
    COMPLIANCE = ["OWASP", "MITRE_ATLAS", "NIST", "DASF_V2"]

    categories_payload = {}
    input_cats = [c.strip().upper() for c in CATEGORIES_INPUT.split(",") if c.strip()]
    
    for cat in input_cats:
        if cat in SECURITY:
            categories_payload.setdefault("SecuritySubCategory", []).append(cat)
        elif cat in SAFETY:
            categories_payload.setdefault("SafetySubCategory", []).append(cat)
        elif cat in BRAND:
            categories_payload.setdefault("BrandSubCategory", []).append(cat)
        elif cat in COMPLIANCE:
            categories_payload.setdefault("ComplianceSubCategory", []).append(cat)
        else:
            print(f"⚠️ Warning: Unknown category '{cat}', defaulting to SecuritySubCategory")
            categories_payload.setdefault("SecuritySubCategory", []).append(cat)

    # --- 3. Build the Data-Plane Payload ---
    scan_payload = {
        "name": SCAN_NAME,
        "target": {
            "uuid": target_id
        },
        "job_type": "DYNAMIC",
        "job_metadata": {
            "categories": categories_payload
        }
    }

    print("\n--- DEBUG: Scan Payload ---")
    print(json.dumps(scan_payload, indent=2))
    print("---------------------------\n")

    # --- 4. DATA-PLANE: Trigger the Scan ---
    print(f"Triggering Prisma AIRS Scan: '{SCAN_NAME}' via Data-Plane...")
    scan_resp = requests.post(f"{DATA_BASE_URL}/scan", headers=headers, json=scan_payload)

    if not scan_resp.ok:
        print(f"Failed to start scan: {scan_resp.text}")
        sys.exit(1)

    scan_data = scan_resp.json()
    scan_id = scan_data.get("uuid") or scan_data.get("id") or scan_data.get("scan_id", "UNKNOWN")

    print(f"✅ Scan successfully started! Scan ID: {scan_id}")

    # --- 5. Write Beautiful Summary to GitHub UI ---
    write_summary(f"## 🛡️ Prisma AIRS Red Team Scan Triggered")
    write_summary(f"**Target:** `{TARGET_NAME}`")
    write_summary(f"**Scan Name:** `{SCAN_NAME}`")
    write_summary(f"**Scan ID:** `{scan_id}`")
    write_summary(f"### 🎯 Attack Categories Executing:")
    write_summary("```json\n" + json.dumps(categories_payload, indent=2) + "\n```")
    write_summary("\n*The scan is now running in the background. Check the Prisma AIRS console for live execution details and reports.*")

if __name__ == "__main__":
    main()
