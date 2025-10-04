# PM Notification Quality Assistant

This project is a full-stack application designed to analyze the quality of Plant Maintenance (PM) notifications. It consists of a Python/Flask backend that uses a Large Language Model for analysis and an SAP Fiori/UI5 frontend for the user interface.

## Table of Contents

- [Project Structure](#project-structure)
- [Application Overview](#application-overview)
- [Key Features](#key-features)
- [Architecture Deep Dive](#architecture-deep-dive)
- [Getting Started](#getting-started)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Lessons Learned](#lessons-learned)

## Project Structure

```
.
├── approuter/         # Node.js App Router (serves UI, proxies to backend)
├── backend/           # Python Flask Backend
└── pm-analyzer-fiori/ # SAP Fiori Frontend
```

## Application Overview

The PM Notification Quality Assistant aims to proactively enhance the quality of Plant Maintenance notifications, particularly in highly regulated environments like pharmaceutical production. By leveraging Artificial Intelligence, the application identifies deficiencies in documentation, provides actionable insights, and supports a continuous improvement process (KVP). It's designed for a range of users, ensuring that maintenance records are audit-proof and compliant with stringent data integrity principles (ALCOA+).

> **Note:** This version of the application has authentication completely removed for simplified deployment and demonstration purposes.

## Key Features

- **AI-Powered Quality Analysis:** Automated evaluation of maintenance notification texts based on Good Manufacturing Practice (GMP) and ALCOA+ principles.
- **Quantitative Scoring:** Each analysis provides a numerical quality score (0-100) for quick assessment.
- **Detailed Problem Identification:** The AI highlights specific issues and gaps in the notification documentation.
- **Summarized Expert Assessment:** A concise summary explains the AI's findings and recommendations.
- **Multi-language Support:** The application supports analysis in both English and German.
- **Notification Management:** View, filter, and search through a list of PM notifications.
- **Detailed Notification View:** Access comprehensive details of individual notifications and trigger on-demand AI analysis.
- **Visual Score Indicator:** A clear visual indicator provides immediate feedback on the notification's quality score.

## Architecture Deep Dive

The application follows a client-server architecture, with a distinct separation between the backend and frontend components, deployed as a Multi-Target Application (MTA) on SAP BTP Cloud Foundry.

### Backend (Python/Flask)

The backend is a lightweight Flask application responsible for handling API requests and performing the core AI-driven text analysis.

- **Technology Stack:** Flask, Gunicorn, Pydantic, Google Gemini API.
- **Deployment Type:** Deployed as a standard Cloud Foundry application.
- **`main.py`**: The central Flask application file. It defines API routes (`/health` and `/api/analyze`).
- **`app/services/analysis_service.py`**: Integrates with the Google Gemini API (`gemini-1.5-flash-latest`).
- **`requirements.txt`**: Lists Python dependencies. Gunicorn is used as the production-grade WSGI server.
- **`manifest.yml`**: Defines the Cloud Foundry application properties. Crucially, it specifies the command to run the app with Gunicorn and declaratively defines the application's route.

### Frontend (SAP Fiori/UI5)

The frontend is an SAP Fiori application built with SAP UI5, providing an intuitive and enterprise-grade user interface.

- **Technology Stack:** SAP UI5, Node.js App Router.
- **Deployment Type:** The UI5 application's static content is embedded directly within the App Router's build artifact and served by the App Router itself. This robust pattern bypasses the need for the HTML5 Application Repository service.
- **`approuter/`**: Acts as the single entry point. It serves the static Fiori UI content and proxies API calls to the backend via the BTP Destination service.
- **`xs-app.json`**: Configures routing rules. It serves the Fiori app's content from a local directory (`localDir`) and proxies `/api` calls to the backend destination, preserving the API path prefix.

## Getting Started

### Prerequisites

- [Python 3.8+](https://www.python.org/downloads/)
- [Node.js 16+](https://nodejs.org/en/download/)
- [SAP Cloud Foundry CLI](https://developers.sap.com/topics/cloud-foundry.html)

### Local Development

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/pm-notification-analyzer.git
    cd pm-notification-analyzer
    ```
2.  **Configure the backend:**
    - Navigate to the `backend` directory.
    - Create a `.env` file by copying the `.env.example` file.
    - Add your `GOOGLE_API_KEY` to the `.env` file.
3.  **Run the backend:**
    ```bash
    # Create and activate a virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # Install dependencies
    pip install -r requirements.txt

    # Run the backend server
    python3 -m app.main
    ```
    The backend will now be running on `http://localhost:5001`.
4.  **Run the frontend:**
    In a new terminal window:
    ```bash
    # Navigate to the frontend directory
    cd pm-analyzer-fiori/

    # Install npm dependencies
    npm install

    # Start the frontend
    npm run start-noflp
    ```
    The frontend will now be running on `http://localhost:8080`.

## Deployment

The application is deployed to SAP BTP Cloud Foundry using a fully automated GitHub Actions workflow. The workflow is defined in `.github/workflows/deploy.yml`.

### Manual Post-Deployment Step

After the first deployment to a new SAP BTP subaccount, you must manually create an HTTP Destination. This tells the App Router how to find the backend.

- **Navigate To:** Your BTP Subaccount → Connectivity → Destinations
- **Name:** `pm-analyzer-backend` (must be exact)
- **Type:** `HTTP`
- **URL:** The URL of your deployed `pm-analyzer-backend` application.
- **Proxy Type:** `Internet`
- **Authentication:** `NoAuthentication`

## Configuration

### Backend

The backend requires a `GOOGLE_API_KEY` to be set as an environment variable. For local development, you can create a `.env` file in the `backend` directory. For production, this is set via the `cf set-env` command in the deployment workflow.

## Lessons Learned

- **Use a versioned SAPUI5 CDN:** This ensures the application always receives the latest secure patch for your chosen version.
- **Embed the UI in the Approuter:** This is a simpler and more robust deployment pattern than using the HTML5 Application Repository service.
- **Use a WSGI-compliant server:** A Flask (WSGI) application must be served by a WSGI-compliant server like Gunicorn.
- **Declaratively manage routes:** Always rely on the `manifest.yml` to declaratively manage routes.
- **Align App Router path rewriting:** The path rewriting logic in the App Router's `xs-app.json` must align perfectly with the backend's API route definitions.
- **Securely automate environment variables:** Never hardcode secrets. Use the platform's secret management for production environments.