# PM Notification Quality Suite

This project is a full-stack application suite designed to analyze and manage the quality of Plant Maintenance (PM) notifications. It consists of multiple services, including a Python/Flask backend that uses a Large Language Model for analysis and SAP Fiori/UI5 frontends for the user interfaces.

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
├── launchpad/
│   └── webapp/        # Unified Launchpad Frontend (SAP Fiori/UI5)
├── pm-analyzer/
│   ├── backend/       # Maintenance Execution Assistant Backend (Python/Flask)
│   └── frontend/      # Maintenance Execution Assistant Frontend (SAP Fiori/UI5)
└── rule-manager/
    ├── backend/       # Rule Manager Backend (Python/Flask)
    └── frontend/      # Rule Manager Frontend (SAP Fiori/UI5)
```

## Application Overview

The project is a suite of applications, accessible from a central launchpad.

1.  **Suite Launchpad:** The main entry point for all users, providing access to the different applications.
2.  **Maintenance Execution Assistant:** A tool for maintenance planners and technicians to view notifications and get real-time quality analysis from a hybrid AI and rule-based system.
3.  **Rule Manager:** A tool for Quality Assurance experts to define, manage, and audit the business rules used by the assistant. It includes an AI Assistant to help create rules from SOP documents.

## Key Features

### Maintenance Execution Assistant
- **Hybrid Quality Analysis:** Automated evaluation using a combination of Google's Vertex AI and a configurable rule engine.
- **Notification Management:** View, filter, and search through a list of PM notifications.
- **Detailed Notification View:** Access comprehensive details and trigger on-demand analysis.
- **What-If Analysis & Chat Assistant:** Interactive tools to improve documentation quality.

### Rule Manager
- **Web-Based Rule Editor:** A user-friendly UI for QA experts to create and manage rules and rulesets without coding.
- **Advanced Rule Types:** Supports two types of rules:
    - **Validation Rules:** Simple, objective checks on specific fields (e.g., length, content).
    - **AI Guidance Rules:** High-level instructions that dynamically guide the AI's analysis.
- **Robust Versioning & Audit Trail:** All changes to rulesets are versioned, and a complete audit trail is maintained for compliance.
- **AI SOP Assistant:** Upload Standard Operating Procedure (SOP) documents (PDF) and get AI-powered suggestions for new rules.
- **Activation Lifecycle:** Rulesets can be drafted, tested, and formally activated for use in the analysis engine.

## Architecture Deep Dive

The application follows a microservices architecture where multiple services cooperate.

### Maintenance Execution Assistant Service
- **Backend (Python/Flask):** Handles API requests for notifications and performs the hybrid analysis. It calls the Rule Manager service to fetch active rules for a given notification type.
- **Frontend (SAP Fiori/UI5):** Provides the main user interface for viewing and analyzing notifications.

### Rule Manager Service
- **Backend (Python/Flask):** A dedicated service that manages the entire lifecycle of quality rules. It exposes a REST API for the main analyzer to consume.
- **Frontend (SAP Fiori/UI5):** A separate, standalone UI for quality experts to manage the rule engine, create rulesets, and use the SOP Assistant.

## Getting Started

### Running with Docker Compose

This is the easiest way to get the entire application stack running.

1.  **Configure Credentials:** Make sure you have valid `.env` files in the `pm-analyzer/backend` and `rule-manager/backend` directories.
2.  **Run Docker Compose:**

    ```bash
    docker-compose up --build
    ```

This will build the Docker images for each service and start them. The main entry point for the application is the **Suite Launchpad**.

-   **Suite Launchpad:** http://localhost:8008

From the launchpad, you can navigate to the individual applications:
-   **Maintenance Execution Assistant:** http://localhost:8081
-   **Rule Manager:** http://localhost:8080


### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop)
- [Python 3.8+](https://www.python.org/downloads/) (Optional, for local debugging)
- [Node.js 16+](https://nodejs.org/en/download/) (Optional, for local debugging)
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)

## Deployment

The application is deployed to SAP BTP Cloud Foundry using a fully automated GitHub Actions workflow. The workflow is defined in `.github/workflows/deploy.yml`.

> **Note:** The deployment configuration has not yet been updated to include the new Rule Manager and Launchpad applications.


## Configuration

### Backend

The backend requires a `GOOGLE_CLOUD_PROJECT` to be set as an environment variable. For local development, you can create a `.env` file in the `backend` directory. For production, this is set via the `cf set-env` command in the deployment workflow.

## Lessons Learned

- **Use a versioned SAPUI5 CDN:** This ensures the application always receives the latest secure patch for your chosen version.
- **Embed the UI in the Approuter:** This is a simpler and more robust deployment pattern than using the HTML5 Application Repository service.
- **Use a WSGI-compliant server:** A Flask (WSGI) application must be served by a WSGI-compliant server like Gunicorn.
- **Declaratively manage routes:** Always rely on the `manifest.yml` to declaratively manage routes.
- **Align App Router path rewriting:** The path rewriting logic in the App Router's `xs-app.json` must align perfectly with the backend's API route definitions.
- **Securely automate environment variables:** Never hardcode secrets. Use the platform's secret management for production environments.