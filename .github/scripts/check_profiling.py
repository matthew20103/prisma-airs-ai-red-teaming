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



    # 1. Fetch deep dive details (Base configuration)

    details_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers)

    target_data = details_resp.json() if details_resp.ok else {}

    

    # 2. Fetch the Profiling Data

    print("Fetching deep profiling data from API...\n")

    prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profiling", headers=headers)

    

    # Fallback: Sometimes APIs use /profile instead of /profiling for GET requests

    if prof_resp.status_code == 404:

        prof_resp = requests.get(f"{MGMT_BASE_URL}/target/{target_id}/profile", headers=headers)

        

    prof_data = prof_resp.json() if prof_resp.ok else {}



    # Determine Status

    profiling_status = prof_data.get("status") or target_data.get("profiling_status", "UNKNOWN")

    profiling_status = str(profiling_status).upper()



    print(f"Current Profiling Status: {profiling_status}")

    print("-" * 50)



    # --- Initialize GitHub Job Summary Output ---

    # Added the magnifying glass icon here!

    summary_output = [

        f"## 🔍 Prisma AIRS Profiling Report: `{TARGET_NAME}`",

        f"**Target ID:** `{target_id}`",

        ""

    ]



    if profiling_status == "COMPLETED":

        print("✅ Profiling is complete! Here are the learned attributes based on the API Schema:\n")

        summary_output.append(f"### Status: ✅ {profiling_status}")

        summary_output.append("The profiling process has successfully mapped the following attributes:\n")

        

        # Look for dynamic fields

        other_details = prof_data.get("other_details") or target_data.get("other_details") or {}

        ai_fields = prof_data.get("ai_generated_fields") or target_data.get("ai_generated_fields") or []

        background = prof_data.get("target_background") or target_data.get("target_background") or {}

        context = prof_data.get("additional_context") or target_data.get("additional_context") or {}



        # 1. System Capabilities

        print("--- SYSTEM CAPABILITIES (other_details) ---")

        summary_output.append("#### ⚙️ System Capabilities")

        if other_details:

            details_json = json.dumps(other_details, indent=2, ensure_ascii=False)

            print(details_json + "\n")

            summary_output.append("```json\n" + details_json + "\n```")

        else:

            print("No 'other_details' object found in the API response.\n")

            summary_output.append("*No 'other_details' object found.*")



        # 2. AI Generated Fields

        if ai_fields:

            print("--- AI GENERATED FIELDS ---")

            ai_json = json.dumps(ai_fields, indent=2)

            print(ai_json + "\n")

            summary_output.append("#### 🧠 AI Generated Fields")

            summary_output.append("```json\n" + ai_json + "\n```")



        # 3. Standard Contexts

        print("--- TARGET CONTEXT & BACKGROUND ---")

        context_json = json.dumps({"target_background": background, "additional_context": context}, indent=2, ensure_ascii=False)

        print(context_json)

        summary_output.append("#### 📂 Target Context & Background")

        summary_output.append("```json\n" + context_json + "\n```")



    elif profiling_status in ["PENDING", "IN_PROGRESS", "RUNNING"]:

        msg = "⏳ Profiling is still running. Please check back later."

        print(msg)

        summary_output.append(f"### Status: ⏳ {profiling_status}")

        summary_output.append(msg)

    else:

        msg = f"⚠️ Profiling ended with status: {profiling_status}"

        print(msg)

        summary_output.append(f"### Status: ⚠️ {profiling_status}")



    # Write the compiled summary out to GitHub Actions

    write_to_summary("\n".join(summary_output))



if __name__ == "__main__":

    main()
