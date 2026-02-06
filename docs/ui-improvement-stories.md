# UI/UX Improvement User Stories

> **Date:** 2026-02-06
> **Audit method:** Playwright automated screenshots of all views at 1440x900/1920x1080
> **Current state:** SAP Horizon theme, ShellBar added, basic Fiori controls in place

---

## Personas

| Persona | Role | Goals |
|---------|------|-------|
| **Maria** | Maintenance Planner | Reviews PM notifications daily, needs to quickly identify quality issues and act on them |
| **Thomas** | Quality Manager | Monitors ALCOA+ compliance trends, exports audit reports for regulators |
| **Elena** | Reliability Engineer | Analyzes equipment failure patterns, uses MTBF/MTTR data for predictive maintenance |
| **Jan** | Rule Administrator | Creates and maintains quality rulesets, manages rule lifecycle (Draft > Active > Retired) |
| **Auditor** | External Auditor | Needs clean audit trails with FDA 21 CFR Part 11 compliance evidence |

---

## P0 — Critical Bugs

### US-01: Quality Dashboard renders blank page
**As** Thomas (Quality Manager), **I want** the Quality Dashboard to load and display KPI tiles, trend charts, and ALCOA+ compliance data **so that** I can monitor overall notification quality.

**Current behavior:** Navigating to `#/QualityDashboard` shows only the ShellBar and an empty page — no tiles, no panels, no content at all.
**Expected:** 6 KPI tiles (Overall Quality Score, Total Notifications, Completeness, Accuracy, Timeliness, ALCOA+), trend chart, distribution panel, ALCOA+ details table, Common Issues, and Recommendations.
**Root cause hypothesis:** The `sap.suite.ui.microchart` library (RadialMicroChart, InteractiveLineChart, HarveyBallMicroChart) may fail to load silently, or the API call in `_loadDashboardData()` returns an error that is swallowed.
**Acceptance criteria:**
- [ ] Quality Dashboard renders all 6 KPI tiles
- [ ] Trend chart and score distribution panel are visible
- [ ] ALCOA+ compliance table shows data
- [ ] Period selector (7/30/90 days) triggers a data reload

### US-02: Audit Dashboard returns UNAUTHORIZED error
**As** an Auditor, **I want** the Audit Trail Dashboard to load change history without authentication errors **so that** I can review data integrity records.

**Current behavior:** Error dialog: "Failed to load audit data: UNAUTHORIZED". All KPI tiles show 0. "Changes by..." panels show "No notifications found."
**Expected:** Audit data loads when auth is disabled (current config).
**Root cause hypothesis:** The audit API endpoint requires authentication even though Clerk is disabled. The backend middleware may still enforce auth on audit endpoints.
**Acceptance criteria:**
- [ ] Audit data loads without login when auth is disabled
- [ ] KPI tiles (Total Changes, Objects Changed, Users Involved, Creates, Updates, Deletes) show real counts
- [ ] Recent Changes table populates

---

## P1 — Major UX Issues

### US-03: Launchpad tile subtitles are truncated
**As** Maria (Maintenance Planner), **I want** to read the full description of each launchpad tile **so that** I know what each application does before clicking.

**Current behavior:** Subtitles truncated: "Analyze PM Notificat...", "ALCOA+ Complianc...", "MTBF & MTTR Analy..."
**Improvement:** Use `TwoByOne` frameType for the first tile (primary app) or shorten subheader texts to fit within `OneByOne` tile width.
**Acceptance criteria:**
- [ ] All 4 tile subheaders are fully readable without truncation

### US-04: Notification detail page is very dense — poor readability
**As** Maria, **I want** the notification detail page to have clear visual hierarchy and sufficient spacing **so that** I can quickly find the information I need.

**Current behavior:** DynamicSideContent splits the screen with very small text. The Quality Score panel on the right competes with the main content. Timeline steps are small. The long text field is hard to read. The whole page feels cramped.
**Improvement:**
- Use an `ObjectPageLayout` (sap.uxap) instead of Page + DynamicSideContent for the main notification data
- Move the AI Quality panel to a collapsible side panel or a separate tab
- Give the timeline visualization more vertical space
- Increase padding/margins on form fields
**Acceptance criteria:**
- [ ] Notification header area shows key info (ID, description, priority, status) prominently
- [ ] Tabs (Details, Work Order) have comfortable content spacing
- [ ] AI Quality panel is easily togglable without shrinking main content
- [ ] Long text field is fully readable

### US-05: Audit Dashboard "Changes by" panels are too narrow
**As** Thomas, **I want** the distribution panels to show full labels **so that** I can see which object classes and users have the most changes.

**Current behavior:** Two left-side panels show "Changes b..." truncated. Panels are extremely narrow (~100px) while the rest of the page is empty space.
**Improvement:** Use a responsive `l:Grid` layout with `L6 M6 S12` spans so each distribution panel takes 50% width.
**Acceptance criteria:**
- [ ] "Changes by Object Class" and "Changes by User" panel titles are fully visible
- [ ] Distribution lists have adequate width to show values

### US-06: No way to navigate back to Launchpad from worklist/dashboards
**As** Maria, **I want** to easily navigate back to the Launchpad from any application **so that** I can switch between the Maintenance Assistant, Rule Manager, and dashboards.

**Current behavior:** The ShellBar home icon navigates back to Launchpad from PM Analyzer/Rule Manager (App.controller.js), but there's no visible home button — only clicking the title text triggers navigation. Users may not discover this.
**Improvement:** Add a visible home icon/logo to the ShellBar that clearly signals it's clickable. Use the `homeIcon` property with a proper icon URI.
**Acceptance criteria:**
- [ ] ShellBar shows a clickable home icon (e.g., SAP logo or house icon)
- [ ] Clicking the home icon navigates to the Launchpad

---

## P2 — UX Enhancements

### US-07: Notification list needs an item count and better visual density
**As** Maria, **I want** to see how many notifications are in the list and identify high-priority ones at a glance **so that** I can prioritize my work.

**Current behavior:** No item count visible. All list items look the same except for the priority text color. No visual indicator of quality score per notification.
**Improvement:**
- Add `headerToolbar` with item count: "Notifications (5)"
- Add a quality score `ObjectNumber` or micro indicator on each list item
- Use `highlight` property on ObjectListItem for priority-based row highlighting (Error for Very High/High, Warning for Medium)
**Acceptance criteria:**
- [ ] List header shows total count of notifications
- [ ] High-priority notifications have visual row highlighting
- [ ] Quality score (if analyzed) is shown inline

### US-08: Rule Manager needs rule count and creation date on dashboard
**As** Jan (Rule Admin), **I want** to see when each ruleset was created and how many rules it contains **so that** I can understand the maturity and completeness of each ruleset.

**Current behavior:** Dashboard shows name, assigned-to type, status, version. Missing: creation date, rule count, last modified date.
**Improvement:** Add "Created" and "Rules" columns, or show rule count as a badge on the ObjectIdentifier.
**Acceptance criteria:**
- [ ] Each ruleset row shows creation date
- [ ] Each ruleset row shows number of rules contained

### US-09: Reliability Dashboard needs "Equipment Requiring Attention" section
**As** Elena (Reliability Engineer), **I want** to see a table of equipment that requires immediate attention **so that** I can prioritize maintenance actions.

**Current behavior:** The Reliability Dashboard shows KPI tiles (96% reliability, 100% availability, 5 equipment, 0 critical/high risk) and the FMEA panel, but the "Equipment Requiring Attention" panel between them is missing or empty.
**Improvement:** Ensure the Equipment Requiring Attention table is visible when there's equipment data. If 0 critical/0 high risk, show a positive confirmation message instead of hiding the section.
**Acceptance criteria:**
- [ ] Equipment Requiring Attention section always visible
- [ ] Shows "No equipment requires immediate attention" message with success icon when risk is 0
- [ ] All Equipment expandable section shows the 5 monitored items

### US-10: Add breadcrumb navigation to sub-pages
**As** Maria, **I want** breadcrumb navigation on detail pages and dashboards **so that** I always know where I am and can navigate back step by step.

**Current behavior:** Sub-pages (notification detail, quality dashboard, reliability dashboard, audit dashboard, rule editor) have a back button but no breadcrumb trail.
**Improvement:** Add `sap.m.Breadcrumbs` control to sub-page headers showing the navigation path (e.g., "Notifications > 10000005").
**Acceptance criteria:**
- [ ] All detail/sub-pages show breadcrumb navigation
- [ ] Breadcrumb links are clickable and navigate to the correct parent page

### US-11: Rule Editor page is bare — needs header info and better layout
**As** Jan, **I want** the Rule Editor to show ruleset metadata and rules in a clear layout **so that** I can effectively manage rules within a ruleset.

**Current behavior:** Rule Editor shows "Edit Ruleset" title and a raw table of rules. No ruleset name, type, status, or version info. No visual distinction between rule types. Table has plain Text cells with no formatting.
**Improvement:**
- Add an `ObjectHeader` showing ruleset name, type, status badge, version, creation date
- Use `ObjectIdentifier` for rule names in the table
- Add `ObjectStatus` for rule type with color coding
- Show score impact as an `ObjectNumber` with color
**Acceptance criteria:**
- [ ] Ruleset metadata (name, type, status, version) displayed in header
- [ ] Rules table uses proper Fiori controls (ObjectIdentifier, ObjectStatus, ObjectNumber)
- [ ] Score impact values are color-coded (positive = green, negative = red)

### US-12: Launchpad tiles should show notification/ruleset counts
**As** Maria, **I want** the launchpad tiles to show summary counts **so that** I can see at a glance how many notifications need attention and how many active rules exist.

**Current behavior:** Tiles show only static titles and icons. No dynamic data.
**Improvement:** Use `NumericContent` in TileContent to show:
- Maintenance Execution Assistant: count of outstanding notifications
- Rule Manager: count of active rulesets
- Quality Dashboard: current overall quality score
- Reliability Dashboard: current average reliability score
**Acceptance criteria:**
- [ ] At least one tile shows a dynamic count/metric
- [ ] Counts update when data changes

---

## P3 — Polish & Consistency

### US-13: Audit Dashboard KPI tile subtitles show internal model property names
**As** Thomas, **I want** KPI tiles to show proper human-readable subtitles **so that** the dashboard looks professional.

**Current behavior:** Subtitles show internal names: "inPeriod", "uniqueObjects", "activeUsers", "newRecords", "modifications", "removals" instead of proper labels.
**Improvement:** Use i18n keys or proper readable text for all tile subtitles.
**Acceptance criteria:**
- [ ] All 6 Audit Dashboard KPI tile subtitles are human-readable

### US-14: Consistent button styling across toolbar actions
**As** a user, **I want** toolbar actions to have consistent visual hierarchy **so that** I know which is the primary action.

**Current behavior:** PM Analyzer worklist toolbar: "Quality Dashboard" is `Emphasized` (filled blue), "Reliability Dashboard" is `Ghost` (outlined), "Audit Trail" is `Transparent`. This mixed styling is inconsistent — all three are peer navigation actions and should have equal visual weight.
**Improvement:** Use consistent `Ghost` type for all peer navigation buttons, or use `IconTabBar` for dashboard switching instead of buttons.
**Acceptance criteria:**
- [ ] Peer navigation actions use the same button type
- [ ] Primary action (if any) is clearly differentiated from navigation

### US-15: Empty states should use illustrations
**As** a user, **I want** empty data states to show helpful illustrations and guidance **so that** I understand why there's no data and what to do next.

**Current behavior:** Empty states show plain text like "No rulesets found.", "No FMEA data available.", "No changes found for the selected criteria."
**Improvement:** Use `sap.m.IllustratedMessage` control with appropriate illustration type (e.g., `NoData`, `NoSearchResults`, `EmptyList`) and a helpful description.
**Acceptance criteria:**
- [ ] All empty states use IllustratedMessage with an illustration
- [ ] Empty states include a descriptive subtitle

### US-16: Mobile responsiveness — tiles and layouts should adapt
**As** Maria, **I want** to use the application on a tablet **so that** I can review notifications on the plant floor.

**Current behavior:** Layouts use fixed percentages (e.g., Panel width="60%") and don't fully adapt to smaller screens. GenericTiles may overflow on narrow viewports.
**Improvement:** Use responsive layout controls (Grid, FlexBox) with proper breakpoints. Test at 768px and 1024px widths.
**Acceptance criteria:**
- [ ] All pages render without horizontal scroll at 768px width
- [ ] KPI tiles wrap properly on tablet-width screens
- [ ] Tables are horizontally scrollable or columns collapse on small screens

---

## Implementation Priority

| Priority | Stories | Effort | Impact |
|----------|---------|--------|--------|
| **P0 — Must Fix** | US-01, US-02 | Medium | Critical — core features broken |
| **P1 — Next Sprint** | US-03, US-04, US-05, US-06 | Medium-Large | High — major UX blockers |
| **P2 — Backlog** | US-07–US-12 | Medium | Medium — quality of life |
| **P3 — Polish** | US-13–US-16 | Small-Medium | Low — professional polish |
