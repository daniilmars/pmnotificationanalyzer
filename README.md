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
├── pm-analyzer/
│   ├── backend/       # Main PM Analyzer Backend (Python/Flask)
│   └── frontend/      # Main PM Analyzer Frontend (SAP Fiori/UI5)
└── rule-manager/
    ├── backend/       # Rule Manager Backend (Python/Flask)
    └── frontend/      # Rule Manager Frontend (SAP Fiori/UI5)
```

## Application Overview

The project now consists of two main applications:

1.  **PM Notification Quality Assistant:** A tool for maintenance planners to view notifications and get real-time quality analysis from a hybrid AI and rule-based system.
2.  **Rule Manager:** A tool for Quality Assurance experts to define, manage, and audit the business rules used by the main analyzer. It includes an AI Assistant to help create rules from SOP documents.

## Key Features

### PM Notification Analyzer
- **Hybrid Quality Analysis:** Automated evaluation using a combination of Google's Gemini AI and a configurable rule engine.
- **Notification Management:** View, filter, and search through a list of PM notifications.
- **Detailed Notification View:** Access comprehensive details and trigger on-demand analysis.
- **What-If Analysis & Chat Assistant:** Interactive tools to improve documentation quality.

### Rule Manager
- **Web-Based Rule Editor:** A user-friendly UI for QA experts to create and manage rules and rulesets without coding.
- **Versioning & Audit Trail:** All changes to rules are versioned and logged to ensure GMP compliance.
- **AI SOP Assistant:** Upload Standard Operating Procedure (SOP) documents (PDF) and get AI-powered suggestions for new rules.
- **Activation Lifecycle:** Rulesets can be drafted, tested, and formally activated for use in the analysis engine.

## Architecture Deep Dive

The application follows a microservices architecture where two distinct services cooperate.

### PM Notification Analyzer Service
- **Backend (Python/Flask):** Handles API requests for notifications and performs the hybrid analysis. It calls the Rule Manager service to fetch active rules for a given notification type.
- **Frontend (SAP Fiori/UI5):** Provides the main user interface for viewing and analyzing notifications.

### Rule Manager Service
- **Backend (Python/Flask):** A dedicated service that manages the entire lifecycle of quality rules. It exposes a REST API for the main analyzer to consume.
- **Frontend (SAP Fiori/UI5):** A separate, standalone UI for quality experts to manage the rule engine, create rulesets, and use the SOP Assistant.

## Getting Started

### Prerequisites

- [Python 3.8+](https://www.python.org/downloads/)
- [Node.js 16+](https://nodejs.org/en/download/)

### Local Development (Split Mode)

The project is designed to run in a "split mode" with four services running in parallel. You will need **four separate terminal windows**.

#### 1. Configure Credentials

- **Rule Manager Backend:** This service requires a Google Cloud Service Account for the AI SOP Assistant.
    1.  Place your downloaded service account JSON key file in `rule-manager/backend/` and name it `service-account.json`.
    2.  Create a file named `.env` in `rule-manager/backend/`.
    3.  Add the following line:
        ```
        GOOGLE_APPLICATION_CREDENTIALS="service-account.json"
        ```
- **Main Analyzer Backend:** This service uses a simple API Key.
    1.  Create a file named `.env` in `pm-analyzer/backend/`.
    2.  Add your key:
        ```
        GOOGLE_API_KEY="AIzaSy..."
        ```

#### 2. Run the Servers

**Terminal 1: Start Rule Manager Backend**
```bash
# Navigate to the Rule Manager backend
cd rule-manager/backend

# Create a virtual environment if you haven't already
# python3 -m venv venv.nosync

# Activate it
. venv.nosync/bin/activate

# Install dependencies
pip install -r requirements.txt

# Initialize and seed the database
python3 scripts/seed.py

# Run the server
python3 -m app.main
# (This service runs on http://localhost:5002)
```

**Terminal 2: Start Main Analyzer Backend**
```bash
# Navigate to the main backend
cd pm-analyzer/backend

# Create a virtual environment if you haven't already
# python3 -m venv venv

# Activate it
. venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python3 run.py
# (This service runs on http://localhost:5001)
```

**Terminal 3: Start Rule Manager Frontend**
```bash
# Navigate to the Rule Manager frontend
cd rule-manager/frontend

# Install dependencies
npm install

# Start the local server
npm run start-local
# (This will open in your browser at http://localhost:8080)
```

**Terminal 4: Start Main Analyzer Frontend**
```bash
# Navigate to the main analyzer frontend
cd pm-analyzer/frontend

# Install dependencies
npm install

# Start the local server
npm run start-noflp
# (This will open in your browser, likely at http://localhost:8081)
```

## Deployment

The application is deployed to SAP BTP Cloud Foundry using a fully automated GitHub Actions workflow. The workflow is defined in `.github/workflows/deploy.yml`.

> **Note:** The deployment configuration has not yet been updated to include the new Rule Manager microservice.

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