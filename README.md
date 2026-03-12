# 🛡️ Prisma AIRS AI Red Teaming Automation

This repository provides a collection of GitHub Actions workflows to automate the lifecycle of AI Red Teaming using **Palo Alto Networks Prisma AIRS**. These workflows allow you to manage targets, monitor AI profiling, and execute security scans directly from your CI/CD pipeline.

## 🚀 Workflows

| # | Workflow Name | Description |
|---|---|---|
| **1** | **Prisma AIRS - List All Targets** | Lists all configured AI targets within the specified TSG. |
| **2** | **Prisma AIRS - Get Target Details** | Fetches detailed configuration and metadata for a specific target. |
| **3** | **Prisma AIRS - Create Target** | Programmatically provisions a new AI target (API or Web) for testing. |
| **4** | **Prisma AIRS - Check Profiling Status** | Monitors the profiling process and generates a detailed summary of learned attributes. |
| **5** | **Prisma AIRS - Run Red Team Scan** | Triggers an active security assessment against a profiled target. |
| **6** | **Prisma AIRS - List Scan Jobs** | Provides a history and status overview of all executed scan jobs. |
| **7** | **Prisma AIRS - Get Scan Report** | Retrieves and summarizes the security findings from a completed scan. |

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
Workflows typically require a `TARGET_NAME` input. This can be provided manually via the "Run workflow" dispatch menu in the Actions tab.

---

## 📊 Automated Reporting
The **Check Profiling Status** workflow includes a custom **GitHub Job Summary**. Every time it runs, it generates a report containing:

* **Target Profiling Summary Table:** Quick-look metrics for Competitors, Languages, Banned Keywords, and Tools.
* **System Capabilities:** A detailed JSON breakdown of the target's technical stack (collapsed by default).
* **Target Context & Background:** The AI's identity, industry focus, and use case (collapsed by default).

---

## 🛠️ Usage
1.  Navigate to the **Actions** tab in GitHub.
2.  Select the desired workflow (e.g., `4. Prisma AIRS - Check Profiling Status`).
3.  Click **Run workflow**.
4.  Enter the `TARGET_NAME`.
5.  Once completed, click on the run to view the **Summary** report at the bottom of the page.

---

## 📂 Project Structure
* `.github/workflows/`: Contains the YAML definitions for the Actions.
* `.github/scripts/`: Contains the Python logic for API integration and report generation.
