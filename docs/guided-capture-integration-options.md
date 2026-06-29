# Guided Capture — Integration Architecture Options

> **Status:** ✅ Accepted — **Option C confirmed (2026-06-29)**
> **Date:** 2026-06-29
> **Decides:** Open question from the requirements (FR-0.3 / Q4): how does the guided app
> **read** PM context ("work due", catalogs, equipment history) and **write** records back to
> SAP PM — including offline behaviour and AI enablement — in a GxP-regulated environment?

---

## 1. What the decision really involves

It is not one choice but three coupled paths:

1. **Read path** — getting "work due/open", catalogs (object part / damage / cause / activity),
   measuring points & limits, and equipment failure history (the AI needs history to rank codes).
2. **Write path** — getting notifications, confirmations, readings and signatures *into* SAP PM
   as the system of record.
3. **Connectivity** — the plant floor is intermittently connected (NFR-2), so offline capture +
   sync is effectively mandatory for the reactive/planned journeys.

### Non-negotiable principle (regulatory)
**SAP S/4HANA PM remains the GxP system of record.** Any on-device or middleware store is a
**transient cache + outbox**, never the record itself. The capture timestamp is fixed on-device
(ALCOA+ Contemporaneous) and carried through sync; sync time is recorded separately. This keeps
the validation scope (GAMP 5) bounded no matter which option we pick.

### Building blocks that exist today
- **S/4HANA OData APIs** — `API_MaintenanceNotification`, `API_MaintenanceOrder_002`
  (v1 deprecated since Cloud 2308), order confirmation and measuring-point/measurement-document
  services, published on the SAP Business Accelerator Hub.
- **SAP Service & Asset Manager (SSAM)** — SAP's packaged mobile maintenance app, native
  (iOS/Android) built on the **Mobile Development Kit (MDK)** + **SAP Mobile Services**, using
  **offline OData** and the **Mobile Application Integration Framework (MAIF)** for backend
  integration. MAIF ships with S/4HANA 1909+ on-premise.
- **SAP BTP** — where our AI/LLM services already live and where a sync/integration layer would run.

---

## 2. The options

### Option A — Direct live OData (online-only)
Our SAPUI5 + AI app calls S/4HANA PM OData services synchronously; no local store.

**Pros**
- Simplest architecture; least to build and validate.
- Real-time accuracy — "work due" is always current.
- Single source of truth; cleanest ALCOA+ story (no second copy).
- Reuses SAP authorizations and audit trail directly.

**Cons**
- **No offline** — fails the core plant-floor reality (basements, steel, dead zones).
- Latency per call; SAP load under many concurrent technicians.
- Capture is blocked whenever the network is — exactly when Tom is at the asset.
- AI history/aggregation still needs somewhere to run (extra reads against SAP).

> **Verdict:** viable only for the desktop *Enrich* path; insufficient on its own for floor capture.

---

### Option B — Adopt & extend SAP Service & Asset Manager (SSAM)
Use SAP's packaged mobile app; configure/extend it via MDK metadata.

**Pros**
- Offline, checklists, measurement readings, signatures, barcode & voice are **already built**.
- SAP-supported, roadmap-aligned, lower long-term maintenance for the plumbing.
- MAIF/offline OData handles delta sync, conflict, paging out of the box.
- Fastest route to a *standard* mobile maintenance capability.

**Cons**
- **UX is constrained to MDK metadata** — our radically guided, conversational, AI-first concept
  is hard or impossible to express; we'd be fighting the framework.
- AI enablement is awkward — MDK isn't built to host our suggestion/coaching loop.
- Licensing cost per user; MDK skill set required.
- Vendor lock-in to the SSAM model; the differentiated "make documentation effortless" vision
  gets diluted into "standard mobile forms."

> **Verdict:** great if the goal were a conventional mobile maintenance app; a poor fit for the
> *novel guided/AI experience* that is the entire point of this project.

---

### Option C — Custom SAPUI5 + AI experience on SAP Mobile Services offline OData  *(recommended)*
Build our own guided UX, but ride **SAP Mobile Services offline OData** for the sync spine and
keep the **AI services on BTP** beside it. S/4HANA stays system of record.

**Pros**
- **Full UX freedom** for the guided/voice/photo/conversational concept — our differentiator.
- Offline + delta sync + conflict handling provided by **validated SAP tech** (don't reinvent it).
- Clean separation: offline store = cache/outbox; **S/4HANA = record** → bounded validation scope.
- AI/LLM layer on BTP can pre-compute history-based code ranking and run the suggestion loop
  without ever authoring the record (AI-G6).
- Reuses SAP auth, and the same OData entities SSAM uses, so backend coverage is proven.

**Cons**
- More to build than B (we own the client UX and the AI integration).
- Requires SAP Mobile Services entitlement and offline-OData modelling effort.
- We must design the AI context store (equipment history for ranking) — added component.
- Offline + AI interplay needs care (AI suggestions may be degraded/unavailable offline — see §4).

> **Verdict:** best balance — SAP solves the hard, regulated plumbing; we own the experience that
> makes the project worth doing.

---

### Option D — Bespoke BTP middleware + custom offline store
Build our own integration/sync layer on BTP (e.g. Integration Suite + CAP service + a custom
offline mechanism), fully decoupled from SAP.

**Pros**
- Maximum control over data shape, caching, and AI aggregation.
- Can heavily pre-process/enrich PM data for the guided UX and AI.
- Not tied to SAP Mobile Services specifics.

**Cons**
- **Highest build + validation burden** — we'd reimplement delta sync, conflict resolution and
  offline integrity that SAP already provides (and has validated).
- A persistent middleware store raises the **ALCOA+/system-of-record** question sharply
  ("which copy is true?") and enlarges GAMP 5 scope.
- Most infrastructure to run, secure, and keep in step with SAP upgrades.
- Slowest time-to-value; highest risk.

> **Verdict:** only justified if SAP Mobile Services is unavailable or the data-shaping needs are
> extreme. Otherwise it's effort spent rebuilding solved problems.

---

## 3. Comparison matrix

Scale: ✅ strong · ◐ partial · ⚠️ weak

| Criterion | A — Live OData | B — Adopt SSAM | C — Custom on Mobile Svcs ✅ | D — Bespoke BTP |
|-----------|:---:|:---:|:---:|:---:|
| Offline / plant-floor fit | ⚠️ | ✅ | ✅ | ✅ |
| Real-time "work due" accuracy | ✅ | ◐ | ◐ | ◐ |
| Data integrity / SoR clarity (ALCOA+) | ✅ | ✅ | ✅ | ⚠️ |
| GxP validation scope (smaller = better) | ✅ | ✅ | ◐ | ⚠️ |
| AI enablement (suggestions/coaching) | ◐ | ⚠️ | ✅ | ✅ |
| UX freedom for the guided concept | ✅ | ⚠️ | ✅ | ✅ |
| Build effort / time-to-value | ✅ | ✅ | ◐ | ⚠️ |
| Licensing / run cost | ✅ | ⚠️ | ◐ | ◐ |
| Upgrade resilience / low lock-in | ◐ | ◐ | ◐ | ◐ |

---

## 4. How the recommended option (C) behaves online vs offline

| Capability | Online | Offline |
|------------|--------|---------|
| Scan & resolve asset | Live lookup | From synced equipment cache |
| "Work due" routing (FR-0.3) | Live/near-live | From last sync (clearly timestamped "as of …") |
| Voice/photo capture | Yes | Yes (stored locally) |
| AI suggestions / code ranking (T1/T2) | Full | **Degraded/deferred** — capture proceeds; AI enrichment runs on sync (capture is never blocked by AI, NFR-3) |
| Tap-to-select catalogs | Yes | From synced catalog cache |
| Submit / confirm / readings | Live write | Queued in outbox, synced on reconnect (capture timestamp preserved) |
| Electronic signature (T3) | Yes | Policy decision — see open items |

---

## 5. Recommendation

> **DECISION (2026-06-29): Option C confirmed by product owner.** Build the custom SAPUI5 + AI
> guided experience on SAP Mobile Services offline OData; S/4HANA PM is the system of record; AI
> layer on BTP; desktop *Enrich* path may use direct live OData (A) as a sub-mode. The §7 decisions
> below remain to be confirmed but do not block starting the UX concept.

**Adopt Option C** — a custom SAPUI5 + AI guided experience on **SAP Mobile Services offline OData**,
with **S/4HANA PM as the system of record** and the **AI layer on BTP**. For the desktop *Enrich*
path (always connected) we can use **direct live OData (Option A) as a sub-mode**, since offline
isn't needed there. This gives us SAP's validated offline/sync plumbing without surrendering the
guided/AI experience that justifies the project.

---

## 6. What would change the recommendation
- **Already own & run SSAM?** → re-weigh **B** (extend it) for speed, accepting UX constraints;
  or run **C alongside** SSAM for the differentiated capture flow.
- **ECC, not S/4HANA?** → OData/MAIF coverage differs; confirm available APIs (may push toward a
  thin integration layer, nudging C toward C+D).
- **No SAP Mobile Services entitlement** → **D** becomes the offline fallback (build the sync).
- **Offline depth is "spotty but present," not "truly offline"** → **A** alone may suffice for some
  journeys, simplifying everything.
- **Signature required offline** → strengthens the case for a robust on-device store (C/D) and a
  defined offline-signature policy.

---

## 7. Decisions needed to finalise
1. S/4HANA or ECC? Cloud or on-premise?
2. Is SAP Service & Asset Manager already licensed/deployed?
3. Is SAP Mobile Services available to us (entitlement)?
4. Required offline depth: truly offline, or intermittent-but-present?
5. Must electronic signatures be possible **offline**, or only when connected?
