# Gemini CLI Interaction Protocol

## 1. Purpose

This document outlines a standardized protocol for interacting with the Gemini CLI agent. The goal is to maximize efficiency, ensure clarity in communication, and maintain a structured, well-documented development process. Adhering to this protocol will enable the agent to understand context faster, perform tasks more accurately, and create a persistent knowledge base for the project.

## 2. Core Principles

- **Clarity is Key:** The agent's effectiveness is directly proportional to the clarity of the user's requests. Vague goals will lead to ambiguous results.
- **Context is King:** The more context the agent has, the better it can align with project conventions, architecture, and goals.
- **Iterative Approach:** Complex tasks should be broken down into smaller, verifiable steps. The user's role is to guide and validate these steps.
- **You are the Architect:** The user is the final authority on architectural decisions, coding standards, and feature acceptance. The agent is a highly skilled implementer and assistant.

## 3. The Development Workflow

We will follow a five-phase workflow for any significant task (e.g., new features, complex bug fixes, refactoring).

### Phase 1: Onboarding & Context Sync

**Goal:** To provide the agent with the necessary context to understand the project or a specific task.

**Procedure:**
1.  For a new project, a user should create an `ONBOARDING.md` file in this `doc/` directory.
2.  This file should contain a high-level overview of the project, the tech stack, key architectural patterns, and pointers to critical files.
3.  When starting a session, the first command should be: `"Screen the project, starting with doc/ONBOARDING.md and README.md"`
4.  The agent will use this to build its initial understanding.

*(See Appendix A for the `ONBOARDING.md` template.)*

### Phase 2: Task Definition

**Goal:** To provide a clear, unambiguous definition of the task to be performed.

**Procedure:**
1.  For any new task, the user will provide a concise but complete task definition, ideally following a template.
2.  The prompt should be structured to include a summary, acceptance criteria, and any constraints.

*(See Appendix B for the `TASK_TEMPLATE.md` format.)*

### Phase 3: Implementation & Collaboration

**Goal:** The agent executes the task while the user supervises and provides clarification.

**Procedure:**
1.  **Agent:** Upon receiving a task, the agent will formulate a high-level plan and share it (often using the `write_todos` tool).
2.  **Agent:** The agent proceeds with the implementation, using its tools to read, write, and test code. It will explain critical or potentially destructive commands before execution.
3.  **User:** The user's role is to monitor the agent's actions, approve or deny tool calls, and answer clarifying questions from the agent if it gets stuck.

### Phase 4: User Verification

**Goal:** The user validates that the implemented solution meets the acceptance criteria.

**Procedure:**
1.  Once the agent reports completion, the user is responsible for the final verification.
2.  This may include:
    -   Running the application and performing manual tests.
    -   Executing the full test suite (`npm test`, `pytest`, etc.).
    -   Reviewing the generated code for style and correctness.
3.  The user provides feedback for any necessary revisions.

### Phase 5: Decision Logging

**Goal:** To document key decisions made during the development process for future reference.

**Procedure:**
1.  When a non-trivial decision is made (e.g., choosing a library, opting for a specific architectural pattern), it should be recorded.
2.  The user can instruct the agent: `"Log the following decision: <decision details>"`
3.  The agent will append the decision to a central `DECISION_LOG.md` file.

*(See Appendix C for the `DECISION_LOG.md` format.)*

---

## Appendix

### Appendix A: `ONBOARDING.md` Template

*(To be created at `doc/ONBOARDING.md`)*

```markdown
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
```

### Appendix B: `TASK_TEMPLATE.md` Format

*(Use this structure in your prompts)*

```markdown
**Task:** Add a "Copy to Clipboard" Button

**Acceptance Criteria:**
- A button labeled "Copy" is visible next to the "Long Text" field in the Object View.
- Clicking the button copies the entire content of the "Long Text" field to the user's clipboard.
- A confirmation message (e.g., a Toast) appears briefly to confirm the text was copied.

**Constraints:**
- Use only standard SAPUI5 APIs. Do not add any new libraries.
```

### Appendix C: `DECISION_LOG.md` Format

*(To be created at `doc/DECISION_LOG.md`)*

```markdown
# Decision Log

---
**Date:** 2025-11-16
**Context:** Selecting a deployment pattern for the Fiori UI.
**Decision:** The UI5 static content will be embedded directly within the App Router's build artifact and served by the App Router itself.
**Rationale:** This robust pattern bypasses the need for the HTML5 Application Repository service, simplifying deployment and configuration on SAP BTP.
```
