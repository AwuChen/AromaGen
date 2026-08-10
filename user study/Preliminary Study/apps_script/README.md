# AromaGen Study 1 — Session Generator (deployment)

A Google Apps Script web app with two pages behind one URL:

- **Admin control panel** (`?admin=<token>`): paste participant IDs, pick 12
  or 24 exposures, click Generate. Each participant gets their own session
  link.
- **Participant session** (`?pid=P007`): a custom page (not a Google Form)
  that walks a participant through familiarity → trials → closing question,
  saving every answer to the shared spreadsheet the instant it's submitted.

Everything lands in one spreadsheet ("AromaGen User Study 1 - Master
Data"): `trials`, `participants`, `sessions`, `familiarity`, plus
`form_registry`/`form_links` (legacy, see below).

## Why two systems exist in this codebase

The first few participants (P1–P4) were generated as actual Google Forms
before this architecture changed. Google Forms cannot expose any
in-progress/unsubmitted state to Apps Script — if a participant closed the
tab partway through, everything they'd done was unrecoverably lost, with no
possible workaround from the backend side. That's a hard platform wall, not
a bug. The fix was to stop using Forms for the participant-facing UI and
build a small custom web app instead (`SessionEngine.gs` + `Session.html`),
which saves each trial to the spreadsheet immediately rather than waiting
for one final Submit.

**`FormBuilder.gs`'s Form-creation code is left intact and untouched** so
P1–P4's already-distributed links keep working — don't delete it. The
control panel now calls `generateSessionsForParticipants` (session engine),
not `generateFormsForParticipants` (legacy Forms path); the latter still
exists and still works if you ever need it, it's just not wired into the UI
anymore.

## Deploy (one-time setup)

1. Go to [script.google.com](https://script.google.com) → New project.
2. Rename it something like "AromaGen Study 1".
3. Create these files, copying contents exactly: `Code.gs`, `Data.gs`,
   `Assignment.gs`, `FormBuilder.gs`, `SessionEngine.gs` (all Script type),
   and `ControlPanel.html`, `Session.html` (Html type). Also set
   `appsscript.json`'s contents via Project Settings → "Show appsscript.json
   manifest file" if it doesn't appear as an editable file directly.
4. Deploy → New deployment → type "Web app". Execute as: **Me**. Who has
   access: **Anyone** (this is required — participants aren't you and
   can't be individually authorized, so the deployment itself must be
   public; the admin-token check in `doGet` is what actually protects the
   control panel, not the deployment's access setting).
5. Authorize when prompted.
6. Your admin URL is the deployment URL **plus `?admin=` and the token
   in `SessionEngine.gs`'s `ADMIN_TOKEN` constant**. Bookmark that exact
   URL. Never send it to a participant.

## Before running the real batch

**Test with 2 dummy participant IDs first**, and this time actually click
through a full session in a real browser — quit partway through one of
them on purpose and confirm the `trials`/`sessions`/`participants` rows
reflect exactly what you'd expect (partial data present, `session_status`
= "in_progress" not "completed"). I've verified the assignment algorithm
(Python, `study_design.py`) and confirmed the deployment is reachable
anonymously without a forced Google login, but I have no browser access in
this environment — I cannot watch the actual click-through UI execute, and
Apps Script wraps every response in a sandboxed iframe that tools like curl
can't see inside. The server-side logic has been read through carefully and
reasoned about, but "carefully reasoned" is not "watched work."

## What's in the master spreadsheet

- **trials**: one row per (participant, trial) — descriptor, cluster, all
  4 options, correct/selected index, confidence, familiarity for that
  descriptor, written the instant each trial is answered (not batched at
  session end). The tidy table for accuracy/confusion/confidence analyses.
- **participants**: one row per participant, created the moment their
  session is generated (`session_status: "not_started"`) and updated live
  as they progress (`"in_progress"` → `"completed"`) — this is where you
  see, at a glance, who quit and how far they got. Also holds the closing
  open-response.
- **sessions**: internal engine state — the frozen trial plan (`plan_json`,
  includes correct answers, never sent to the client), current step,
  status. Don't edit; useful to inspect if something looks wrong.
- **familiarity**: one row per (participant, word) familiarity rating.
- **form_registry** / **form_links**: legacy, only relevant to P1–P4's
  original Google Forms. Leave alone.

## Decisions and known limitations, stated rather than papered over

1. **Familiarity timing**: one grid up front covering every word the
   participant will see (target or distractor) across their session, not
   per-trial. Conflicts with the written SOP's per-trial familiarity
   question; built to the newer verbal instruction.
2. **The 30-second recovery wait is now genuinely enforced** (client-side
   countdown disables the Continue button) — an actual improvement over
   the Forms-based version, which could only ever describe the wait in
   text since Forms has no timer primitive.
3. **Distractors**: all 50 use the same-cluster/adjacent-cluster rule.
   Nobody has checked which of these 50 overlap Sniffin' Sticks / UPSIT's
   own item banks (which should take priority when they apply) — I don't
   have a verified copy of those proprietary answer keys.
4. **No demographics/screening question** is collected by this system.
   If you're not collecting it elsewhere (e.g. at intake/booking), you have
   no record of participants' olfactory-function status for the paper's
   validity section — confirm this is covered before writing up results.
5. **No response-time data.** Neither Google Forms nor this custom page
   captures per-question timing. Not available from this pipeline.
6. **Descriptor coverage**: mathematically bounded to spread ≤1 *within*
   any single cluster (provable property of "always assign the
   currently-least-used descriptor"); a spread of 1-2 *between* a 4-item
   and a 5-item cluster is an unavoidable consequence of requiring equal
   representation per cluster per participant, not an algorithm weakness.
   Live counts are visible in the control panel's section 4.
