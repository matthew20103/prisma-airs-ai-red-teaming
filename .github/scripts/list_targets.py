import os
import requests
import sys

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

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        headers = {"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # --- 1. Fetch and Print Network Brokers ---
    print("\nFetching all registered Network Brokers...\n")
    
    # Updated to the network-broker endpoint
    brokers_resp = requests.get(f"{MGMT_BASE_URL}/network-broker", headers=headers)
    
    if brokers_resp.ok:
        brokers = brokers_resp.json().get("data", [])
        write_summary("## 🌐 Prisma AIRS Network Brokers")
        
        if not brokers:
            print("No Network Brokers found in this TSG.")
            write_summary("No Network Brokers found in this TSG.\n\n---\n")
        else:
            print(f"{'BROKER NAME':<35} | {'STATUS':<15} | {'UUID'}")
            print("-" * 90)
            write_summary("| Broker Name | Status | UUID |")
            write_summary("|---|---|---|")
            
            for b in brokers:
                name = b.get("name", "Unknown")[:34]
                full_name = b.get("name", "Unknown")
                status = b.get("status", "N/A")  # Usually "Online", "Offline", "Active", etc.
                uuid = b.get("uuid") or b.get("id") or "N/A"
                
                print(f"{name:<35} | {status:<15} | {uuid}")
                write_summary(f"| `{full_name}` | `{status}` | `{uuid}` |")
            
            print("-" * 90)
            print(f"Total Brokers: {len(brokers)}\n")
            write_summary(f"\n**Total Brokers:** `{len(brokers)}`\n\n---\n")
    else:
        print(f"Failed to list network brokers. Status: {brokers_resp.status_code}")
        print(f"Raw Response: {brokers_resp.text}\n")
        # Script continues so it can still fetch targets

    # --- 2. Fetch and Print Targets ---
    print("Fetching all registered targets...\n")
    list_resp = requests.get(f"{MGMT_BASE_URL}/target", headers=headers)
    
    if not list_resp.ok:
        print(f"Failed to list targets: {list_resp.text}")
        sys.exit(1)

    targets = list_resp.json().get("data", [])
    write_summary("## 📋 Prisma AIRS Registered Targets")
    
    if not targets:
        print("No targets found in this TSG.")
        write_summary("No targets found in this TSG.")
        sys.exit(0)

    print(f"{'NAME':<35} | {'STATUS':<10} | {'VALIDATED':<10} | {'TYPE':<15} | {'UUID'}")
    print("-" * 115)
    write_summary("| Name | Status | Validated | Type | UUID |")
    write_summary("|---|---|---|---|---|")
    
    for t in targets:
        name = t.get("name", "Unknown")[:34]
        full_name = t.get("name", "Unknown")
        status = t.get("status", "N/A")
        validated = str(t.get("validated", "False"))
        t_type = t.get("target_type", "N/A")
        uuid = t.get("uuid") or t.get("id") or "N/A"
        
        print(f"{name:<35} | {status:<10} | {validated:<10} | {t_type:<15} | {uuid}")
        write_summary(f"| `{full_name}` | `{status}` | `{validated}` | `{t_type}` | `{uuid}` |")

    print("-" * 115)
    print(f"Total Targets: {len(targets)}")
    write_summary(f"\n**Total Targets:** `{len(targets)}`")

if __name__ == "__main__":
    main()
