import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

JOB_ID = os.environ.get("JOB_ID")
ATTACK_ID = os.environ.get("ATTACK_ID")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
DATA_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/data-plane/v1"

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

def escape_md(text):
    """Escapes markdown for single-line usage."""
    if not text:
        return ""
    return str(text).replace('\n', ' ').replace('\r', '').replace('|', '&#124;')

def main():
    if not JOB_ID or not ATTACK_ID:
        error_msg = "Both JOB_ID and ATTACK_ID must be provided. Please trigger the workflow with valid inputs."
        print(error_msg)
        write_to_summary(f"## ❌ Error\n{error_msg}")
        sys.exit(1)

    print("Generating OAuth 2.0 Access Token...")
    try:
        access_token = get_access_token() 
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        print(error_msg)
        write_to_summary(f"## ❌ Prisma AIRS Auth Failed\n**Error:** {error_msg}")
        sys.exit(1)

    write_to_summary(f"## 🔬 Multi-Turn Attack Details\n**Job ID:** `{JOB_ID}` <br> **Attack ID:** `{ATTACK_ID}`\n")

    headers = {
        "Authorization": f"Bearer {access_token}", 
        "Accept": "application/json"
    }
    
    # Using the exact endpoint from the official documentation
    endpoint = f"/report/static/{JOB_ID}/attack-multi-turn/{ATTACK_ID}"
    url = f"{DATA_BASE_URL}{endpoint}"
    
    print(f"Fetching multi-turn attack details from {url} ...")
    response = requests.get(url, headers=headers)
    
    if not response.ok:
        print(f"❌ Failed to fetch details: {response.status_code}")
        write_to_summary(f"#### ❌ Failed to Fetch Attack Details\n**Status Code:** {response.status_code}\n```json\n{response.text}\n```")
        sys.exit(1)

    data = response.json()
    
    # Assume the API returns a direct object for the attack, or wraps it in 'data'
    attack = data.get("data", data)

    if not attack:
        write_to_summary("✅ **No attack details found** for this specific ID.")
        sys.exit(0)

    # Extract high-level details
    attack_category = attack.get("category", attack.get("sub_category", "Unknown Category"))
    goal = attack.get("goal", "Unknown Goal")
    is_successful = attack.get("successful", False)
    status = "❌ Bypassed" if is_successful else "✅ Blocked/Failed"
    
    write_to_summary(f"### Attack Category: {escape_md(attack_category)}")
    write_to_summary(f"**Goal:** {escape_md(goal)}  <br> **Final Result:** {status}\n")

    # Flatten the raw conversation data
    raw_conversation_data = attack.get("outputs", attack.get("turns", []))
    conversation_data = []
    
    for item in raw_conversation_data:
        if isinstance(item, list):
            conversation_data.extend(item)
        elif isinstance(item, dict):
            conversation_data.append(item)
    
    if conversation_data:
        # Group by Attempt (generation)
        attempts_map = {}
        for turn in conversation_data:
            if not isinstance(turn, dict):
                continue
            gen_num = turn.get("generation", 1)  # Default to 1 if missing
            if gen_num not in attempts_map:
                attempts_map[gen_num] = []
            attempts_map[gen_num].append(turn)
            
        # Render the grouped data
        for gen_num in sorted(attempts_map.keys()):
            write_to_summary(f"#### 🔄 Attempt {gen_num}")
            
            for turn in attempts_map[gen_num]:
                turn_num = turn.get("turn", "N/A")
                
                # Extract prompt and response using keys
                prompt = str(turn.get("prompt", turn.get("input", "N/A")))
                resp = str(turn.get("output", turn.get("response", "N/A")))
                
                # Check turn-specific status (threat field)
                is_threat = turn.get("threat")
                if is_threat is True:
                    turn_status = "❌ Bypassed"
                elif is_threat is False:
                    turn_status = "✅ Blocked"
                else:
                    if "successful" in turn:
                        turn_status = "❌ Bypassed" if turn.get("successful") else "✅ Blocked"
                    else:
                        turn_status = "N/A"

                # Clearly list out the Turn, Prompt, and Response using code blocks for safety
                write_to_summary(f"**Turn {turn_num}** | **Status:** {turn_status}")
                write_to_summary(f"**Attack Prompt:**\n```text\n{prompt}\n```")
                write_to_summary(f"**Target AI Response:**\n```text\n{resp}\n```\n")
    else:
        write_to_summary("> *No turn-by-turn conversation data available in `outputs` or `turns` fields for this attack.*\n")

    # Add Raw JSON block at the bottom
    write_to_summary(
        "<details>\n"
        "<summary>📋 View Raw Multi-Turn Attack JSON</summary>\n\n"
        "```json\n" + json.dumps(data, indent=2) + "\n```\n\n"
        "</details>\n"
    )

    print("✅ Successfully fetched and processed multi-turn details.")

if __name__ == "__main__":
    main()
