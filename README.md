# PM Notification Quality Assistant

This project is a full-stack application designed to analyze the quality of Plant Maintenance (PM) notifications. It consists of a Python/Flask backend that uses a Large Language Model for analysis and an SAP Fiori/UI5 frontend for the user interface.

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

## SAP BTP Deployment Strategy (CI/CD with GitHub Actions)

The application is deployed to SAP BTP Cloud Foundry using a fully automated GitHub Actions workflow.

- **Backend Deployment:** The backend is pushed directly using `cf push`. The command relies on the `backend/manifest.yml` to declaratively set its route.

- **Frontend Deployment:** The App Router and the embedded Fiori UI are deployed together via the MTA `cf deploy` command.

- **Secrets Management:** The `GOOGLE_API_KEY` is not stored in the repository. It is injected at deployment time using GitHub Actions Secrets and the `cf set-env` command.

## Manual Post-Deployment Step

Even with a fully automated CI/CD pipeline, one manual step is required after the very first deployment to a new SAP BTP subaccount.

**Create Backend Destination:** You must manually create an HTTP Destination in your SAP BTP subaccount. This tells the App Router how to find the backend.

- **Navigate To:** Your BTP Subaccount → Connectivity → Destinations

- **Name:** `pm-analyzer-backend` (must be exact)

- **Type:** `HTTP`

- **URL:** The URL of your deployed `pm-analyzer-backend` application.

- **Proxy Type:** `Internet`

- **Authentication:** `NoAuthentication`

## Lessons Learned from Deployment

Deploying this stack to SAP BTP involved several specific challenges. This section captures the key lessons to aid future deployments.


Lesson: Use the versioned SAPUI5 CDN (https://ui5.sap.com/<version>/...) and an "evergreen" URL (e.g., /1.120/) to ensure the application always receives the latest secure patch for your chosen version.

Embedded Frontend vs. HTML5 Repo: The initial strategy using the HTML5 Application Repository service led to complex, hard-to-debug authentication issues.

Lesson: A simpler, more robust deployment pattern is to embed the UI directly into the Approuter. This makes the Approuter a self-contained web server for both static files and API proxying, eliminating a point of failure.

WSGI vs. ASGI Server Mismatch: The backend initially failed with a 500 Internal Server Error and a TypeError.

Lesson: A Flask (WSGI) application must be served by a WSGI-compliant server like Gunicorn. The Cloud Foundry buildpack may incorrectly infer a different server (like Uvicorn) if it's present in requirements.txt. The start command must be explicitly defined in the manifest.

Implementation: Added gunicorn to requirements.txt and set an explicit command: gunicorn --bind 0.0.0.0:$PORT app.main:app in backend/manifest.yml.

Declarative Route Management is Key: The backend initially deployed without a URL because the CI/CD script used a --no-route flag.

Lesson: Always rely on the manifest.yml to declaratively manage routes. Imperative flags like --no-route in a CI/CD script are fragile and lead to errors. Manual cf map-route commands should only be used for temporary debugging, not as a standard process.

Implementation: Removed the --no-route flag from the cf push command in the .github/workflows/deploy.yml script.

Align App Router Path Rewriting: API calls failed with a 404 Not Found from the backend even after all platform routing was correct.

Lesson: The path rewriting logic in the App Router's xs-app.json must align perfectly with the backend's API route definitions. If the backend expects an /api/ prefix, the App Router must not strip it away.

Implementation: Modified the API route target in approuter/xs-app.json from "/$1" to "/api/$1" to preserve the path.

Securely Automate Environment Variables: The backend requires a GOOGLE_API_KEY.

Lesson: Never hardcode secrets. In a CI/CD context, use the platform's secret management (e.g., GitHub Actions Secrets). The cf set-env command should be followed by cf restage for the variable to be loaded by the application.

Implementation: The GOOGLE_API_KEY is stored as a GitHub Secret and injected during the deployment workflow using cf set-env, followed by a cf restage of the backend app.

## How to start the application locally
### Create and activate a virtual environment
source venv/bin/activate

### Navigate to the backend directory
cd backend/

### Install dependencies
pip install -r requirements.txt

### Run the backend server
python3 -m app.main
The backend will now be running on http://localhost:5001

### Start the Frontend Application
In a new terminal window, start the SAP Fiori development server.
cd pm-analyzer-fiori/

### Install npm dependencies (you only need to do this once)
npm install

### Start the Frontend without the Sandbox
npm run start-noflp