# Project Onboarding: PM Notification Analyzer

- **Project Overview:** A full-stack application to analyze the quality of Plant Maintenance (PM) notifications using an LLM.
- **Tech Stack:**
  - **Backend:** Python, Flask, Gunicorn
  - **Frontend:** SAP Fiori (SAPUI5)
  - **Deployment:** SAP BTP, Cloud Foundry
- **Key Files:**
  - `backend/app/main.py`: Main Flask application routes.
  - `backend/app/services/analysis_service.py`: Core LLM integration logic.
  - `pm-analyzer-fiori/webapp/manifest.json`: Fiori app configuration.
  - `pm-analyzer-fiori/webapp/controller/Object.controller.js`: Detail view logic.
- **Development Conventions:**
  - Backend follows standard Flask patterns.
  - Frontend uses modern SAPUI5 asynchronous patterns.
  - All code must be formatted and linted before commit (tooling to be defined).
