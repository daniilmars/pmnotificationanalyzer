PM Notification Quality Assistant
This project is a full-stack application designed to analyze the quality of Plant Maintenance (PM) notifications. It consists of a Python/Flask backend that uses a Large Language Model for analysis and an SAP Fiori/UI5 frontend for the user interface.

Project Structure
.
├── approuter/         # Node.js App Router (serves UI, proxies to backend)
├── backend/           # Python Flask Backend
└── pm-analyzer-fiori/ # SAP Fiori Frontend

Application Overview
The PM Notification Quality Assistant aims to proactively enhance the quality of Plant Maintenance notifications, particularly in highly regulated environments like pharmaceutical production. By leveraging Artificial Intelligence, the application identifies deficiencies in documentation, provides actionable insights, and supports a continuous improvement process (KVP). It's designed for a range of users, ensuring that maintenance records are audit-proof and compliant with stringent data integrity principles (ALCOA+).

Note: This version of the application has authentication completely removed for simplified deployment and demonstration purposes.

Key Features
AI-Powered Quality Analysis: Automated evaluation of maintenance notification texts based on Good Manufacturing Practice (GMP) and ALCOA+ principles.

Quantitative Scoring: Each analysis provides a numerical quality score (0-100) for quick assessment.

Detailed Problem Identification: The AI highlights specific issues and gaps in the notification documentation.

Summarized Expert Assessment: A concise summary explains the AI's findings and recommendations.

Multi-language Support: The application supports analysis in both English and German, with the ability to switch languages in the frontend.

Notification Management: View, filter, and search through a list of PM notifications.

Detailed Notification View: Access comprehensive details of individual notifications and trigger on-demand AI analysis.

Visual Score Indicator: A clear visual indicator (progress bar with color coding) provides immediate feedback on the notification's quality score.

Architecture Deep Dive
The application follows a client-server architecture, with a distinct separation between the backend and frontend components, deployed as a Multi-Target Application (MTA) on SAP Business Technology Platform (BTP) Cloud Foundry.

Backend (Python/Flask)

The backend is a lightweight Flask application responsible for handling API requests and performing the core AI-driven text analysis.

Deployment Type: Deployed as a standard Cloud Foundry application (org.cloudfoundry.app type within the MTA).

main.py: The central Flask application file. It defines API routes (/health and /api/analyze), handles incoming requests, and orchestrates calls to the AI service. Authentication middleware has been removed.

app/services/analysis_service.py: Integrates with the Google Gemini API (gemini-1.5-flash-latest) for text analysis using a detailed prompt.

app/models.py: Defines Pydantic data models (AnalysisRequest, AnalysisResponse).

app/auth.py: Placeholder file; authentication logic has been removed.

Dockerfile: Used for local Docker-based development/testing, but not for the BTP Cloud Foundry deployment (which uses a buildpack).

requirements.txt: Lists Python dependencies, including uvicorn for serving the Flask app.

manifest.yml: Defines the Cloud Foundry application properties (buildpack, command, memory, disk, and fixed route).

Technology Stack: Flask, Pydantic, Google Gemini API, uvicorn.

Frontend (SAP Fiori/UI5)

The frontend is an SAP Fiori application built with SAP UI5, providing an intuitive and enterprise-grade user interface.

Deployment Type: The UI5 application's static content is embedded directly within the App Router's build artifact and served by the App Router itself. This bypasses the HTML5 Application Repository runtime service for the UI content.

App Router (approuter/): A Node.js application that acts as the single entry point. It serves the static Fiori UI content and proxies API calls to the backend via the Destination service. Authentication is completely disabled.

xs-app.json: Configures routing rules. It now includes a localDir route to serve the Fiori app's content directly from its embedded location (resources/pm-analyzer-fiori) and continues to proxy /api calls to the backend.

UI5 Application (pm-analyzer-fiori/webapp/):

index.html: The main entry point for the UI5 application; Auth0 script removed.

Component.js: Core UI5 component definition; Auth0 initialization and authentication logic removed.

Controllers (controller/): Handle UI logic and backend calls. All authentication-related logic (login/logout, token fetching) has been removed.

Views (view/): Define UI layout; authentication-related UI elements removed.

manifest.json: UI5 application descriptor. Updated to reflect no authentication and correct data source URLs.

ui5.yaml: UI5 tooling configuration. Configured to exclude auth0-spa-js.production.js from minification during generateComponentPreload.

ui5-deploy.yaml: UI5 deployment configuration for the build process.

package.json: Defines Node.js dependencies and build scripts. The build:cf script now builds the Fiori app and a postbuild:cf script copies the output into the App Router's directory.

Technology Stack: SAP UI5, Node.js App Router, Fetch API.

SAP BTP Deployment Strategy (CI/CD with GitHub Actions)

The application is deployed to SAP BTP Cloud Foundry using a GitHub Actions workflow.

mta.yaml (Project Root): The central Multi-Target Application descriptor.

Defines pm-analyzer-approuter (App Router), pm-analyzer-fiori (Fiori UI content module), and pm-analyzer-fiori-app-content (content deployer for HTML5 App Repo).

Backend as existing-service: The pm-analyzer-backend is declared as an org.cloudfoundry.existing-service resource. This means the backend application is pushed separately by cf push in the workflow.

UI as Embedded Content: The pm-analyzer-fiori module (type com.sap.application.content) is built directly into the App Router's artifact (target-path: resources/pm-analyzer-fiori), bypassing the HTML5 App Repo runtime service for the UI content.

Service Requirements: App Router requires pm-analyzer-destination and pm-analyzer-html5-repo-host.

.github/workflows/deploy.yml: GitHub Actions workflow orchestrates the deployment.

Prerequisites: Installs Node.js, CF CLI, multiapps plugin, jq, and mbt.

Backend Deployment:

Deletes any existing pm-analyzer-backend application for a clean push.

Pushes the pm-analyzer-backend application using cf push -f manifest.yml --no-route --no-start (route defined in backend/manifest.yml).

Starts the pm-analyzer-backend application using cf start.

MTA Deployment:

Builds the MTA archive (.mtar) using mbt build.

Moves the generated .mtar file to the correct location for cf deploy.

Deploys the MTA using cf deploy. This step creates/updates the App Router and deploys the Fiori UI content.

Route Management: The backend uses a fixed route defined in backend/manifest.yml. The App Router's route is automatically generated by BTP.

Manual Post-Deployment Steps:

Backend Destination: After successful deployment, you will need to manually create a Destination in your SAP BTP subaccount named pm-analyzer-backend. This destination should point to the URL of your deployed pm-analyzer-backend application (e.g., https://pm-analyzer-backend-dev.cfapps.<your-region>.hana.ondemand.com). This is how your App Router will find the backend.

Quick Start: Running the Application Locally
You will need two separate terminal windows to run both the backend and frontend servers simultaneously.

Prerequisites

Node.js (LTS version recommended)

Python 3.8+

A .env file in the backend/ directory containing GOOGLE_API_KEY for the analysis service.

1. Start the Backend Server

First, navigate to the backend directory and start the Python server.

# 1. Go to the backend directory
cd backend/

# 2. Create and activate a virtual environment (only once)
python3 -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
.\\venv\\Scripts\\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the backend server
python3 -m app.main

The backend will now be running on http://localhost:5001 (or the port specified in your .env).

2. Start the Frontend Application

In a new terminal window, navigate to the Fiori app directory and start the local development server.

# 1. Go to the Fiori app directory
cd pm-analyzer-fiori/

# 2. Install npm dependencies (only once)
npm install

# 3. Start the frontend server
# This will use ui5.yaml to proxy API requests to your local backend.
npx fiori run --open 'test/flpSandbox.html?sap-ui-xx-viewCache=false'

This command starts a local server and automatically opens your Fiori application in a web browser. The server is pre-configured in ui5.yaml to proxy API requests to your local backend.

