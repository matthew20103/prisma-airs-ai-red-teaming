import os
import requests
import sys
import json

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

AUTH_URL = "https://auth.apps.paloaltonetworks.com/oauth2/access_token"
MGMT_BASE_URL = "https://api.sase.paloaltonetworks.com/ai-red-teaming/mgmt-plane/v1"

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

def parse_text_env(var_name, default=None):
    """Parses plain text fields and drops them if an exclusion keyword is used."""
    val = os.environ.get(var_name, "").strip()
    if not val:
        return default
        
    if val.upper() in ['NONE', 'NA', 'N/A', 'NULL', '-']:
        return None
        
    return val

def parse_json_env(var_name, default=None):
    """Parses JSON fields and drops them if an exclusion keyword is used."""
    val = os.environ.get(var_name, "").strip()
    if not val:
        return default
    
    if val.upper() in ['NONE', 'NA', 'N/A', 'NULL', '-', '{}']:
        return None
        
    try:
        return json.loads(val)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse {var_name} as JSON. Error: {e}")
        return default

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)
        
    target_name = os.environ.get("TARGET_NAME")

    if not target_name:
        print("Error: TARGET_NAME is required.")
        sys.exit(1)

    session_supported = os.environ.get("SESSION_SUPPORTED", "false").lower() == "true"
    
    resp_json = parse_json_env("RESPONSE_JSON", {"reply": "{RESPONSE}"})
    response_key = next(iter(resp_json.keys()), "reply") if resp_json else "reply"

    # 1. Base Variables
    target_payload = {
        "name": target_name,
        "target_type": os.environ.get("TARGET_TYPE", "APPLICATION"),
        "connection_type": os.environ.get("CONNECTION_TYPE", "CUSTOM"),
        "response_mode": os.environ.get("RESPONSE_MODE", "REST"),
        "api_endpoint_type": os.environ.get("API_ENDPOINT_TYPE", "PUBLIC"),
        "session_supported": session_supported,
        "extra_info": {
            "response_key": response_key
        },
        "connection_params": {
            "api_endpoint": os.environ.get("MODEL_ENDPOINT"),
            "request_json": parse_json_env("REQUEST_JSON", {"prompt": "{INPUT}"}),
            "response_json": resp_json,
            "response_key": response_key
        }
    }

    # 2. String/Optional Fields
    description = parse_text_env("DESCRIPTION")
    if description:
        target_payload["description"] = description

    # FIX: Move network broker ID inside connection_params
    nb_uuid = parse_text_env("NB_CHANNEL_UUID")
    if nb_uuid and target_payload["api_endpoint_type"] == "NETWORK_BROKER":
        # Check standard API specs, usually it is network_broker_id
        target_payload["connection_params"]["network_broker_id"] = nb_uuid

    req_headers = parse_json_env("REQUEST_HEADERS")
    if req_headers:
        target_payload["connection_params"]["request_headers"] = req_headers

    # 3. Multi-turn config
    if session_supported:
        mt_config = parse_json_env("MULTI_TURN_CONFIG")
        if mt_config and "type" in mt_config:
            target_payload["multi_turn_config"] = mt_config

    # 4. Target Metadata
    rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "false").lower() == "true"
    target_payload["target_metadata"] = {
        "rate_limit_enabled": rate_limit_enabled
    }
    if rate_limit_enabled:
        target_rate_limit = os.environ.get("TARGET_RATE_LIMIT", "100").strip()
        target_payload["target_metadata"]["rate_limit"] = int(target_rate_limit) if target_rate_limit.isdigit() else 100

    # 5. FIX: Parse Context blocks as JSON, not Strings
    target_bg = parse_json_env("TARGET_BACKGROUND")
    if target_bg:
        target_payload["target_background"] = target_bg

    add_context = parse_json_env("ADDITIONAL_CONTEXT")
    if add_context:
        target_payload["additional_context"] = add_context

    # --- Target Management Execution ---
    print(f"Checking for existing target named '{target_name}'...")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to fetch targets: {list_resp.text}")
        sys.exit(1)

    existing_targets = list_resp.json().get("data", [])
    target_id = next((t.get("id") for t in existing_targets if t.get("name") == target_name), None)
    
    is_update = bool(target_id)
    query_params = {"validate": "true"}

    print("\n--- DEBUG: Smart Payload being sent to Prisma AIRS ---")
    print(json.dumps(target_payload, indent=2))
    print("------------------------------------------------------\n")

    if is_update:
        print(f"Updating existing target: {target_name} ({target_id})")
        resp = requests.put(f"{MGMT_BASE_URL}/target/{target_id}", headers=headers, json=target_payload, params=query_params)
    else:
        print(f"Creating new target: {target_name}")
        resp = requests.post(f"{MGMT_BASE_URL}/target", headers=headers, json=target_payload, params=query_params)
        
    if not resp.ok:
        print(f"Target management failed: {resp.text}")
        if "validation_error" in resp.text:
            print("\n[!] VALIDATION FAILED: Prisma AIRS rejected the payload or couldn't reach the endpoint.")
            print("[!] Check the DEBUG payload above to ensure your schema and authentication headers are correct.")
        sys.exit(1)
        
    target_id = target_id or resp.json().get("uuid") or resp.json().get("id")
    print(f"\n✅ Target is successfully registered and validated! ID: {target_id}")
    print("✅ Profiling has been automatically triggered by Prisma AIRS in the background.")
    print("Use the 'Check Profiling Status' workflow to see the results later!")

    action_text = "Updated" if is_update else "Created"
    api_endpoint = target_payload.get("connection_params", {}).get("api_endpoint", "N/A")
    target_type = target_payload.get("target_type", "N/A")

    write_summary(f"## 🎯 Prisma AIRS Target {action_text}")
    write_summary(f"**Status:** `Successfully {action_text}` ✅")
    write_summary(f"**Target Name:** `{target_name}`")
    write_summary(f"**Target ID:** `{target_id}`")
    write_summary(f"**Target Type:** `{target_type}`")
    write_summary(f"**Endpoint URL:** `{api_endpoint}`")
    write_summary(f"\n*This AI agent is now registered in Prisma AIRS and profiling has been triggered in the background! Use the Check Profiling Status workflow to see the results.*")

if __name__ == "__main__":
    main()
