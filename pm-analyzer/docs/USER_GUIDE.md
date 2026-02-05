# PM Notification Analyzer - User Guide

## Introduction

The PM Notification Analyzer is an AI-powered application for analyzing SAP Plant Maintenance (PM) notifications. It helps maintenance teams improve data quality, predict equipment failures, and ensure regulatory compliance.

---

## Getting Started

### Accessing the Application

1. Open the **SAP Build Work Zone** launchpad
2. Click the **PM Notification Analyzer** tile
3. You will be authenticated via SAP XSUAA (Single Sign-On)

### Navigation

| Area | Description |
|------|-------------|
| **Worklist** | Browse and filter all maintenance notifications |
| **Notification Detail** | View details, codes, work orders, and AI analysis |
| **Quality Dashboard** | ALCOA+ data quality metrics and trends |
| **Reliability Dashboard** | MTBF/MTTR, Weibull analysis, FMEA |
| **Audit Dashboard** | FDA 21 CFR Part 11 change history and compliance |

---

## Worklist (Notification List)

The worklist displays all SAP PM notifications with filtering and pagination.

### Filters

| Filter | Description |
|--------|-------------|
| **Notification Type** | M1 (Maintenance Request), M2 (Malfunction Report), M3 (Activity Report) |
| **Priority** | Very High (1), High (2), Medium (3), Low (4) |
| **Equipment** | Filter by equipment number |
| **Functional Location** | Filter by functional location |
| **Creator** | Filter by notification creator |
| **Status** | Filter by system status |

### Pagination

- Default page size: 50 items
- Navigate between pages using the pagination controls at the bottom
- Adjust page size from 10 to 100 items

### Language

Switch between English (EN) and German (DE) using the language selector. All notification texts, descriptions, and labels will update accordingly.

---

## Notification Detail

Click any notification in the worklist to open its detail view.

### Tabs

#### Details Tab
- Notification header information (type, priority, dates, equipment)
- Functional location and equipment description
- Long text description

#### Codes Tab
- **Damage codes** (Object Part + Damage Code)
- **Cause codes** (Cause Group + Cause Code)
- **Activity codes** (Activity Group + Activity Code)

#### Work Order Tab
- Linked maintenance order details
- Operations with work center, duration, and description
- Material components (BOM items)

#### Analysis Tab
Click **Analyze** to run AI-powered analysis on the notification. The analysis evaluates:
- **Data completeness** - Are all required fields filled?
- **Description quality** - Is the problem clearly described?
- **Code accuracy** - Are damage/cause codes appropriate?
- **Actionability** - Can a technician act on this notification?

Results include a quality score (0-100%) and specific recommendations.

#### Chat Tab
Ask follow-up questions about the notification using the AI chat assistant:
- "What maintenance actions are recommended?"
- "Is this a recurring issue?"
- "What spare parts might be needed?"

---

## Quality Dashboard

The Quality Dashboard provides ALCOA+ data quality metrics across all notifications.

### ALCOA+ Principles

| Principle | What It Measures |
|-----------|-----------------|
| **Attributable** | Can we identify who created/modified the data? |
| **Legible** | Is the data readable and understandable? |
| **Contemporaneous** | Was the data recorded at the time of the event? |
| **Original** | Is this the original record (not a copy)? |
| **Accurate** | Is the data factually correct? |
| **Complete** | Are all required fields populated? |
| **Consistent** | Is the data consistent across related records? |
| **Enduring** | Is the data stored in a durable format? |
| **Available** | Can authorized users access the data when needed? |

### Key Metrics

- **Overall Quality Score** - Weighted average across all ALCOA+ dimensions
- **Completeness Rate** - Percentage of required fields populated
- **Timeliness Score** - How promptly notifications are created after events
- **Quality Trend** - Score progression over time (daily/weekly/monthly)

### Export

Click **Export CSV** to download quality metrics for external analysis.

---

## Reliability Dashboard

The Reliability Dashboard provides equipment reliability engineering metrics.

### Key Metrics

| Metric | Description |
|--------|-------------|
| **MTBF** | Mean Time Between Failures - average operating time between breakdowns |
| **MTTR** | Mean Time To Repair - average duration of maintenance activities |
| **Availability** | Equipment availability percentage (MTBF / (MTBF + MTTR)) |
| **Reliability Score** | Composite score combining multiple reliability indicators |

### Weibull Analysis

The Weibull failure distribution chart shows:
- **Beta (β) < 1**: Early life failures (infant mortality)
- **Beta (β) = 1**: Random failures (constant failure rate)
- **Beta (β) > 1**: Wear-out failures (aging equipment)

### FMEA (Failure Mode and Effects Analysis)

The FMEA table lists potential failure modes ranked by:
- **Severity** - Impact of the failure (1-10)
- **Occurrence** - Frequency of the failure (1-10)
- **Detection** - Likelihood of detecting the failure before it occurs (1-10)
- **RPN** - Risk Priority Number (Severity × Occurrence × Detection)

### Predictive Maintenance

Equipment with high failure probability shows predictive maintenance recommendations:
- Estimated next failure window
- Recommended preventive actions
- Confidence level of the prediction

---

## Audit Dashboard

The Audit Dashboard supports FDA 21 CFR Part 11 compliance requirements.

### Change History

Every modification to notification data is tracked:
- **Who** changed it (username)
- **When** it was changed (date and time)
- **What** was changed (old value → new value)
- **Transaction code** used

### Version History

View historical versions of notifications to track how they evolved over time.

### Time Confirmations

View labor confirmations against maintenance orders:
- Worker ID and work center
- Actual work start and end times
- Actual duration vs. planned duration

### Export

Generate PDF audit trail reports or export to CSV for external review.

---

## Reports

### PDF Reports

Generate professional PDF reports from any dashboard:

| Report | Contents |
|--------|----------|
| **Notification Report** | Full notification details with analysis |
| **Quality Report** | ALCOA+ scores, trends, and recommendations |
| **Reliability Report** | MTBF/MTTR metrics, FMEA, equipment rankings |
| **Audit Report** | Change document history for compliance review |

### CSV Exports

Export raw data from Quality, Reliability, and Audit dashboards for use in Excel, Power BI, or other tools.

---

## Alerts & Notifications

### Alert Rules

The system includes predefined alert rules:

| Rule | Trigger | Severity |
|------|---------|----------|
| Critical Quality Score | Quality score < 50% | Critical |
| Low Quality Score | Quality score < 70% | High |
| Critical Reliability Risk | Reliability score < 40% | Critical |
| High Failure Probability | Failure probability > 70% | High |
| Overdue Maintenance | Days overdue > 0 | High |
| Critical Equipment Down | Type M1 + Priority 1 | Critical |
| ALCOA+ Violation | Compliance score < 80% | High |

### Subscriptions

Subscribe to receive email alerts based on:
- Alert type (quality, reliability, compliance, equipment failure)
- Minimum severity level
- Specific equipment or functional locations

---

## GDPR & Privacy

### Your Data Rights

As a user, you have the following rights under GDPR:

| Right | How to Exercise |
|-------|----------------|
| **Access (Art. 15)** | Go to Settings > Privacy > Export My Data |
| **Erasure (Art. 17)** | Contact your administrator or submit a request via Settings > Privacy |
| **Portability (Art. 20)** | Export your data as JSON or CSV |
| **Consent (Art. 7)** | Manage your consent preferences in Settings > Privacy > Consent |

### Consent Management

You can grant or revoke consent for:
- AI-powered analysis of notification data
- Email notifications
- Usage analytics
- Third-party QMS integration

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus search box |
| `Enter` | Open selected notification |
| `Esc` | Close dialog / clear selection |

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Notifications not loading | Check your network connection and refresh the page |
| Analysis button disabled | Ensure the notification has a description text |
| Quality scores show 0% | Verify notification data completeness |
| PDF report fails | Check that the notification exists and has data |
| Language not switching | Clear browser cache and reload |

### Support

Contact your system administrator or raise a support ticket through the SAP Build Work Zone help center.

---

*PM Notification Analyzer v2.1.0 | Last updated: February 2026*
