# Project Onboarding: PM Notification Quality Suite

- **Project Overview:** A suite of full-stack applications designed to analyze and manage the quality of Plant Maintenance (PM) notifications.
- **Tech Stack:**
  - **Backend:** Python, Flask, Gunicorn
  - **Frontend:** SAP Fiori (SAPUI5)
  - **Deployment:** SAP BTP, Cloud Foundry (via Docker)
- **Key Files & Directories:**
  - `launchpad/`: The main entry point for the application suite.
  - `pm-analyzer/`: Contains the "Maintenance Execution Assistant" application.
  - `rule-manager/`: Contains the "Rule Manager" application.
  - `docker-compose.yml`: Defines all the services and their orchestration for local development.
  - `README.md`: The main source of truth for project setup and architecture.
- **Development Conventions:**
  - The project uses a microservices architecture.
  - Backend services follow standard Flask patterns.
  - Frontend applications use modern SAPUI5 asynchronous patterns.
  - All code must be formatted and linted before commit (tooling to be defined).
