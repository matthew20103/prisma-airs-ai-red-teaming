# 🛡️ Prisma AIRS AI Red Teaming Automation

This repository provides a collection of GitHub Actions workflows to automate the lifecycle of AI Red Teaming using **Palo Alto Networks Prisma AIRS**. These workflows allow you to manage targets, monitor AI profiling, and execute security scans directly from your CI/CD pipeline.

## 🚀 Workflows

| # | Workflow Name | Description |
|---|---|---|
| **01** | **Prisma AIRS - List All Targets** | Lists all configured AI targets within the specified TSG. |
| **02** | **Prisma AIRS - Get Target Details** | Fetches detailed configuration and metadata for a specific target. |
| **03** | **Prisma AIRS - Create Target** | Programmatically provisions a new AI target (API or Web) for testing. |
| **04** | **Prisma AIRS - Check Profiling Status** | Monitors the profiling process and generates a detailed summary of learned attributes. |
| **05** | **Prisma AIRS - Run Red Team Scan** | Triggers an active security assessment against a profiled target. |
| **06** | **Prisma AIRS - List Scan Jobs** | Provides a history and status overview of all executed scan jobs. |
| **07** | **Prisma AIRS - Get Scan Report** | Retrieves and summarizes the security findings from a completed scan. |
| **08** | **Prisma AIRS - Download Scan Report** | Downloads the security scan report artifacts. |
| **09** | **Prisma AIRS - Get Score Trend** | Retrieves the security and safety score trends over time. |
| **10** | **Prisma AIRS - Get Multi-Turn Attack Details** | Fetches detailed turn-by-turn conversation logs, attacker prompts, and AI responses for specific multi-turn attacks. |
| **11** | **Prisma AIRS - List Job Attacks** | Lists all individual attacks executed during a job to easily retrieve their respective Attack IDs. |

---

## ⚙️ Configuration

### GitHub Secrets
To authenticate with the Prisma AIRS API, you must add the following **Secrets** to your repository:

| Secret Name | Description |
|---|---|
| `PRISMA_CLIENT_ID` | Your Prisma SASE OAuth 2.0 Client ID. |
| `PRISMA_CLIENT_SECRET` | Your Prisma SASE OAuth 2.0 Client Secret. |
| `PRISMA_TSG_ID` | Your Tenant Service Group ID. |

### Environment Variables
Workflows typically require inputs such as `TARGET_NAME` or `JOB_ID`. These can be provided manually via the "Run workflow" dispatch menu in the Actions tab.

---

## 📊 Automated Reporting
Many workflows include a custom **GitHub Job Summary**. Every time they run, they generate rich Markdown reports directly in the GitHub UI containing:

* **Target Profiling Summaries:** Quick-look metrics for Competitors, Languages, Banned Keywords, and Tools.
* **Scan Dashboards:** Visual pie charts and distribution tables of successful bypasses by severity and category.
* **Multi-Turn Transcripts:** Detailed breakdowns of Gen AI attacks, grouping attacker prompts and target responses by turn.
* **Raw JSON Diagnostics:** Collapsible raw API responses for deeper debugging.

---

## 🛠️ Usage
1.  Navigate to the **Actions** tab in GitHub.
2.  Select the desired workflow (e.g., `10. Prisma AIRS - Get Multi-Turn Attack Details`).
3.  Click **Run workflow**.
4.  Enter the required parameters (e.g., Job ID, Attack ID).
5.  Once completed, click on the run to view the **Summary** report at the bottom of the page.

---

## 📂 Project Structure
* `.github/workflows/`: Contains the YAML definitions for the Actions.
* `.github/scripts/`: Contains the Python logic for API integration, data parsing, and report generation.
