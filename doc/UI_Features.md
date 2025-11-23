# Technical Design Specification
## Project: SAP PM Intelligent Reliability Workspace
**Version:** 2.0 (State of the Art Redesign)  
**Target Platform:** SAP BTP (Business Technology Platform) / SAP S/4HANA (Fiori Launchpad)

---

## 1. Executive Summary
The **Intelligent Reliability Workspace** is a unified frontend application designed to replace the fragmented standard SAP GUI transactions (IW21/22/28 and IW31/32/38). It merges **Notification (Problem Definition)** and **Order (Resolution Planning & Execution)** into a single lifecycle view.

The core differentiator is the **"Quality Guardian,"** an active AI agent that ensures data entry meets GMP/ALCOA+ standards in real-time, preventing poor data quality ("Garbage In") rather than reporting on it later.

---

## 2. Solution Architecture

### 2.1 High-Level Architecture
*   **Frontend:** SAPUI5 (Custom Control) or React (via SAP Cloud Application Programming Model - CAP).
*   **Middleware:** SAP BTP (Cloud Foundry) for orchestration and AI services.
*   **Backend:** SAP S/4HANA or SAP ECC 6.0 (EHP7+).
*   **Integration Layer:** OData V4 Services (RAP/CAP) wrapping standard BAPIs.

### 2.2 Functional Roles
1.  **The Planner/Gatekeeper:** Desktop-focused. Heavily uses the Planning & Material views.
2.  **The Technician:** Tablet/Mobile-focused. Uses Execution, Voice-to-Text, and Camera features.

---

## 3. User Interface (UI) Design Concept

The UI abandons the traditional "Tab Strip" in favor of a **Three-Pane "Command Center" Layout**.

### 3.1 Pane 1: Context & Navigation (Left Sidebar - 20% Width)
*   **Purpose:** Persistent context of *what* is being worked on.
*   **Components:**
    *   **Asset Card:** Thumbnail of Equipment, Functional Location, Current Status (System Status).
    *   **Visual Digital Twin:** A 2D SVG or 3D Viewer of the asset. Clicking a component (e.g., "Motor") highlights it and pre-filters catalog codes.
    *   **Risk Profile:** Badges showing "GMP Critical", "Safety Critical", or "Bad Actor" (high frequency of failure).

### 3.2 Pane 2: The Workspace (Center - 55% Width)
*   **Purpose:** The dynamic working area. It changes views based on the Lifecycle Phase.
*   **View A: Definition (Triage):**
    *   Subject & Long Text (Smart Editor).
    *   Object Part / Damage Code selection.
*   **View B: Planning (The "Amazon" Experience):**
    *   **Operations List:** Drag-and-drop interface.
    *   **Visual BOM:** Exploded view of the machine. Clicking a part checks stock (ATP) and adds to the shopping cart (Reservation).
*   **View C: Execution (Technician View):**
    *   Large, touch-friendly cards for Operations.
    *   Time Confirmation Start/Stop buttons.
    *   Media Upload (Before/After photos).

### 3.3 Pane 3: The Quality Guardian (Right Sidebar - 25% Width)
*   **Purpose:** Always-on AI assistant (replaces the "Qualitätsanalyse" tab).
*   **Components:**
    *   **Live Quality Score:** A gauge (0-100%) updating with every keystroke.
    *   **Actionable Insights:** "You selected 'Leak' but didn't specify 'Seal' as the object. Fix now?"
    *   **Chat Interface:** "Show me the last 3 repairs on this motor."

---

## 4. Functional Modules & Technical Logic

### 4.1 Module: Smart Planning & Materials (Visual BOM)
Instead of searching `MARA` tables by text, the user interacts with a visual hierarchy.
*   **Logic:**
    1.  Fetch Equipment ID (`EQUI`).
    2.  Determine Construction Type (`EQMT_BOM`).
    3.  Load BOM Items (`STPO`) and merge with Material Master (`MARA`) for descriptions.
    4.  **Stock Check:** Call `BAPI_MATERIAL_AVAILABILITY` on selection.
    5.  **Action:** On "Add," create entry in `RESB` (Reservation) linked to the `AUFK` (Order).

### 4.2 Module: Execution & Activity Documentation
Standard `QMAK` (Activities) input is tedious. We replace it with **Voice-to-Record**.
*   **Workflow:**
    1.  Technician dictates: *"Replaced the sealing ring on the main valve."*
    2.  **STT (Speech-to-Text):** Transcribes audio.
    3.  **NLP Parsing:** Recognizes "Replaced" (Activity Code) and "Sealing Ring" (Object Part).
    4.  **Auto-Populate:**
        *   Updates Notification Activities (`QMAK`).
        *   Updates Order Confirmation Longtext (`AFRU`).
        *   Sets Status to `CNF` (Confirmed).

### 4.3 Module: The "Quality Guardian" (AI Layer)
This runs ALCOA+ checks in the background.
*   **Validation Rules (Engine):**
    *   *Completeness:* Does `QMFE` (Damage) exist? Is `QMUR` (Cause) linked?
    *   *Coherence:* Does the Long Text contain keywords matching the Codes? (e.g., Text says "broken", Code says "electrical fault" -> mismatch).
    *   *Traceability:* Are uploaded photos tagged with metadata (User, Timestamp, Geo-location)?

---

## 5. Data Model & Integration Map

This section maps the UI features to specific SAP Backend Tables and BAPIs.

### 5.1 The Problem (Notification)
| UI Component | SAP Table | Field Description | Write Method (BAPI) |
| :--- | :--- | :--- | :--- |
| Header Data | **QMEL** | Equipment, FunctLoc, Priority, ReportedBy | `BAPI_ALM_NOTIF_CREATE` |
| Description | **STXH / STXL** | Long Text (The narrative) | `BAPI_ALM_NOTIF_SAVE` |
| Defect Coding | **QMFE** | Item (Object Part, Damage Code) | `BAPI_ALM_NOTIF_DATA_ADD` |
| Root Cause | **QMUR** | Cause Codes (Why it happened) | `BAPI_ALM_NOTIF_DATA_ADD` |
| Activities | **QMAK** | What was done (The immediate fix) | `BAPI_ALM_NOTIF_DATA_ADD` |

### 5.2 The Plan & Execution (Order)
| UI Component | SAP Table | Field Description | Write Method (BAPI) |
| :--- | :--- | :--- | :--- |
| Order Header | **AUFK** | Order Type, Dates, Status | `BAPI_ALM_ORDER_MAINTAIN` |
| Operations | **AFVC** | Work steps, Control keys (Steuerschlüssel) | `BAPI_ALM_ORDER_MAINTAIN` |
| Materials | **RESB** | Reservations (Spare parts) | `BAPI_ALM_ORDER_MAINTAIN` |
| Time Confirm | **AFRU** | Actual hours, Technician ID | `BAPI_ALM_CONF_CREATE` |
| Status Flow | **JEST** | User Status / System Status (REL, TECO) | `STATUS_CHANGE_EXTERN` |

### 5.3 Documents & Media
| UI Component | SAP Table | Logic |
| :--- | :--- | :--- |
| Attachments | **SRGBTBREL** | Links Business Object to Attachment |
| Storage | **KPRO / DMS** | Physical storage (Content Server) |
| Method | **GOS (Generic Object Services)** | Use `BDS_BUSINESSDOCUMENT_CREATE` to attach photos to the Notification ID. |

---

## 6. Implementation Strategy

### 6.1 Phase 1: The "Digital Wrapper" (MVP)
*   **Goal:** Read-only "Quality Analysis" + Basic Edit.
*   **Tech:** SAPUI5 application consuming `C_MaintNotificationTP` CDS View.
*   **Feature:** Implement the "Quality Score" logic in JavaScript on the frontend.

### 6.2 Phase 2: The "Unified Workspace"
*   **Goal:** Merge Order and Notification.
*   **Tech:** Implement `BAPI_ALM_ORDER_MAINTAIN`.
*   **Feature:** Drag-and-drop operations and Visual BOM.

### 6.3 Phase 3: The "AI Integration"
*   **Goal:** Generative AI for text and image analysis.
*   **Tech:** Connect to SAP Generative AI Hub (via BTP).
*   **Feature:** "Rewrite for GMP" button and Auto-Coding suggestions.

---

## 7. Sample API Payload (JSON)
*Example: Creating a unified entry (Notification + Order + Material).*

```json
{
  "NotificationHeader": {
    "Equipment": "10005678",
    "ShortText": "Tablet Press #3 - Force Feeder Drift",
    "Priority": "1",
    "Items": [
      {
        "ItemSortNo": "0001",
        "Descript": "Force Feeder Sensor",
        "ObjectPart": "SENSOR",
        "DamageCode": "DRIFT"
      }
    ]
  },
  "OrderOperation": [
    {
      "Activity": "0010",
      "ControlKey": "PM01",
      "Description": "Calibrate Sensor",
      "WorkCenter": "INST-MECH",
      "Duration": "1.5",
      "DurationUnit": "H"
    }
  ],
  "Components": [
    {
      "Material": "500-100-ABC",
      "RequirementQuantity": "1",
      "ItemCategory": "L" // Stock Item
    }
  ]
}
```

## 8. Compliance & Validation (ALCOA+)
*   **Attributable:** Every action (edit, status change) logs the User ID via SAP Change Documents (`CDHDR`/`CDPOS`).
*   **Legible:** Long texts are rendered in readable fonts; history is preserved.
*   **Contemporaneous:** Time confirmations (`AFRU`) must be within X hours of the actual work (validated by UI logic).
*   **Original:** The first entry is preserved; edits are versioned.
*   **Accurate:** The "Quality Guardian" enforces mandatory fields based on Equipment Classification.