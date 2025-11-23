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
- **Multi-language Support:** The application supports full analysis and UI localization in **English** and **German**, including translated test data.
- **Notification Management:** View, filter, and search through a list of PM notifications.
- **Detailed Notification View:** Access comprehensive details of individual notifications and trigger on-demand AI analysis.
- **Unified Workspace:** View Notification (Problem) and Order (Resolution) details in a single view.
- **"Command Center" Layout:** A persistent side panel ("Quality Guardian") displays real-time AI analysis and chat without obstructing the main workspace.
- **"What-If" Analysis:** Interactive editing of the notification text to instantly see how changes affect the quality score.
- **Chat Assistant:** A conversational AI interface to ask questions about the notification and get guidance.

## UI/UX Overview

The user interface is designed to be intuitive and efficient, following standard SAP Fiori design principles. It provides a clear and structured way for users to interact with PM notifications and their quality analysis.

### Worklist View (Main Screen)

The initial screen of the application is the **Worklist View**, which serves as the central hub for managing notifications.

- **Notification List:** Displays a comprehensive list of PM notifications, showing key information at a glance (ID, description, priority, status, etc.).
- **Filtering:** A powerful filter bar allows users to narrow down the list based on various criteria.
- **Navigation:** Users can select a notification from the list to navigate to the detailed **Object View**.
- **Language Selection:** A language switcher allows users to toggle between English and German, instantly localizing the UI and the data content.

### Object View (Detail Screen)

The **Object View** provides a detailed look at a single PM notification, utilizing a **Dynamic Side Content** layout.

1.  **Main Content (Left):**
    -   **Header:** Key header data (Priority, Type, Creator, Dates).
    -   **Notification Tab:** Detailed problem description, functional location, equipment, and damage codes.
    -   **Work Order Tab:** Linked order details, operations table, and components/materials list.

2.  **Quality Guardian (Right Side Panel):**
    -   **Live Score:** A visual gauge (0-100%) indicating the quality of the documentation.
    -   **Problem List:** Specific, actionable items identified by the AI (e.g., "Missing root cause").
    -   **What-If Analysis:** An editor to refine the description and re-analyze.
    -   **Chat Assistant:** An interactive chat to query the notification context.

## Architecture Deep Dive

The application follows a client-server architecture, with a distinct separation between the backend and frontend components, deployed as a Multi-Target Application (MTA) on SAP BTP Cloud Foundry.

### Backend (Python/Flask)

The backend is a lightweight Flask application responsible for handling API requests, managing the SQLite database, and performing the core AI-driven text analysis.

- **Technology Stack:** Flask, Gunicorn, Pydantic, Google Gemini API, SQLite.
- **Database:** A local `sap_pm.db` (SQLite) simulates the SAP backend tables (`QMEL`, `AUFK`, `AFVC`, etc.) with a fully relational schema including multi-language text tables.
- **API Endpoints:**
    -   `/api/notifications`: Fetches the list of notifications (supports language param).
    -   `/api/notifications/<id>`: Fetches full object details (Notification + Order + Items) in the requested language.
    -   `/api/analyze`: Performs AI analysis.
    -   `/api/chat`: Handles conversational queries.

### Frontend (SAP Fiori/UI5)

The frontend is an SAP Fiori application built with SAP UI5, providing an intuitive and enterprise-grade user interface.

- **Technology Stack:** SAP UI5, Node.js App Router.
- **Layout:** Uses `DynamicSideContent` to implement the "Command Center" pattern.
- **Data Binding:** Uses standard OData-like JSON models with extensive use of Expression Binding for visibility control.
- **Localization:** Fully localized using `i18n` properties files and dynamic backend content fetching.

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

    # Initialize Database (First time only)
    python3 -c "from app.database import init_db; init_db()"
    python3 scripts/seed_data.py

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
