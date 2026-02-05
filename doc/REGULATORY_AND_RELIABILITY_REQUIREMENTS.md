# Regulatory & Reliability Engineering Requirements Analysis

**Document Version:** 1.0
**Date:** 2026-02-04
**Purpose:** Define requirements for using PM Notification Analyzer in regulated industries and reliability engineering contexts

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Regulatory Compliance Frameworks](#2-regulatory-compliance-frameworks)
   - [FDA 21 CFR Part 11](#21-fda-21-cfr-part-11---electronic-records--signatures)
   - [EU GMP Annex 11](#22-eu-gmp-annex-11---computerised-systems)
   - [GAMP 5](#23-gamp-5---risk-based-validation)
   - [AI/ML in GxP Environments](#24-aiml-in-gxp-environments)
3. [Reliability Engineering Requirements](#3-reliability-engineering-requirements)
   - [ISO 55000 Asset Management](#31-iso-55000---asset-management)
   - [RCM Data Requirements](#32-reliability-centered-maintenance-rcm-data-requirements)
   - [FMEA Data Quality](#33-fmea-data-quality-requirements)
   - [SAP PM Best Practices](#34-sap-pm-data-quality-best-practices)
4. [Gap Analysis Summary](#4-gap-analysis-summary)
5. [Recommended Feature Roadmap](#5-recommended-feature-roadmap)
6. [Data Quality Requirements Matrix](#6-data-quality-requirements-matrix)
7. [References](#7-references)

---

## 1. Executive Summary

This document analyzes the requirements for deploying the PM Notification Analyzer in:

1. **Regulated Industries** (Pharmaceutical, Medical Devices, Food & Beverage) where compliance with FDA 21 CFR Part 11, EU GMP Annex 11, and GAMP 5 is mandatory
2. **Reliability Engineering Contexts** where high-quality maintenance data is essential for FMEA, RCM, and predictive maintenance initiatives

### Current Compliance Status

| Framework | Status | Key Gaps |
|-----------|--------|----------|
| FDA 21 CFR Part 11 | Partial | Electronic signatures, full RBAC |
| EU GMP Annex 11 | Partial | Validation documentation, supplier qualification |
| GAMP 5 | Partial | Formal specifications, traceability matrix |
| ISO 55000 | Good | KPI dashboard, lifecycle tracking |
| RCM/FMEA | Partial | MTBF/MTTR metrics, RPN calculation |

### Existing Compliance Features

- Audit trail with user attribution and timestamps (Rule Manager)
- Version control for rulesets with status lifecycle
- Input validation across all API endpoints
- JWT-based authentication framework (ready to enable)
- ALCOA+ principles documented and partially implemented
- AI-assisted data quality validation

---

## 2. Regulatory Compliance Frameworks

### 2.1 FDA 21 CFR Part 11 - Electronic Records & Signatures

FDA 21 CFR Part 11 establishes criteria under which electronic records and electronic signatures are considered trustworthy, reliable, and equivalent to paper records.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **System Validation** | Demonstrate accuracy, reliability, consistent performance | Partial | Need formal IQ/OQ/PQ documentation |
| **Audit Trail** | Record all create/modify/delete actions with timestamps | Implemented | Rule Manager has full audit trail |
| **Record Protection** | Prevent unauthorized access/modification | Partial | Auth framework exists but disabled by default |
| **Electronic Signatures** | Two-factor identification (ID + password) | Placeholder | Model exists, implementation needed |
| **Signature Linking** | Signatures linked to respective records | Missing | Need to implement for rule activation |
| **Authority Checks** | Limit access based on roles | Partial | RBAC decorators exist, roles not enforced |
| **Device Checks** | Verify source of data entry | Missing | No device/terminal identification |
| **Time-Stamped Audit Trail** | UTC timestamps, tamper-evident | Implemented | Server-generated UTC timestamps |
| **Operational Checks** | Enforce sequencing of steps | Partial | Status lifecycle enforced |
| **Copy Generation** | Human-readable copies for inspection | Implemented | JSON export available |

#### Key Implementation Requirements

1. **Electronic Signature Components:**
   - Unique user identification code
   - Password or biometric verification
   - Signature meaning declaration (e.g., "approved", "reviewed")
   - Link between signature and signed record

2. **Audit Trail Requirements:**
   - Who made the change (user ID)
   - What was changed (field/record)
   - When it was changed (UTC timestamp)
   - Previous value (for modifications)
   - Reason for change (where applicable)

3. **System Controls:**
   - Automatic session timeout
   - Failed login attempt limiting
   - Unique user accounts (no shared credentials)
   - Password complexity requirements

---

### 2.2 EU GMP Annex 11 - Computerised Systems

EU GMP Annex 11 applies to all computerised systems used in GMP-regulated activities, emphasizing risk management and data integrity.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **Risk Management** | Apply throughout system lifecycle | Partial | Risk assessment framework needed |
| **Personnel Qualifications** | Documented training & competency | Missing | No training tracking |
| **Supplier Assessment** | Audit AI/LLM providers (Google Gemini) | Missing | Need supplier qualification |
| **Data Integrity (ALCOA+)** | Attributable, Legible, Contemporaneous, Original, Accurate | Documented | Framework designed per ALCOA+ |
| **Validation Documentation** | Validation protocols & reports | Missing | Need formal CSV documentation |
| **Change Control** | Documented change management | Implemented | Version control with audit trail |
| **Business Continuity** | Backup, recovery procedures | Missing | No documented BCP |
| **Periodic Review** | Regular system evaluation | Missing | No review scheduling |
| **Security Controls** | Physical & logical access | Partial | Logical access, no physical |
| **Printouts** | Clear, unambiguous printable records | Partial | JSON export, no formatted reports |

#### ALCOA+ Principles Implementation

| Principle | Description | Implementation |
|-----------|-------------|----------------|
| **Attributable** | Who performed action | User ID in audit trail |
| **Legible** | Readable and permanent | JSON storage, UTF-8 encoding |
| **Contemporaneous** | Recorded at time of activity | Server-generated timestamps |
| **Original** | First capture of data | Versioning prevents overwrite |
| **Accurate** | Free from errors | Input validation, AI verification |
| **Complete** | All data present | Mandatory field enforcement |
| **Consistent** | Same format/structure | Schema validation |
| **Enduring** | Available throughout retention | Database persistence |
| **Available** | Accessible when needed | API endpoints, export functions |

---

### 2.3 GAMP 5 - Risk-Based Validation

GAMP 5 provides a risk-based approach to compliant GxP computerised systems, categorizing software and defining validation requirements.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **Software Category** | Categorize system (Cat 3/4/5) | Missing | Need formal categorization |
| **Specification (URS/FS/DS)** | User, Functional, Design specs | Missing | No formal specifications |
| **Risk Assessment** | FMEA for system functions | Missing | Need system FMEA |
| **Test Protocols** | IQ, OQ, PQ documentation | Partial | Unit tests exist, no formal protocols |
| **Traceability Matrix** | Requirements to tests | Missing | Need RTM |
| **Configuration Management** | Baseline & change control | Implemented | Git + ruleset versioning |
| **Incident Management** | Defect tracking & resolution | Missing | No incident tracking system |
| **Periodic Review** | Maintain validated state | Missing | No review process |

#### Software Categorization

This application would likely be classified as:

- **Category 4 (Configured Products):** The base application with configurable rules
- **Category 5 (Custom Applications):** The AI/LLM integration components

Both categories require:
- User Requirements Specification (URS)
- Functional Specification (FS)
- Configuration/Design Specification
- Test protocols (IQ/OQ/PQ)
- Traceability matrix

---

### 2.4 AI/ML in GxP Environments

Recent FDA and EMA guidance (2024) addresses the use of AI/ML in regulated environments.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **AI Model Documentation** | Document model purpose, training data, limitations | Missing | Need Gemini usage documentation |
| **Predetermined Change Control Plan** | Define acceptable model changes | Missing | Need PCCP for AI components |
| **Explainability** | Ability to explain AI decisions | Partial | Analysis provides rationale |
| **Human Oversight** | Human review of AI outputs | Implemented | Users review before action |
| **Data Quality for Training** | Validate training data sources | N/A | Using pre-trained Gemini |
| **Performance Monitoring** | Track AI accuracy over time | Missing | No AI performance metrics |
| **Bias Detection** | Monitor for discriminatory outputs | Missing | No bias monitoring |
| **Credibility Assessment** | 7-step FDA framework | Missing | Need formal assessment |

#### AI Governance Requirements

1. **Documentation:**
   - AI model identification (Gemini version)
   - Intended use and limitations
   - Input/output specifications
   - Prompt versioning

2. **Controls:**
   - Human-in-the-loop for critical decisions
   - Override capability
   - Audit trail for AI interactions

3. **Monitoring:**
   - Performance metrics tracking
   - Drift detection
   - User feedback collection

---

## 3. Reliability Engineering Requirements

### 3.1 ISO 55000 - Asset Management

ISO 55000 provides requirements for effective asset management across the full lifecycle.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **Asset Hierarchy** | Structured equipment taxonomy | Implemented | Equipment + Functional Location |
| **Lifecycle Management** | Track asset from acquisition to disposal | Partial | Limited to notifications |
| **Risk-Based Decisions** | Prioritize based on criticality | Implemented | Priority field + analysis |
| **Performance Monitoring** | KPIs for asset performance | Missing | No KPI dashboard |
| **Continuous Improvement** | Feedback loops for improvement | Partial | Chat/what-if analysis |
| **Documentation** | Complete asset records | Implemented | Full notification history |

#### Key Asset Management Features Needed

1. **Asset Health Scoring**
   - Aggregate notification history
   - Calculate reliability metrics
   - Trend analysis

2. **Criticality Assessment**
   - Equipment criticality ranking
   - Risk-based prioritization
   - Resource allocation support

---

### 3.2 Reliability Centered Maintenance (RCM) Data Requirements

RCM requires high-quality failure data to develop effective maintenance strategies.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **Failure Mode Identification** | Capture specific failure modes | Partial | Damage codes exist |
| **Failure Cause Analysis** | Root cause documentation | Implemented | Cause codes + validation |
| **Failure Consequences** | Impact assessment | Implemented | Product impact analysis |
| **Failure History** | Historical failure data | Partial | Need aggregation/reporting |
| **MTBF/MTTR Tracking** | Mean time metrics | Missing | Need calculation engine |
| **Criticality Ranking** | Equipment criticality | Partial | Priority exists, not criticality |
| **Maintenance Effectiveness** | Track maintenance outcomes | Missing | No effectiveness metrics |

#### Required Metrics

| Metric | Formula | Data Source |
|--------|---------|-------------|
| **MTBF** | Total Operating Time / Number of Failures | Notification timestamps, equipment uptime |
| **MTTR** | Total Repair Time / Number of Repairs | Notification start/end dates |
| **Availability** | MTBF / (MTBF + MTTR) | Calculated from above |
| **Failure Rate** | Number of Failures / Time Period | Notification counts by period |

---

### 3.3 FMEA Data Quality Requirements

Failure Mode and Effects Analysis requires structured failure data for risk assessment.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **Failure Mode Codes** | Standardized failure taxonomy | Implemented | FEGRP/FECOD fields |
| **Severity Rating** | Impact severity classification | Implemented | Critical/Major/Minor |
| **Occurrence Frequency** | Failure frequency data | Missing | Need frequency tracking |
| **Detection Method** | How failures are detected | Missing | No detection field |
| **RPN Calculation** | Risk Priority Number | Missing | Need S x O x D calculation |
| **Recommended Actions** | Mitigation actions | Implemented | CAPA suggestions |
| **Action Tracking** | Track action completion | Missing | No action tracking |

#### RPN Calculation Requirements

```
RPN = Severity (S) x Occurrence (O) x Detection (D)

Where:
- Severity (1-10): Impact of failure
- Occurrence (1-10): Frequency of failure
- Detection (1-10): Likelihood of detecting before impact

Action Thresholds:
- RPN >= 200: Immediate action required
- RPN 100-199: Action needed
- RPN < 100: Monitor
```

---

### 3.4 SAP PM Data Quality Best Practices

High-quality notification data is essential for downstream analysis.

#### Requirements Matrix

| Requirement | Description | Current Status | Gap |
|-------------|-------------|----------------|-----|
| **Mandatory Fields** | Enforce required data entry | Implemented | Validation enforces fields |
| **Standardized Codes** | Consistent coding schemes | Implemented | Type, Priority, Damage codes |
| **Breakdown Indicator** | Track unplanned downtime | Partial | Field exists in schema |
| **Malfunction Start/End** | Downtime duration | Implemented | STRMN/LTRMN fields |
| **Long Text Quality** | Detailed problem description | Implemented | AI validates long text |
| **Equipment Linkage** | Proper equipment assignment | Implemented | EQUNR validation |
| **Work Center Assignment** | Correct responsibility | Implemented | WorkCenter field |
| **Notification Type** | Correct type selection | Implemented | M1/M2/M3 validated |

#### Data Quality Rules Enforced by AI

1. **Completeness Rules:**
   - Long text must be detailed (>50 characters recommended)
   - Root cause must be identified
   - Product impact must be assessed
   - CAPA must be outlined

2. **Consistency Rules:**
   - Equipment must be valid
   - Functional location must match equipment
   - Priority must align with impact

3. **Accuracy Rules:**
   - Technical terms should be correct
   - Dates should be logical (start before end)
   - Quantities should be reasonable

---

## 4. Gap Analysis Summary

### Critical Gaps (Must Address for Regulated Use)

| Priority | Gap | Regulatory Driver | Effort | Files Affected |
|----------|-----|-------------------|--------|----------------|
| **P1** | Electronic Signature Implementation | 21 CFR Part 11 | Medium | `auth.py`, `api.py`, `database.py` |
| **P1** | Full RBAC Enforcement | 21 CFR Part 11, Annex 11 | Medium | `auth.py`, `main.py`, frontend |
| **P1** | Validation Documentation (IQ/OQ/PQ) | GAMP 5, Annex 11 | High | New documentation |
| **P1** | AI/LLM Usage Documentation | FDA AI Guidance | Medium | New documentation |
| **P2** | Training & Competency Tracking | Annex 11 | Medium | New module |
| **P2** | Supplier Qualification (Google) | Annex 11 | Low | Documentation only |
| **P2** | Business Continuity Plan | Annex 11 | Medium | Documentation + implementation |
| **P2** | Incident Management System | GAMP 5 | Medium | New module or integration |

### Reliability Engineering Gaps

| Priority | Gap | Standard | Effort | Implementation |
|----------|-----|----------|--------|----------------|
| **P1** | MTBF/MTTR Calculation | ISO 55000, RCM | Medium | New service module |
| **P1** | Failure Frequency Tracking | FMEA | Medium | Database + API |
| **P2** | KPI Dashboard | ISO 55000 | High | New frontend view |
| **P2** | RPN Calculation Engine | FMEA | Medium | New service module |
| **P3** | Predictive Analytics | RCM | High | ML model integration |
| **P3** | Action Tracking System | FMEA | Medium | New module |

---

## 5. Recommended Feature Roadmap

### Phase 3: Regulatory Compliance Enhancements

```
┌─────────────────────────────────────────────────────────────────┐
│  3.1 Electronic Signatures                                       │
│  ├── Implement e-signature capture for rule activation           │
│  ├── Two-factor authentication (username + password)             │
│  ├── Signature meaning declarations                              │
│  └── Signature linking to records                                │
├─────────────────────────────────────────────────────────────────┤
│  3.2 Full Role-Based Access Control                              │
│  ├── Admin, QA Expert, Viewer, Auditor roles                     │
│  ├── Permission matrix enforcement                               │
│  ├── Session timeout & re-authentication                         │
│  └── Access attempt logging                                      │
├─────────────────────────────────────────────────────────────────┤
│  3.3 Validation Support Package                                  │
│  ├── Requirements traceability matrix export                     │
│  ├── Test protocol templates (IQ/OQ/PQ)                          │
│  ├── Validation summary report generation                        │
│  └── System configuration documentation                          │
├─────────────────────────────────────────────────────────────────┤
│  3.4 AI Governance Module                                        │
│  ├── AI model usage logging                                      │
│  ├── Prompt versioning & audit trail                             │
│  ├── AI confidence scoring                                       │
│  └── Human override documentation                                │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 4: Reliability Engineering Enhancements

```
┌─────────────────────────────────────────────────────────────────┐
│  4.1 Reliability Metrics Engine                                  │
│  ├── MTBF calculation by equipment/location                      │
│  ├── MTTR tracking from notification to closure                  │
│  ├── Availability calculations                                   │
│  └── Failure rate trending                                       │
├─────────────────────────────────────────────────────────────────┤
│  4.2 FMEA Integration                                            │
│  ├── RPN (Risk Priority Number) calculation                      │
│  ├── Severity x Occurrence x Detection scoring                   │
│  ├── Failure mode categorization                                 │
│  └── Action recommendation engine                                │
├─────────────────────────────────────────────────────────────────┤
│  4.3 Analytics Dashboard                                         │
│  ├── Quality score trends over time                              │
│  ├── Top failure modes by equipment class                        │
│  ├── Notification quality KPIs                                   │
│  └── Compliance metrics (completeness, timeliness)               │
├─────────────────────────────────────────────────────────────────┤
│  4.4 Predictive Capabilities                                     │
│  ├── Failure pattern recognition                                 │
│  ├── Equipment health scoring                                    │
│  ├── Maintenance optimization recommendations                    │
│  └── What-if scenario modeling                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Quality Requirements Matrix

For reliable analysis and regulatory compliance, the following data quality dimensions must be enforced:

| Dimension | Description | Current | Target | Validation Rule |
|-----------|-------------|---------|--------|-----------------|
| **Completeness** | All required fields populated | 85% | 100% | Mandatory field validation |
| **Accuracy** | Data reflects reality | Variable | >95% | AI-assisted validation |
| **Consistency** | Same codes/formats used | High | 100% | Code table enforcement |
| **Timeliness** | Data entered promptly | Unknown | <24hrs | Timestamp monitoring |
| **Uniqueness** | No duplicate records | Enforced | 100% | Primary key constraints |
| **Validity** | Data within acceptable ranges | Validated | 100% | Range/format validation |
| **Traceability** | Data source identifiable | Implemented | 100% | User attribution |
| **Auditability** | Changes tracked | Rule Mgr | 100% | Audit trail logging |

### Data Quality KPIs

| KPI | Description | Target | Measurement |
|-----|-------------|--------|-------------|
| **Notification Completeness Rate** | % of notifications with all required fields | >95% | Count mandatory fields filled |
| **Long Text Quality Score** | Average AI quality score for long text | >70 | AI analysis score |
| **Root Cause Identification Rate** | % of notifications with root cause | >90% | Count cause codes filled |
| **CAPA Documentation Rate** | % of notifications with CAPA | >85% | AI detection of CAPA |
| **Data Entry Timeliness** | % entered within 24 hours | >80% | Creation timestamp analysis |

---

## 7. References

### Regulatory References

1. **FDA 21 CFR Part 11**
   - [eCFR :: 21 CFR Part 11](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11)
   - [FDA 2024 Clinical Investigations Guidance](https://www.fda.gov/media/166215/download)

2. **EU GMP Annex 11**
   - [EU GMP Annex 11 Official Document](https://health.ec.europa.eu/system/files/2016-11/annex11_01-2011_en_0.pdf)
   - [ECA Academy Guide](https://www.gmp-compliance.org/guidelines/gmp-guideline/eu-gmp-annex-11-computerised-systems)

3. **AI/ML Guidance**
   - [FDA AI/ML Software Guidance](https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-software-medical-device)
   - [ISPE AI Governance in GxP](https://ispe.org/pharmaceutical-engineering/july-august-2024/artificial-intelligence-governance-gxp-environments)
   - [ISPE GAMP AI Guide](https://www.bioprocessintl.com/regulations/ispe-releases-gamp-guide-on-artificial-intelligence)

### Reliability Engineering References

4. **ISO 55000 & Asset Management**
   - [CMMS & ISO 55000 Compliance](https://llumin.com/how-cmms-supports-compliance-with-iso-55000-standards/)
   - [RCM & ISO 55000](https://reliabilityweb.com/articles/entry/rcm_providing_the)

5. **RCM & FMEA**
   - [IBM RCM Guide](https://www.ibm.com/think/topics/reliability-centered-maintenance)
   - [RCM & FMEA Discussion](https://assetmanagementprofessionals.org/discussion/rcm-and-fmea)
   - [Emerson Reliability White Paper](https://www.emerson.com/documents/automation/white-paper-information-needed-for-effective-services-en-68110.pdf)

6. **SAP PM Best Practices**
   - [NRX SAP PM Best Practices](https://www.nrx.com/simplify-plant-maintenance/)
   - [SAP PM Notification Guide](https://www.nrx.com/asset-and-maintenance-data-quality/simple-sap-notification/)

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-04 | Claude Code | Initial version |

---

## Appendix A: Acronyms

| Acronym | Definition |
|---------|------------|
| ALCOA+ | Attributable, Legible, Contemporaneous, Original, Accurate (+ Complete, Consistent, Enduring, Available) |
| CAPA | Corrective and Preventive Action |
| CFR | Code of Federal Regulations |
| CMMS | Computerized Maintenance Management System |
| CSV | Computer System Validation |
| EAM | Enterprise Asset Management |
| FDA | Food and Drug Administration |
| FMEA | Failure Mode and Effects Analysis |
| FS | Functional Specification |
| GAMP | Good Automated Manufacturing Practice |
| GMP | Good Manufacturing Practice |
| GxP | Good Practice (general term) |
| IQ | Installation Qualification |
| MTBF | Mean Time Between Failures |
| MTTR | Mean Time To Repair |
| OQ | Operational Qualification |
| PCCP | Predetermined Change Control Plan |
| PM | Plant Maintenance |
| PQ | Performance Qualification |
| RBAC | Role-Based Access Control |
| RCM | Reliability Centered Maintenance |
| RPN | Risk Priority Number |
| RTM | Requirements Traceability Matrix |
| URS | User Requirements Specification |
