# Guided Capture — UX Concept Requirements

> **Status:** Draft v0.1 — Requirements phase
> **Date:** 2026-06-21
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
| **Workflow coverage** | **Full lifecycle** — Quick Capture → Enrich → Execute (work order) → Close/Confirm |
| **Devices** | **Mixed** — phone-first on the floor, desktop for completion/review |
| **Input modalities** | **All** — voice, photo/video, tap-to-select, conversational AI wizard |
| **AI proactivity** | **Risk-tiered** — autonomy steps down as regulatory weight steps up (see §6) |

### 3.1 The lifecycle, reframed as a guided journey

```
   CAPTURE                ENRICH              EXECUTE              CLOSE
 (on the asset)        (any device)        (work order)      (signed-off record)
┌───────────┐        ┌───────────┐       ┌───────────┐       ┌───────────┐
│ 30-second │        │ AI fills   │       │ Confirm   │       │ What did  │
│ voice +   │  ───▶  │ gaps; Tom  │ ───▶  │ ops, parts│ ───▶  │ you find/ │
│ photo     │        │ confirms   │       │ used, time│       │ do? + sign│
└───────────┘        └───────────┘       └───────────┘       └───────────┘
   minimal              quality              hands-on             ALCOA+
   friction             nudges               reality              complete
```

The key idea: **capture must be near-zero friction**, and quality is *progressively*
assembled — never demanded all at once.

---

## 4. Functional Requirements

### FR-1 — Quick Capture (phone, on the asset)
- **FR-1.1** Identify the asset with the least effort: scan QR/NFC/barcode on equipment,
  pick from "near me" (last-used / GPS / location beacon), or search as fallback.
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
- A1: Equipment carries scannable identifiers (QR/NFC/barcode) **or** a searchable master exists.
- A2: The Gemini-based AI services can be extended for voice transcription, image
  understanding, and structured extraction (or complemented by suitable services).
- A3: The existing notification data model (type, damage/cause codes, malfunction dates,
  long text, work order) is the target structure to populate.
- A4: Offline capture on mobile is acceptable to the validation strategy provided ALCOA+
  contemporaneity rules (§5) are met.

---

## 10. Open Questions (to resolve before the concept design)
1. **Asset identification:** Do your assets already have QR/NFC/barcodes, or must we rely on search?
2. **Voice/vision AI:** Is extending Gemini to audio + image acceptable, or is there a
   preferred/validated service for transcription and image understanding in your GxP scope?
3. **Offline scope:** Is full offline capture required (basements/steel), or is "spotty but
   present" connectivity the realistic worst case?
4. **Signature reach:** Which lifecycle events legally require an e-signature in *your*
   regulatory interpretation — only Close, or also root-cause/CAPA confirmation?
5. **Rollout:** Is the new guided flow **additive** (a new "Report a Fault" entry alongside
   today's analyzer), or does it **replace** the current create/detail experience?

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
