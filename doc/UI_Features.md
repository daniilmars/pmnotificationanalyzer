
# UI Features and Concepts

**Version:** 1.0
**Status:** As-Built Documentation

---

## 1. Solution Overview

The PM Notification Quality Suite is composed of three distinct frontend applications, providing a complete workflow for technicians, planners, and quality experts.

1.  **Suite Launchpad**: The central, unified entry point for all users.
2.  **Maintenance Execution Assistant**: The primary tool for maintenance personnel to view and analyze the quality of PM Notifications.
3.  **Rule Manager**: A dedicated application for Quality Assurance experts to configure the business logic that drives the quality analysis.

---

## 2. UI Design Concept

The UI for all applications is built using SAP's Fiori design language (SAPUI5), ensuring a consistent, enterprise-grade user experience.

### 2.1 Suite Launchpad

*   **Purpose:** To provide a simple and clear starting point for the entire suite.
*   **Layout:** A minimalist page centered around two main tiles.
*   **Components:**
    *   **Tile 1: Maintenance Execution Assistant:** Navigates the user to the analysis application.
    *   **Tile 2: Rule Manager:** Navigates the user to the rule management application.

### 2.2 Maintenance Execution Assistant (The Analyzer)

*   **Purpose:** To allow users to view a list of PM notifications and trigger a detailed quality analysis.
*   **View 1: Notification List:**
    *   Displays a filterable list of PM notifications.
    *   Each notification shows key information and a quality score.
*   **View 2: Notification Detail & Analysis:**
    *   Shows the full details of a selected notification.
    *   Features a "Quality Guardian" panel that displays the AI-generated analysis, including a quality score, a summary, and a list of identified problems.

### 2.3 Rule Manager

*   **Purpose:** To provide a comprehensive, user-friendly interface for managing the entire lifecycle of quality rules without writing any code.

*   **Screen 1: Ruleset Dashboard**
    *   **Layout:** A main dashboard showing a table of all rulesets.
    *   **Columns:** Ruleset Name, Assigned To (Notification Type), Status, and Version.
    *   **Actions:**
        *   **Create Ruleset:** Opens a dialog to create a new, empty ruleset.
        *   **Create New Version:** (Visible for "Active" rulesets) Creates a new "Draft" version from the active one, copying all rules.
        *   **Edit:** (Visible for "Draft" rulesets) Allows editing the metadata of a draft.
        *   **Activate:** (Visible for "Draft" rulesets) Promotes a draft to become the new active version.
        *   **Delete:** (Visible for "Draft" rulesets) Deletes a draft ruleset.

*   **Screen 2: Rule Editor**
    *   **Layout:** A detail page for a single ruleset, showing a table of its individual rules.
    *   **Columns:** Rule Name, Description, Rule Type, Target Field, Condition, Value, Score Impact.
    *   **Actions (Visible only for Draft rulesets):**
        *   **Create Rule:** Opens a dynamic dialog to add a new rule.
        *   **Edit Rule:** Opens the same dialog pre-filled with the rule's data.
        *   **Delete Rule:** Deletes a rule after confirmation.

*   **Component: Dynamic Rule Dialog**
    *   **Context-Aware Form:** The dialog for creating and editing rules is dynamic.
    *   When **"Rule Type"** is set to **"VALIDATION"**, it shows fields for Target, Condition, Value, etc.
    *   When **"Rule Type"** is set to **"AI_GUIDANCE"**, it hides the irrelevant fields, showing only Name and Description.

*   **Component: SOP Assistant**
    *   A dialog-based workflow that allows users to upload a PDF SOP.
    *   The backend uses the Gemini API to extract potential rules from the document.
    *   The user is then navigated to a review screen to approve, edit, or reject the AI-generated suggestions.