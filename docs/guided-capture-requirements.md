# Guided Capture — UX Concept Requirements

> **Status:** Draft v0.2 — Requirements phase
> **Date:** 2026-06-28
> **Context:** New UI/UX concept for the PM Notification Quality Suite
> **Problem statement:** Maintenance technicians are not motivated to document properly.
> Documentation quality must instead be *engineered in at capture time* through a guided,
> low-friction experience — without violating the regulatory constraints of a GxP environment.

---

## 1. Vision

Today the suite is an **analyzer**: it scores and critiques notifications *after* they exist.
But poor documentation is created upstream, at the moment a technician reports a fault.

This concept flips the model from **"judge the documentation"** to
**"make good documentation the path of least resistance."**

The guiding principle:

> The technician's job is to fix machines, not fill forms.
> The system does the paperwork; the technician confirms the truth.

---

## 2. Personas

We introduce one **new primary persona** and reuse the existing supporting ones.

| Persona | Role | Goal | Pain today |
|---------|------|------|------------|
| **Tom** (NEW) | Maintenance Technician | Report and resolve faults fast | Forms are slow, irrelevant, in the way; types the bare minimum |
| **Maria** | Maintenance Planner | Plan work from clean notifications | Receives vague, incomplete notifications |
| **Thomas** | Quality Manager | ALCOA+ compliance & trends | Can't trend on garbage data |
| **Auditor** | External Auditor | Prove data integrity (Part 11) | Needs to see who authored what, and when |

**Tom's reality (drives every design decision):**
- On the plant floor: gloved, hands often busy, noise, poor lighting, dirt.
- Phone in pocket; sometimes a shared tablet; a desktop only back in the shop.
- Connectivity is intermittent (basements, steel structures).
- Motivated by speed and "did I do it right?", not by completeness for its own sake.

---

## 3. Scope (confirmed)

| Dimension | Decision |
|-----------|----------|
| **Maintenance types** | **All** — planned/preventive, proactive corrective (condition/inspection-driven), reactive corrective (breakdown), inspection/calibration. The flow **branches by type** (see §3.1). |
| **Workflow coverage** | **Full lifecycle** — Identify → Capture → Enrich → Execute → Close/Confirm |
| **Devices** | **Mixed** — phone-first on the floor, desktop for completion/review |
| **Input modalities** | **All** — voice, photo/video, tap-to-select, conversational AI wizard |
| **Asset identification** | **Data Matrix (2D) scan** as the primary front door; GS1 Data Matrix may carry equipment / serial / batch in one scan. Search is the fallback. |
| **AI proactivity** | **Risk-tiered** — autonomy steps down as regulatory weight steps up (see §6) |

### 3.1 One front door, several journeys — maintenance types

The single entry point is **"Scan to start."** Tom scans the asset's **Data Matrix code**;
the system resolves the asset, looks up what work is **due or open** on it, and routes him
into the journey that fits the maintenance type. Each type stresses different data and has a
different trigger, so the guidance adapts.

| Maintenance type | Trigger / entry point | What pre-exists | What the guided flow emphasizes | Heaviest regulated data |
|------------------|-----------------------|-----------------|---------------------------------|--------------------------|
| **Planned / Preventive** | Maintenance plan → scheduled order (exists before Tom arrives) | Order + task list / operations | Scan → pull up the **due checklist** → guided step-by-step execution → record **measurement readings / counters** → confirm + findings | Measurement readings, pass/fail vs. limits |
| **Proactive corrective** (condition / inspection-driven) | A finding during inspection or condition monitoring | Sometimes an inspection round | Capture the **finding + condition severity**, recommend a correction, hand off to planning | Condition assessment, severity |
| **Reactive corrective** (breakdown) | Unplanned fault discovered on the floor | Nothing — starts from zero | **Fast capture** (voice + photo), **malfunction start/end** (downtime!), breakdown indicator, immediate fix confirmation | Malfunction times, breakdown indicator |
| **Inspection / Calibration** | Scheduled or ad-hoc check | Calibration plan / limits | Guided **reading entry vs. acceptance limits**, automatic pass/fail, **e-signature** | Calibration result (Part 11 signature) |

**Why this matters for the design:** the *capture* step is not one screen. For a breakdown it's
a 30-second voice+photo report; for planned work it's a checklist with measurement entry; for an
inspection finding it's a condition assessment. The **scan + routing** is the shared spine; the
journeys diverge after it.

### 3.2 The lifecycle, reframed as a guided journey

```
  IDENTIFY              CAPTURE               ENRICH             EXECUTE             CLOSE
 (scan asset)        (varies by type)      (any device)       (work order)    (signed-off record)
┌───────────┐       ┌───────────┐        ┌───────────┐      ┌───────────┐     ┌───────────┐
│ Data      │       │ breakdown:│        │ AI fills   │      │ Confirm   │     │ What did  │
│ Matrix    │ ───▶  │ voice+photo│ ───▶  │ gaps; Tom  │ ──▶  │ ops, parts│ ──▶ │ you find/ │
│ scan →    │       │ planned:  │        │ confirms   │      │ used, time│     │ do? + sign│
│ route by  │       │ checklist │        │            │      │ readings  │     │           │
│ work type │       │ +readings │        │            │      │           │     │           │
└───────────┘       └───────────┘        └───────────┘      └───────────┘     └───────────┘
  shared spine        branch by type        quality            hands-on          ALCOA+
                                            nudges              reality           complete
```

The key idea: **identification is one scan**, **capture is near-zero friction and shaped by
the work type**, and quality is *progressively* assembled — never demanded all at once.

---

## 4. Functional Requirements

### FR-0 — Scan to start & route by maintenance type (shared front door)
- **FR-0.1** Identify the asset by scanning its **Data Matrix (2D) code** with the phone camera;
  parse **GS1 Data Matrix** to extract equipment number / serial / batch where encoded.
- **FR-0.2** Fallbacks when no scan is possible: "near me" (last-used / location) and free search.
- **FR-0.3** On successful scan, resolve the asset and look up **work due or open** on it
  (scheduled orders, existing notifications, calibration due), then **route** Tom into the
  matching journey (planned / proactive corrective / reactive corrective / inspection).
- **FR-0.4** If nothing is open and Tom initiates work, let him **pick the maintenance type**
  via clear choices; the chosen type configures the rest of the guided flow.
- **FR-0.5** The scanned asset identity is bound to the record for **attribution** and is
  retained as part of the source data (ALCOA+ Attributable).

### FR-1 — Quick Capture (phone, on the asset)
- **FR-1.1** Capture content is **shaped by maintenance type** (per §3.1): breakdown → fast
  voice+photo fault report; planned → guided checklist + measurement entry; inspection →
  reading-vs-limit entry; proactive → condition/finding assessment.
- **FR-1.2** One-tap **voice capture**: Tom describes the problem out loud; the system
  transcribes it and retains the **raw audio + transcript as the original source record**.
- **FR-1.3** One-tap **photo/video** capture of the fault; multiple media per report.
- **FR-1.4** AI proposes a **structured draft** from voice + photo: notification type,
  damage code, suspected cause, severity/priority, malfunction start — each shown as an
  **editable suggestion**, never a silent commit.
- **FR-1.5** Capture must complete in **under ~60 seconds** for a typical fault.
- **FR-1.6** Works **offline**; queues and syncs when connectivity returns
  (timestamps preserved at capture time — see §5 Contemporaneous).

### FR-2 — Conversational guided wizard
- **FR-2.1** A chat-style flow that asks **one simple question at a time** instead of
  presenting a dense form ("Where? → What's wrong? → Since when? → Still running?").
- **FR-2.2** Questions are **adaptive**: the AI skips what it already inferred and only
  asks for genuinely missing, regulatorily-required, or quality-critical data.
- **FR-2.3** Each step accepts **any modality** (tap a chip, speak, type, attach photo).
- **FR-2.4** A persistent, honest **completeness/quality meter** shows progress and *why*
  more is needed ("Root cause missing — needed for reliability trending").

### FR-3 — Tap-first structured input
- **FR-3.1** Replace free-text with **context-filtered choice chips** wherever a code/taxonomy
  exists (symptoms, damage codes, causes, locations) — pre-ranked by equipment history.
- **FR-3.2** Free text is the *fallback*, not the default; when used, AI maps it to codes
  for Tom to confirm.

### FR-4 — Enrich (any device)
- **FR-4.1** Notifications can be **completed later** at a desktop; capture and completion
  are distinct, resumable steps.
- **FR-4.2** AI highlights exactly the gaps blocking a "good" record and offers drafts.
- **FR-4.3** Real-time coaching with **specific, actionable** nudges (not "low quality").

### FR-5 — Execute & Close
- **FR-5.1** Guided work-order confirmation: operations done, parts used, time spent —
  tap/voice driven.
- **FR-5.2** Guided **findings capture at close**: "What did you actually find? What did you
  do?" — this is the highest-value reliability data and is most often skipped today.
- **FR-5.3** Closing a regulated record requires an **electronic signature** (see §6 Tier 3).
- **FR-5.4** **Measurement & reading capture** (planned / inspection / calibration): present each
  measurement point with its **acceptance limits**, capture the reading by tap/voice, and
  **auto-evaluate pass/fail**. An out-of-limit reading **escalates into a guided finding/notification**
  (bridging an inspection into proactive corrective). Readings are retained as **original
  measurement documents** (ALCOA+ Original/Attributable).

### FR-6 — Cross-cutting
- **FR-6.1** Resume any in-progress capture from any device.
- **FR-6.2** Full **bilingual** support (EN/DE), matching the existing app.
- **FR-6.3** Accessibility: large touch targets, high contrast, glove/noise tolerant.

---

## 5. Data Integrity Requirements (ALCOA+)

Every modality and AI behavior must preserve ALCOA+. This is non-negotiable.

| Principle | Requirement for the guided flow |
|-----------|--------------------------------|
| **Attributable** | Every value is tied to the **human** who confirmed it, not the AI. AI suggestions are logged separately as *suggestions*. |
| **Legible** | Voice transcripts, mapped codes, and final text are all human-readable and retained. |
| **Contemporaneous** | Timestamp is fixed at **moment of capture**, even when offline; sync time is recorded separately, never overwriting capture time. |
| **Original** | Raw voice audio and original photos are **retained as the source record**. The distinction between *AI-suggested* and *human-entered/confirmed* value is preserved. |
| **Accurate** | Human confirmation is mandatory for any regulated field; AI never finalizes. Date logic and code validity enforced. |
| **Complete** | Required fields enforced *progressively*; record cannot be *closed* (signed) until complete. |
| **Consistent** | Tap-to-select drives standardized codes/taxonomy. |
| **Enduring / Available** | Offline queue is durable; nothing is lost; records exportable. |

---

## 6. AI Proactivity — Risk-Tiered Model (the core regulatory mechanism)

> This is the answer to "how proactive should the AI be? — depending on regulatory requirements."

Each field and action is assigned a **regulatory tier**. The AI's autonomy is defined by the tier.
This keeps the experience maximally guided for low-risk data while keeping a human firmly in the
loop (per Part 11 / Annex 11 / FDA AI guidance) for anything that matters.

| Tier | Data / action examples | AI autonomy | Human role | Audit requirement |
|------|------------------------|-------------|------------|-------------------|
| **T0 — Convenience** | Asset identification from scan/GPS, UI prefill of non-record context | **Auto-fill silently** | May correct | Source of inference logged |
| **T1 — Regulated, low impact** | Notification type, functional location, work center | **Suggest; one-tap confirm** | Confirms each | Suggested vs. confirmed value stored |
| **T2 — Regulated, high impact** | Damage code, root cause, severity/priority, CAPA, findings text | **Draft + coach only**; cannot finalize | **Must actively author/edit**; original human input preserved | AI draft, human final, model & prompt version |
| **T3 — Signature events** | Closing a notification, approving/confirming a regulated record | **No auto-fill; no drafting of the attestation** | **Electronic signature** (2-factor) + meaning declaration | Signature linked to record; full event audit |

### AI Governance requirements (apply to all tiers)
- **AI-G1 — Transparency:** Anything AI-generated is visibly marked as a *suggestion* until a human acts on it.
- **AI-G2 — Explainability:** Every suggestion can show *why* ("based on 3 similar past failures on this pump").
- **AI-G3 — Override:** Human can always reject/edit; rejection is frictionless and logged.
- **AI-G4 — Suggestion audit trail:** Store {AI value, human final value, user, timestamp, model version, prompt version} for every AI-assisted field.
- **AI-G5 — Confidence:** AI exposes a confidence signal; low confidence escalates to an explicit human question rather than a silent prefill.
- **AI-G6 — No silent authorship:** The AI must never be the attributable author of a GxP record value.

---

## 7. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| **NFR-1** | Quick Capture usable one-handed, with gloves, in noise (voice + large targets). |
| **NFR-2** | Offline-first capture; durable local queue; conflict-safe sync. |
| **NFR-3** | Capture-to-submit p50 < 60s; AI suggestion latency target < 3s (degrade gracefully if AI/network unavailable — capture must never be blocked by the AI). |
| **NFR-4** | Built on SAPUI5 / Fiori for consistency with the existing suite; reuse Horizon theme. |
| **NFR-5** | EN/DE localization parity. |
| **NFR-6** | Accessibility: WCAG-aligned contrast, target sizes, screen-reader labels. |
| **NFR-7** | All AI calls and human confirmations are auditable per §6. |

---

## 8. Explicitly Out of Scope (for this concept phase)
- Backend electronic-signature *implementation* (we specify the requirement; the existing
  roadmap P1 "Electronic Signatures" covers build-out).
- New reliability metric engines (MTBF/MTTR/RPN) — consume existing/planned services.
- Changes to the Rule Manager and Auditor dashboards (separate personas/flows).

---

## 9. Assumptions
- A1: Equipment carries **Data Matrix (2D) codes**; where GS1-encoded, they may carry
  equipment / serial / batch. A searchable asset master exists for the fallback path.
- A2: The Gemini-based AI services can be extended for voice transcription, image
  understanding, and structured extraction (or complemented by suitable services).
- A3: The existing notification data model (type, damage/cause codes, malfunction dates,
  long text, work order) is the target structure to populate.
- A4: Offline capture on mobile is acceptable to the validation strategy provided ALCOA+
  contemporaneity rules (§5) are met.

---

## 10. Open Questions (to resolve before the concept design)

**Resolved**
- ~~Asset identification~~ → **Data Matrix (2D) scan**, primary front door (GS1 where available).
- ~~Maintenance scope~~ → **All maintenance types** (planned, proactive corrective, reactive
  corrective, inspection/calibration); the flow branches by type.

**Still open**
1. **Voice/vision AI:** Is extending Gemini to audio + image acceptable, or is there a
   preferred/validated service for transcription and image understanding in your GxP scope?
2. **Offline scope:** Is full offline capture required (basements/steel), or is "spotty but
   present" connectivity the realistic worst case?
3. **Signature reach:** Which lifecycle events legally require an e-signature in *your*
   regulatory interpretation — only Close, or also calibration/out-of-limit/CAPA confirmation?
4. **Source of "work due":** Does FR-0.3 (look up open/scheduled work on scan) read from SAP PM
   directly (orders, maintenance plans, measurement points) or via a sync/integration layer?
5. **Rollout:** Is the guided flow **additive** (a new "Scan to start" entry alongside today's
   analyzer/planner views) or does it **replace** the current create/detail experience?
   *(Working assumption: additive — a new unified technician front door — until told otherwise.)*

---

## 11. Success Criteria (how we'll know it worked)
- **SC-1** Median capture time for a new fault < 60s.
- **SC-2** Notification completeness rate ≥ 95% **at creation** (vs. fixed-up later).
- **SC-3** Root-cause identification rate ≥ 90% (today's target is aspirational; capture-time
  guidance should make it routine).
- **SC-4** AI quality score ≥ 70 on first submission for the majority of notifications.
- **SC-5** Zero ALCOA+ findings in audit: every value attributable to a human, contemporaneous,
  with originals retained.
```
