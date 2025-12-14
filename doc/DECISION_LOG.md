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

---
**Date:** 2025-12-14
**Context:** Project Architecture Evolution.
**Decision:** 
1. **Suite Architecture:** Restructured the project into a microservices suite with a central "Suite Launchpad" entry point and two distinct applications ("Maintenance Execution Assistant" and "Rule Manager").
2. **Docker Compose:** Adopted Docker Compose as the primary orchestration tool for local development to manage the increased number of services (5 total).
**Rationale:** The split mode was becoming unwieldy to manage manually. A unified launchpad provides a better user experience, and Docker Compose ensures consistent environments across services.

---
**Date:** 2025-12-14
**Context:** AI Model and SDK Selection.
**Decision:** Migrated from `google.generativeai` (GenAI SDK) to `vertexai` (Vertex AI SDK) for both the Rule Manager (SOP Assistant) and PM Analyzer.
**Rationale:** Vertex AI offers better enterprise-grade features, compliance controls, and integration with Google Cloud Platform, which is suitable for the project's GMP goals.

---
**Date:** 2025-12-14
**Context:** Rule Engine Data Model.
**Decision:** Formalized two distinct rule types: "Validation" (deterministic checks on fields) and "AI Guidance" (semantic instructions for the LLM).
**Rationale:** Purely deterministic rules were insufficient for complex quality checks, while pure AI rules lacked precision. A hybrid model allows for both rigid compliance checks and flexible quality assessment.