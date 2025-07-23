# PM Notification Quality Assistant

This project is a full-stack application designed to analyze the quality of Plant Maintenance (PM) notifications. It consists of a Python/Flask backend that uses a Large Language Model for analysis and an SAP Fiori/UI5 frontend for the user interface.

## Project Structure

```
.
├── backend/         # Python Flask Backend
└── pm-analyzer-fiori/ # SAP Fiori Frontend
```

## Quick Start: Running the Application Locally

You will need two separate terminal windows to run both the backend and frontend servers simultaneously.

### Prerequisites

- [Node.js](https://nodejs.org/) (LTS version recommended)
- [Python 3.8+](https://www.python.org/)
- A `.env` file in the `backend/` directory containing the following keys:
  - `GOOGLE_API_KEY` (for the analysis service)
  - `AUTH0_DOMAIN` and `API_AUDIENCE` (from your Auth0 API settings)

### 1. Start the Backend Server

First, navigate to the backend directory and start the Python server.

```bash
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
```
The backend will now be running on `http://localhost:5000`.

### 2. Start the Frontend Application

In a **new terminal window**, navigate to the Fiori app directory and start the local development server.

```bash
# 1. Go to the Fiori app directory
cd pm-analyzer-fiori/

# 2. Install npm dependencies (only once)
npm install

# 3. Start the frontend server
npx fiori run --open
```
This command starts a local server and automatically opens your Fiori application in a web browser. The server is pre-configured in `ui5.yaml` to proxy API requests to your local backend.