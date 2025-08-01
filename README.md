PM Notification Quality Assistant
This project is a full-stack application designed to analyze the quality of Plant Maintenance (PM) notifications. It consists of a Python/Flask backend that uses a Large Language Model for analysis and an SAP Fiori/UI5 frontend for the user interface.

Project Structure
.
├── backend/         # Python Flask Backend
└── pm-analyzer-fiori/ # SAP Fiori Frontend

Application Overview
The PM Notification Quality Assistant aims to proactively enhance the quality of Plant Maintenance notifications, particularly in highly regulated environments like pharmaceutical production. By leveraging Artificial Intelligence, the application identifies deficiencies in documentation, provides actionable insights, and supports a continuous improvement process (KVP). It's designed for a range of users, from maintenance technicians and quality managers to GMP auditors, ensuring that maintenance records are audit-proof and compliant with stringent data integrity principles (ALCOA+).

Key Features
AI-Powered Quality Analysis: Automated evaluation of maintenance notification texts based on Good Manufacturing Practice (GMP) and ALCOA+ principles.

Quantitative Scoring: Each analysis provides a numerical quality score (0-100) for quick assessment.

Detailed Problem Identification: The AI highlights specific issues and gaps in the notification documentation.

Summarized Expert Assessment: A concise summary explains the AI's findings and recommendations.

Multi-language Support: The application supports analysis in both English and German, with the ability to switch languages in the frontend.

User Authentication: Secure access to the application and its analysis capabilities via Auth0.

Notification Management: View, filter, and search through a list of PM notifications.

Detailed Notification View: Access comprehensive details of individual notifications and trigger on-demand AI analysis.

Visual Score Indicator: A clear visual indicator (progress bar with color coding) provides immediate feedback on the notification's quality score.

Architecture Deep Dive
The application follows a client-server architecture, with a distinct separation between the backend and frontend components.

Backend (Python/Flask)

The backend is a lightweight Flask application responsible for handling API requests, authenticating users, and performing the core AI-driven text analysis.

main.py: The central Flask application file. It defines API routes (/health for status checks and /api/analyze for text analysis), handles incoming requests, and orchestrates calls to other services. It includes robust error handling and integrates the authentication decorator.

app/services/analysis_service.py: This is where the AI magic happens. It integrates with the Google Gemini API (gemini-1.5-flash-latest) to analyze the input text. It uses a meticulously crafted prompt that instructs the AI to act as a GMP auditor, applying a predefined scoring matrix based on GMP and ALCOA+ principles. It also parses the AI's raw text response into a structured format.

app/auth.py: Implements the authentication logic. It uses the python-jose library to validate JSON Web Tokens (JWTs) received from the frontend against Auth0's public keys (JWKS). It includes caching for JWKS to optimize performance and ensures secure access to protected API endpoints via the @token_required decorator.

app/models.py: Defines Pydantic BaseModel classes for AnalysisRequest (input payload for analysis) and AnalysisResponse (structured output from the analysis service), ensuring clear data contracts and validation.

Technology Stack: Flask, Pydantic, python-jose, Google Gemini API, dotenv for environment variable management.

Frontend (SAP Fiori/UI5)

The frontend is an SAP Fiori application built with SAP UI5, providing an intuitive and enterprise-grade user interface.

webapp/controller/App.controller.js: The main application controller, typically used for global initialization logic.

webapp/controller/BaseController.js: A base controller providing common utility functions, such as getRouter, for other controllers to extend.

webapp/controller/Login.controller.js: Manages the login process. It uses the Auth0 client to initiate a login redirect, ensuring users are authenticated before accessing the application's features.

webapp/controller/Worklist.controller.js: Controls the main list view of PM notifications. It populates filter options (creators, types, locations, equipment) dynamically from the loaded data. It handles filtering and searching of notifications and manages language changes. It also handles navigation to the detailed Object view.

webapp/controller/Object.controller.js: Manages the detailed view of a single PM notification. It collects relevant text fields (description, long text, activities) and sends them to the backend's /api/analyze endpoint for AI analysis, including the selected language. It then displays the structured analysis results (score, problems, summary) and updates a visual progress indicator based on the score.

webapp/view/Login.view.xml: Defines the user interface for the login page, featuring a prominent login button.

webapp/view/Worklist.view.xml: Lays out the worklist page, including a header with user information, logout button, and language selector. It contains a filter bar with various input controls (SearchField, ComboBoxes) and a List control to display PM notifications using ObjectListItems.

webapp/view/Object.view.xml: Designs the detailed notification view. It uses SimpleForm to display notification attributes and TextArea for inputting long text and activities. It includes an "Analyze" button and a Panel to show the AI analysis results, complete with a ProgressIndicator for the score, a List for identified problems, and a Text control for the summary.

Technology Stack: SAP UI5, Auth0 SDK (implicitly used via Component.js), Fetch API for backend communication, sap.m and sap.ui.layout libraries for UI controls.

User Interface (UI) Walkthrough
The application provides a streamlined user experience across its different views:

Login Page:

A clean, centered page with a welcoming title and an introductory text.

A single, emphasized "Login" button (sap-icon://log) to initiate the authentication flow.

Worklist Page:

Header: Displays the authenticated user's name, a "Logout" button, and a language selection dropdown (English/Deutsch).

Filter Bar: A powerful tool for narrowing down the list of notifications. Users can:

Search for keywords in the "Short Text" of notifications.

Filter by "Notification Type" (e.g., M1, M2).

Filter by "Created By" user.

Filter by "Functional Location".

Filter by "Equipment".

"Restore" and "Clear" buttons are available for filter management.

Notification List: Displays PM notifications as ObjectListItems, showing:

Notification ID and Description as the title.

Attributes like Functional Location, Equipment, Type, Created By, and Creation Date.

Interaction: Tapping on any notification item navigates the user to the detailed "Object" view.

Object Detail Page:

Header: Features a dynamic title that includes the Notification ID and a "Back" button to return to the Worklist.

Notification Details: Presents all relevant information about the selected notification in a clear, readable form, including:

Description, Functional Location, Equipment.

Notification Type and the user who created it.

"Long Text" and "Activities" are displayed in text areas, allowing for easy review.

Analyze Button: A prominent "Analyze" button (sap-icon://activate) triggers the AI analysis of the notification's content.

Analysis Results Panel: This section becomes visible after the analysis is performed. It's an expandable panel that shows:

Score: A ProgressIndicator visually represents the quality score (e.g., "95/100"). The indicator's color dynamically changes to green (Success), yellow (Warning), or red (Error) based on the score, providing immediate visual feedback.

Problems: A list of specific issues identified by the AI in the notification text.

Summary: A concise textual summary of the AI's overall assessment.

Quick Start: Running the Application Locally
You will need two separate terminal windows to run both the backend and frontend servers simultaneously.

Prerequisites

Node.js (LTS version recommended)

Python 3.8+

A .env file in the backend/ directory containing the following keys:

GOOGLE_API_KEY (for the analysis service)

AUTH0_DOMAIN and API_AUDIENCE (from your Auth0 API settings)

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

The backend will now be running on http://localhost:5000.

2. Start the Frontend Application

In a new terminal window, navigate to the Fiori app directory and start the local development server.

# 1. Go to the Fiori app directory
cd pm-analyzer-fiori/

# 2. Install npm dependencies (only once)
npm install

# 3. Start the frontend server
npx fiori run --open

This command starts a local server and automatically opens your Fiori application in a web browser. The server is pre-configured in ui5.yaml to proxy API requests to your local backend.


Recommended Project Structure for SAP BTP Deployment
For deployment to SAP BTP as a Multi-Target Application (MTA), your project should be organized to clearly separate the different components (frontend, backend) and their respective build artifacts. The mta.yaml file at the project root acts as the blueprint for how these components are assembled and deployed.

.
├── .github/                     # GitHub Actions workflows for CI/CD
│   └── workflows/
│       └── deploy.yml           # Workflow for building and deploying to BTP
├── backend/                     # Python Flask Backend Module
│   ├── app/                     # Flask application source code
│   │   ├── auth.py              # Authentication logic
│   │   ├── main.py              # Main Flask app, API routes
│   │   ├── models.py            # Pydantic data models
│   │   └── services/            # Business logic, e.g., analysis_service.py
│   │       └── analysis_service.py
│   ├── Dockerfile               # Dockerfile for containerizing the backend
│   ├── requirements.txt         # Python dependencies
│   ├── run.py                   # Entry point script (optional, can be in Dockerfile)
│   ├── scripts/                 # Utility scripts (e.g., test data generation)
│   │   ├── __init__.py
│   │   ├── generate_test_data.py
│   │   └── local_test.py
│   └── tests/                   # Unit/integration tests for backend
│       ├── __init__.py
│       └── services/
├── pm-analyzer-fiori/           # SAP Fiori/UI5 Frontend Module
│   ├── webapp/                  # UI5 application source code
│   │   ├── Component.js         # UI5 component definition
│   │   ├── config.json          # Frontend configuration
│   │   ├── controller/          # UI5 controllers
│   │   │   ├── App.controller.js
│   │   │   ├── BaseController.js
│   │   │   ├── Login.controller.js
│   │   │   ├── Object.controller.js
│   │   │   ├── View1.controller.js
│   │   │   └── Worklist.controller.js
│   │   ├── css/                 # Custom CSS files
│   │   ├── i18n/                # Internationalization (i18n) resource bundles
│   │   │   ├── i18n.properties
│   │   │   ├── i18n_de.properties
│   │   │   └── i18n_en.properties
│   │   ├── index.html           # Main HTML entry point for local development
│   │   ├── libs/                # External UI5 libraries (if any)
│   │   ├── localService/        # Local mock data/services for UI5 development
│   │   │   └── mockdata.json
│   │   ├── manifest.json        # UI5 application descriptor
│   │   ├── mock_data_de.json    # Localized mock data for frontend
│   │   ├── mock_data_en.json    # Localized mock data for frontend
│   │   ├── model/               # UI5 models (e.g., formatter.js)
│   │   │   └── formatter.js
│   │   └── view/                # UI5 views (XML)
│   │       ├── App.view.xml
│   │       ├── Login.view.xml
│   │       ├── Object.view.xml
│   │       ├── View1.view.xml
│   │       └── Worklist.view.xml
│   ├── mta.yaml                 # MTA descriptor for the Fiori app (will be merged into root mta.yaml)
│   ├── package.json             # Node.js dependencies for UI5 build
│   ├── package-lock.json        # Locked Node.js dependencies
│   ├── README.md                # Frontend specific README (optional)
│   ├── ui5-deploy.yaml           # UI5 deployment configuration
│   ├── ui5-local.yaml           # UI5 local development configuration
│   ├── ui5-mock.yaml            # UI5 mock server configuration
│   ├── ui5.yaml                 # UI5 tooling configuration
│   ├── xs-app.json              # App Router configuration
│   └── xs-security.json         # XSUAA security descriptor for the frontend
├── .gitignore                   # Specifies intentionally untracked files
├── mta.yaml                     # **Main Multi-Target Application (MTA) descriptor**
├── project_structure.txt        # (Your temporary file)
├── README.md                    # Overall project README
└── venv/                        # Python virtual environment (ignored by Git)

Key Principles and Best Practices

Single MTA Project (mta.yaml at Root):

The most critical file for BTP deployment is the mta.yaml at the project root. This file defines all the modules (your Fiori app, your Python backend, and any required services like XSUAA, Destination, HTML5 Application Repository).

It specifies how each module is built, what resources it consumes, and how they relate to each other.

Your current mta.yaml is inside pm-analyzer-fiori/. For a multi-module MTA, it's best practice to have the main mta.yaml at the project root (.) and then reference the sub-modules. The pm-analyzer-fiori/mta.yaml can be used for local fiori run commands or as a sub-descriptor that gets merged by the main one. However, for CI/CD, a single root mta.yaml is cleaner.

Modularization:

Each distinct part of your application (frontend, backend) should reside in its own top-level directory (e.g., pm-analyzer-fiori/, backend/).

This promotes clear separation of concerns, independent development, and easier management.

Frontend (SAP Fiori/UI5) Best Practices:

webapp/: This is the standard directory for UI5 application source code. All UI5-specific files (views, controllers, models, i18n, manifest.json) belong here.

manifest.json: The application descriptor. It defines the app's metadata, dependencies, routing, and data sources. Crucially, it will define the backend service as a dataSource and reference the xsuaa and destination services.

xs-app.json: Used by the App Router (a BTP service) to define routing rules, including forwarding API calls to your backend service.

xs-security.json: Defines the security configuration for your XSUAA service, including scopes and role templates.

ui5.yaml files: These are for UI5 tooling (local development, mock server, build). They are essential for local development but usually not directly part of the deployed artifact (their build output is).

Build Process: The mta.yaml will define an html5 module type that uses npm install and npm run build:cf (or similar) to create the deployable dist folder.

Backend (Python/Flask) Best Practices:

Dockerfile: Essential for containerizing your Python application. This allows it to be deployed as a Cloud Foundry docker application type. The Dockerfile should specify the base image, install dependencies, copy your application code, and define the command to run your Flask app.

requirements.txt: Lists all Python dependencies. This is used by the Dockerfile to install packages.

app/ directory: Contains your core Flask application code, separated into logical modules (auth, models, services).

Environment Variables: Ensure sensitive information (like GOOGLE_API_KEY, AUTH0_DOMAIN, API_AUDIENCE) is read from environment variables (e.g., using python-dotenv locally) and managed as service bindings or user-provided variables in BTP.

No Hardcoding: Avoid hardcoding URLs or credentials. Use relative paths or environment variables for service discovery in BTP.

Service Bindings and Resources in mta.yaml:

xsuaa: Your frontend will bind to an XSUAA service for authentication and authorization.

destination: If your frontend needs to call external services (like your backend, if it's deployed separately or needs dynamic routing), a Destination service can be used.

app-router: The SAP HTML5 Application Repository service typically requires an App Router to serve your UI5 application and handle authentication and routing to backend services.

Backend as a Service: Your Python backend will be defined as a backend module in mta.yaml, likely of type com.sap.xs.hdi-container or org.cloudfoundry.user-provided-service if you manage the database externally. For a simple Flask app, org.cloudfoundry.app or com.sap.xs.nodejs (if using a Node.js buildpack) or a custom buildpack/docker image is used. In your case, a docker type for the backend is appropriate.

