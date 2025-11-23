# Decision Log

---
**Date:** 2025-11-16
**Context:** Selecting a deployment pattern for the Fiori UI.
**Decision:** The UI5 static content will be embedded directly within the App Router's build artifact and served by the App Router itself.
**Rationale:** This robust pattern bypasses the need for the HTML5 Application Repository service, simplifying deployment and configuration on SAP BTP.

---
**Date:** 2025-11-23
**Context:** Backend cleanup and configuration alignment.
**Decision:** 
1. Removed `backend/vendor` (macOS-specific wheels) to ensure clean, platform-independent installs via `requirements.txt`.
2. Removed `backend/scripts` and `backend/tests` to simplify the project structure as they were deemed unnecessary for the current scope.
3. Updated `backend/run.py` to listen on port 5001, aligning with the `ui5.yaml` proxy configuration.
**Rationale:** Eliminates potential deployment conflicts (wrong architecture wheels), reduces project noise, and ensures immediate local connectivity between Frontend and Backend.