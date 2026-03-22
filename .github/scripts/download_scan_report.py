import os
import requests
import sys

CLIENT_ID = os.environ.get("PRISMA_CLIENT_ID")
CLIENT_SECRET = os.environ.get("PRISMA_CLIENT_SECRET")
TSG_ID = os.environ.get("PRISMA_TSG_ID")

ATTACK_JOB_ID = os.environ.get("ATTACK_JOB_ID")
AGENT_JOB_ID = os.environ.get("AGENT_JOB_ID")
FILE_FORMAT = os.environ.get("FILE_FORMAT", "ALL")

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

def download_report(job_id, label):
    """Hits the /download endpoint and saves the file to the workspace."""
    if not job_id:
        msg = f"⚠️ Skipped {label}: No Job ID provided."
        print(msg)
        write_to_summary(f"### {label}\n{msg}")
        return

    print(f"\nInitiating download for {label} (Job ID: {job_id}, Format: {FILE_FORMAT})...")
    
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    params = {"file_format": FILE_FORMAT}
    url = f"{DATA_BASE_URL}/report/{job_id}/download"
    
    response = requests.get(url, headers=headers, params=params, stream=True)
    
    if response.ok:
        content_disposition = response.headers.get("Content-Disposition", "")
        if "filename=" in content_disposition:
            filename = content_disposition.split("filename=")[-1].strip("\"'")
        else:
            ext = ".zip" if FILE_FORMAT == "ALL" else f".{FILE_FORMAT.lower()}"
            filename = f"{label.replace(' ', '_').lower()}_{job_id}{ext}"
            
        # --- NEW: Create a directory and save the file inside it ---
        os.makedirs("reports", exist_ok=True)
        filepath = os.path.join("reports", filename)
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        success_msg = f"✅ Successfully downloaded: `{filename}`"
        print(success_msg)
        write_to_summary(f"### {label}\n**Job ID:** `{job_id}`\n{success_msg}")
    else:
        error_msg = f"❌ Failed to download {label}. Status: {response.status_code}"
        print(error_msg)
        print(response.text)
        write_to_summary(f"### {label}\n**Job ID:** `{job_id}`\n{error_msg}\n```json\n{response.text}\n```")

def main():
    print("Generating OAuth 2.0 Access Token...")
    try:
        get_access_token() 
    except Exception as e:
        error_msg = f"Authentication failed: {e}"
        print(error_msg)
        write_to_summary(f"## ❌ Download Failed\n**Error:** {error_msg}")
        sys.exit(1)

    write_to_summary("## 📥 Prisma AIRS Report Downloads")
    write_to_summary("> **💡 NOTE:** Your files have been successfully generated! **Scroll down to the very bottom of this page to the 'Artifacts' section** to download them.\n")

    download_report(ATTACK_JOB_ID, "Attack Library")
    download_report(AGENT_JOB_ID, "Agent Scan")

    print("\n✅ Script execution complete.")

if __name__ == "__main__":
    main()
