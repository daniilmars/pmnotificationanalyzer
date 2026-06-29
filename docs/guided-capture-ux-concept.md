# Guided Capture — UX Concept

> **Status:** Draft v0.1 — Concept / wireframe level
> **Date:** 2026-06-29
> **Builds on:** `guided-capture-requirements.md` (v0.3), `guided-capture-integration-options.md` (Option C)
> **Scope of this doc:** the shared **Scan-to-start** front door + the two flagship journeys
> (**Reactive breakdown** and **Planned checklist**), plus the cross-cutting patterns (AI suggestion
> treatment, quality meter, close-out + e-signature, offline states). Other journeys reuse these patterns.

> Wireframes are ASCII, phone-width (the floor device). `[ ]` = button/chip, `(•)`/`( )` = radio,
> `▣`/`▢` = checkbox, `≡` = list, `🎤 📷 ⌨️` = modality affordances.

---

## 1. Design principles

1. **Scan first, type last.** Every session starts from a Data Matrix scan; typing is the last resort.
2. **One question at a time.** Never a wall of fields; a calm, conversational progression.
3. **Suggestions, never silent autofill.** The AI proposes; the human confirms. Provisional state
   is always visible (regulatory: ALCOA+ Attributable, AI-G1/G7).
4. **Progressive quality.** Completeness is assembled step by step; the meter explains *why* more helps.
5. **Modality-agnostic steps.** Any step accepts tap / voice / photo / type interchangeably.
6. **Capture is never blocked by the AI or the network.** Degrade gracefully; enrich on sync (NFR-3).
7. **The work type shapes the screens.** Shared spine, divergent journeys (requirements §3.1).

---

## 2. Information architecture

The guided flow is **additive** — a new primary entry "**Report / Start work**" that opens the
Scan-to-start front door. The existing Worklist / dashboards remain for planners & QA.

```
Suite Launchpad
├── ▶ Start work (Scan to start)        ← NEW guided flow (Tom)   ★ this doc
├── Notifications (Worklist/Analyzer)    ← existing (Maria/Tom desktop Enrich)
├── Quality Dashboard                    ← existing (Thomas)
├── Reliability Dashboard                ← existing (Elena)
└── Audit Trail                          ← existing (Auditor)
```

---

## 3. The reusable AI-suggestion pattern (how the risk tiers look on screen)

This single pattern renders consistently everywhere the AI contributes; the **tier** (requirements §6)
controls how much confirmation friction it carries.

```
 T0  Convenience          T1  Low impact            T2  High impact            T3  Signature
 ───────────────         ─────────────────         ──────────────────         ───────────────
 Auto-filled, quiet      Suggested, 1-tap          Drafted, must edit/own     No AI. Human attests.
 ┌─────────────────┐     ┌─────────────────┐       ┌──────────────────────┐   ┌──────────────────┐
 │ Pump P-101  ✎   │     │ ✨ Type: Malfunc.│       │ ✨ Suggested cause:   │   │ Sign to close    │
 │ (from scan)     │     │ [✓ Confirm] [Edit]│       │ "Seal wear"          │   │ User ID [______] │
 └─────────────────┘     └─────────────────┘       │ ┌──────────────────┐ │   │ Password[______] │
                          chip shows ✨ = AI        │ │ tap to confirm/  │ │   │ Meaning: Closed  │
                                                    │ │ edit — required  │ │   │ [ Sign ]         │
                                                    │ └──────────────────┘ │   └──────────────────┘
                                                    │ Why? ▸ 3 similar…    │
                                                    └──────────────────────┘
```

- **✨ marks anything AI-originated** until a human acts on it; once confirmed/edited it loses the ✨
  and is attributed to the human.
- **"Why? ▸"** expands the explanation (AI-G2). **Edit** is always one tap away (AI-G3).
- T2 fields **cannot be left as the raw AI value** — the human must confirm or change (AI-G7).

---

## 4. Shared front door — Scan to start

### S1 — Start / Scan
```
┌──────────────────────────────┐
│  ‹ Suite        Start work    │
├──────────────────────────────┤
│                              │
│        ┌───────────┐         │
│        │  [▣▣ ▣▣]  │  live   │
│        │  scan box │  camera │
│        └───────────┘         │
│   Point at the Data Matrix    │
│        on the equipment       │
│                              │
│   [ 🔦 Torch ]  [ ⌨️ Enter ID ]│
│                              │
│   Recent:  ≡ P-101  ≡ V-204   │
│   Near me: ≡ Line 3 assets    │
└──────────────────────────────┘
```
- Camera-first; torch for dark plant areas; manual entry & "recent/near me" fallbacks (FR-0.2, NFR-8).

### S2 — Asset resolved → route by what's due
After a successful scan we parse GS1 AIs (01/21/10) → resolve equipment → show open/scheduled work.
```
┌──────────────────────────────┐
│  ‹ Back         Pump P-101    │
├──────────────────────────────┤
│ Pump P-101  ·  SN 48213       │  ← T0 from scan (quiet)
│ Line 3 · Centrifugal pump     │
│ Status: ● Running             │
│ ─────────────────────────────│
│ Work due / open    as of 09:12│  ← "as of" = honest when offline
│ ┌──────────────────────────┐ │
│ │ 🛠  PM order 4500123       │ │
│ │    Preventive · due today │ │  → Planned journey (§6)
│ ├──────────────────────────┤ │
│ │ 🔎 Calibration due in 3d  │ │  → Inspection journey
│ └──────────────────────────┘ │
│                              │
│  Nothing here? Start new:     │
│  [ ⚠ Report a problem ]       │  → Reactive journey (§5)
│  [ + Other work ]             │  → type picker (S3)
└──────────────────────────────┘
```

### S3 — Maintenance type picker (only when nothing is open / "Other work")
```
┌──────────────────────────────┐
│  ‹ Back     What are you doing?│
├──────────────────────────────┤
│ (•) ⚠ Reactive — something    │
│        broke / malfunction    │
│ ( ) 🔧 Planned / preventive   │
│ ( ) 🔎 Inspection / calibration│
│ ( ) 📋 Proactive — I noticed  │
│        something to fix later │
│                              │
│              [ Continue ]     │
└──────────────────────────────┘
```
Choice sets notification/order type behind the scenes (M2/PM02, PM03, PM05, M1/PM01).

---

## 5. Journey A — Reactive breakdown capture (fastest, highest-friction-today)

Goal: a complete **M2 malfunction report** with a full failure-data chain in **< 60s** (SC-1).

### S4 — Quick capture (voice + photo, the "30-second report")
```
┌──────────────────────────────┐
│  ‹ Cancel    Pump P-101  ⚠     │
├──────────────────────────────┤
│  Tell me what's wrong.        │
│                              │
│      ┌────────────────┐       │
│      │      🎤         │  hold │
│      │   (tap/hold)   │  or   │
│      └────────────────┘  tap  │
│  “Bearing on the drive end is │  ← live transcript
│   screaming, smells hot,      │
│   started about an hour ago”  │
│                              │
│  [ 📷 Add photo ]  ●●  (2)     │
│  [ ⌨️ Type instead ]           │
│                              │
│              [ Next → ]       │
└──────────────────────────────┘
```
- Raw audio + transcript + photos retained as **original source record** (FR-1.2/1.3, ALCOA+ Original).

### S5 — AI draft: confirm the failure-data chain
The AI turns voice+photo into a structured **draft** (T1/T2 chips). Tom confirms/edits — fast.
```
┌──────────────────────────────┐
│  ‹ Back     Review (auto-draft)│
├──────────────────────────────┤
│ ✨ I drafted this — check it:  │
│                              │
│ Object part   ✨ Bearing, DE  │ T2 [✓][edit]
│ Failure mode  ✨ Overheating  │ T2 [✓][edit]
│ Cause         ✨ Lubrication? │ T2  tap to confirm ▸ Why?
│ Detection     ✨ Operator     │ T1 [✓]
│ Severity      ✨ High         │ T1 [✓][edit]
│ Malfunction   ✨ ~08:10 today │ T1 [✓][edit]
│ start                         │
│ Breakdown?    (•) Yes ( ) No  │  ← explicit, drives MTBF
│ ─────────────────────────────│
│ Each ✨ is a suggestion until  │
│ you confirm it.               │
│              [ Looks right → ]│
└──────────────────────────────┘
```
- Codes come from context-ranked catalogs (FR-3.1, FR-7). Tapping a chip opens a short pick list,
  not a keyboard. "Why?" explains the suggestion (AI-G2).

### S6 — Quality meter + submit
```
┌──────────────────────────────┐
│  ‹ Back        Almost done    │
├──────────────────────────────┤
│ Quality  ▓▓▓▓▓▓▓▓░░  82  Good  │  ← scored vs failure-data chain (FR-7.5)
│ ✓ Object part  ✓ Mode  ✓ Cause│
│ ✓ Detection    ✓ Times        │
│ ◑ Add a photo of the label →  │  ← only genuinely useful nudges
│ ─────────────────────────────│
│ This creates Malfunction      │
│ report (M2) on Pump P-101.    │
│                              │
│        [ Submit report ]      │
│  Offline → will sync at 🛜    │
└──────────────────────────────┘
```
- Submit always works; offline it queues to the outbox (capture timestamp fixed) and syncs later.

---

## 6. Journey B — Planned checklist execution + measurement readings

Goal: execute a scheduled **PM order**, capture **measurement readings vs. limits**, confirm work.

### S7 — Checklist overview (pulled from the order/task list)
```
┌──────────────────────────────┐
│  ‹ Back   PM 4500123 · P-101  │
├──────────────────────────────┤
│ Preventive · due today        │
│ Progress  ▓▓▓░░░░  3 / 7      │
│ ─────────────────────────────│
│ ▣ 1 Visual inspection         │
│ ▣ 2 Check coupling alignment  │
│ ▣ 3 Vibration reading         │
│ ▢ 4 Bearing temperature  →    │  ← measurement step (S8)
│ ▢ 5 Lubricate bearings        │
│ ▢ 6 Tighten foundation bolts  │
│ ▢ 7 Replace filter element    │
│ ─────────────────────────────│
│        [ Continue step 4 → ]  │
└──────────────────────────────┘
```

### S8 — Step execution + measurement reading (limits & auto pass/fail)
```
┌──────────────────────────────┐
│  ‹ Back   Step 4 of 7         │
├──────────────────────────────┤
│ Bearing temperature (DE)      │
│ Measuring point MP-771        │
│                              │
│   Reading: [   __ ] °C  🎤    │  ← tap/voice numeric entry
│   Limit: 40–75 °C             │
│                              │
│   ░░░░░|▓▓▓▓▓▓▓|░░░  gauge     │
│        40      75             │
│                              │
│   [ 📷 Photo ]  [ Note ]      │
│              [ Save reading → ]│
└──────────────────────────────┘
```
- Reading saved as a **measurement document** vs. the measuring point's range (FR-5.4, ALCOA+ Original).

### S9 — Out-of-limit → auto-escalate to a finding
If the reading breaches the limit, the system offers to spin up a proactive corrective finding —
inspection bridges into corrective (FR-5.4).
```
┌──────────────────────────────┐
│  ⚠ 88 °C is above limit (75)  │
├──────────────────────────────┤
│ Recorded. This looks like a   │
│ problem worth a finding.      │
│                              │
│ ✨ Draft finding:             │
│  Mode: Overheating            │ T2 [✓][edit]
│  Cause: Lubrication?          │ T2  confirm ▸ Why?
│                              │
│ [ Create finding ]  [ Not now]│
└──────────────────────────────┘
```

---

## 7. Cross-cutting close-out

### S10 — Findings capture (the highest-value reliability data, usually skipped)
```
┌──────────────────────────────┐
│  ‹ Back     Wrap up           │
├──────────────────────────────┤
│ What did you find & do?       │
│      ┌────────────────┐  🎤   │
│      │  speak or type │       │
│      └────────────────┘       │
│ ✨ Activity: Replaced bearing │ T2 [✓][edit]
│ ✨ Parts: 1× 6205-2RS         │ T1 [✓][edit]
│ Time spent: [ 1.5 ] h         │
│              [ Next → ]       │
└──────────────────────────────┘
```

### S11 — Electronic signature (T3 — only when required)
```
┌──────────────────────────────┐
│  ‹ Back     Sign to close     │
├──────────────────────────────┤
│ You are closing PM 4500123    │
│ on Pump P-101.                │
│ ─────────────────────────────│
│ Meaning:  (•) Performed       │  ← signature meaning (§11.50)
│           ( ) Reviewed        │
│ User ID   [________________]  │  ← 2 components (§11.200)
│ Password  [________________]  │
│                              │
│ Name + UTC time will be       │
│ recorded with the record.     │
│        [ Sign & close ]       │
└──────────────────────────────┘
```
- No AI here. Manifestation (name + UTC + meaning) + record linkage + retention per Part 11.
- Offline-signature behaviour is an open policy item (requirements §10 Q3).

---

## 8. Desktop Enrich (always-connected sub-mode, Option A)

Same data model, roomier layout — for completing/correcting later. Reuses today's Object page
(now `ObjectPageLayout`) with the AI panel; the **✨ suggestion pattern** and quality meter carry over.
The failure-data chain (FR-7) appears as a dedicated section with the same confirm/edit chips.

---

## 9. Key states

| State | Treatment |
|-------|-----------|
| **Offline** | Banner "Offline — will sync"; "as of <time>" on cached lists; submit → outbox; AI enrichment deferred. |
| **AI unavailable** | Steps fall back to manual tap-to-select; no ✨ drafts; capture proceeds normally (NFR-3). |
| **Scan unreadable** | Torch tip, retry, then manual ID / recent / near-me (NFR-8). |
| **Low AI confidence** | The AI asks an explicit question instead of pre-filling (AI-G5). |
| **Empty "work due"** | Straight to "Report a problem" / type picker — never a dead end. |

---

## 10. Traceability (screen → requirements)

| Screen | Requirements |
|--------|--------------|
| S1 Scan | FR-0.1/0.2, NFR-8 |
| S2 Route | FR-0.3, integration Option C §4 |
| S3 Type picker | FR-0.4, §3.1 |
| S4 Quick capture | FR-1.2/1.3/1.5, ALCOA+ Original |
| S5 AI draft / chain | FR-1.4, FR-3.1, FR-7, §6 T1/T2, AI-G1/G2 |
| S6 Quality + submit | FR-2.4, FR-7.5, FR-1.6, SC-1/2/4 |
| S7 Checklist | FR-1.1 (planned) |
| S8 Reading | FR-5.4 |
| S9 Out-of-limit | FR-5.4 (escalation) |
| S10 Findings | FR-5.2, FR-7.1/7.2 |
| S11 Signature | FR-5.3, §6 T3 |
| Desktop Enrich | FR-4.1/4.2/4.3 |

---

## 11. Open UX questions / next steps
1. **Fidelity:** is this wireframe level enough to proceed, or do you want hi-fi visual mockups
   (Horizon-themed) for the flagship screens next?
2. **Voice review:** how much should the voice transcript be shown/edited before AI structuring?
3. **Checklist source granularity:** how rich are your real PM task lists (do operations carry
   measuring points today)? Affects S7/S8.
4. **Signature meaning options:** which meanings are valid in your SOPs (Performed / Reviewed /
   Approved …)?
