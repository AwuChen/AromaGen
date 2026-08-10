/**
 * Custom participant-facing session engine -- replaces Google Forms for
 * all NEW participants (the first few participants' already-distributed
 * Google Form links keep working via FormBuilder.gs's legacy path, left
 * untouched, so nothing already sent out breaks).
 *
 * Why this exists: Google Forms exposes ZERO visibility into an
 * unsubmitted response -- if a participant closes the tab mid-session,
 * nothing before the final Submit is ever recoverable, by design, with no
 * workaround possible from Apps Script. This engine saves every trial the
 * instant it's answered, so closing the tab at any point preserves
 * everything up to that point, and marks the session's true status
 * ("not_started" / "in_progress" / "completed") directly in the
 * `participants` sheet -- visible at a glance, no guessing who finished.
 *
 * Session state lives in the `sessions` sheet: participant_id, n_exposures,
 * plan_json (the full trial plan -- vocab + per-trial descriptor/options/
 * correctIndex, generated once at session-creation time by the SAME
 * buildAssignment() used for the legacy Forms path), status, current_step
 * (0 = familiarity, 1..N = trial N, N+1 = closing, N+2 = done),
 * session_url, created_at, completed_at.
 *
 * SECURITY NOTE: plan_json (which includes each trial's correctIndex) is
 * never sent to the client. getSessionState() strips it down to only what
 * that step's UI needs -- the 4 (already-shuffled) option words, nothing
 * indicating which one is correct. Correctness is computed exclusively
 * server-side in submitTrial_(), from the server's own copy of the plan --
 * the client never asserts, and is never trusted to assert, its own score.
 */

// Generated once via `node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`.
// Gates access to the admin control panel now that the web app must be
// deployed with "Anyone with the link" access (participants, who aren't
// you, need to be able to open their session page) -- without this gate,
// anyone stripping the ?pid= off their link would land on your control
// panel. Only doGet() in Code.gs checks this; keep it out of any URL you
// share with participants.
// REDACTED for version control -- set your own token here (regenerate via
// the node command above) before deploying. The real value used in
// production is not committed to this repo.
var ADMIN_TOKEN = "REDACTED_SET_YOUR_OWN_TOKEN_HERE";

function baseWebAppUrl_() {
  return ScriptApp.getService().getUrl();
}

/**
 * Same balancing/incremental-tally logic as the legacy Forms path
 * (computeDescriptorTally_, buildAssignment), but creates `sessions` +
 * `participants` rows instead of Google Form objects. Shares the same
 * form_links-based duplicate-ID guard so a participant who already has
 * either a legacy Form or a session never gets a second one.
 */
function generateSessionsForParticipants(participantIdsText, nExposures, seed) {
  var ids = participantIdsText
    .split(/[\n,]/)
    .map(function (s) { return s.trim(); })
    .filter(function (s) { return s.length > 0; });
  if (ids.length === 0) throw new Error("No participant IDs provided.");
  var uniqueIds = Array.from(new Set(ids));
  if (uniqueIds.length !== ids.length) {
    throw new Error("Duplicate participant IDs in the input -- each ID must be unique.");
  }

  var masterSs = getOrCreateMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var linksSheet = masterSs.getSheetByName("form_links");
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var existingIds = {};
    linksSheet.getDataRange().getValues().slice(1).forEach(function (r) { existingIds[r[0]] = true; });
    sessionsSheet.getDataRange().getValues().slice(1).forEach(function (r) { existingIds[r[0]] = true; });

    var newIds = uniqueIds.filter(function (id) { return !existingIds[id]; });
    var skippedIds = uniqueIds.filter(function (id) { return existingIds[id]; });
    if (newIds.length === 0) {
      return { sessions: [], skipped: skippedIds, masterSpreadsheetUrl: masterSs.getUrl() };
    }

    var tally = computeDescriptorTally_(masterSs);
    var assignment = buildAssignment(newIds, Number(nExposures), tally, seed ? Number(seed) : undefined);

    var results = [];
    var now = new Date();
    var participantsSheet = masterSs.getSheetByName("participants");
    newIds.forEach(function (pid) {
      var trials = assignment[pid];
      var vocab = uniqueVocabulary_(trials);
      var plan = { vocab: vocab, trials: trials };
      var sessionUrl = baseWebAppUrl_() + "?pid=" + encodeURIComponent(pid);

      sessionsSheet.appendRow([pid, Number(nExposures), JSON.stringify(plan), "not_started", 0,
        sessionUrl, now, ""]);

      upsertRowByKey_(participantsSheet, "participant_id", pid, {
        participant_id: pid, n_exposures_condition: Number(nExposures),
        form_id: "SESSION:" + pid, form_url: sessionUrl,
        is_duplicate_submission: false, session_status: "not_started"
      });

      results.push({ participantId: pid, sessionUrl: sessionUrl });
    });

    return { sessions: results, skipped: skippedIds, masterSpreadsheetUrl: masterSs.getUrl() };
  } finally {
    lock.releaseLock();
  }
}

function getSessionRow_(sessionsSheet, pid) {
  var data = sessionsSheet.getDataRange().getValues();
  var header = data[0];
  for (var r = 1; r < data.length; r++) {
    if (data[r][0] === pid) {
      var record = {};
      header.forEach(function (h, i) { record[h] = data[r][i]; });
      record._rowIndex = r + 1;
      return record;
    }
  }
  return null;
}

/** What the client needs to render the CURRENT step only -- see the
 * security note at the top of this file for why plan_json never leaves
 * the server whole. */
/** Admin-only: the full ground-truth plan (target descriptor per trial,
 * in presentation order) for one or more participants -- what
 * getSessionState() deliberately withholds from the participant-facing
 * page. Used for the experimenter's own reference (which stimulus to
 * dispense at each trial) and for spot-checking. Temporary Code.gs route
 * removed after use -- not part of the permanent admin surface. */
function getGroundTruthForParticipants_(pids) {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var out = {};
  pids.forEach(function (pid) {
    var row = getSessionRow_(sessionsSheet, pid);
    if (!row) { out[pid] = { error: "not found" }; return; }
    var plan = JSON.parse(row.plan_json);
    out[pid] = {
      status: row.status,
      currentStep: row.current_step,
      trials: plan.trials.map(function (t, i) {
        return { trialNumber: i + 1, cluster: t.cluster, descriptor: t.descriptor };
      })
    };
  });
  return out;
}

function getSessionState(pid) {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var row = getSessionRow_(sessionsSheet, pid);
  if (!row) return { found: false };

  if (row.status === "completed") return { found: true, status: "completed" };

  var plan = JSON.parse(row.plan_json);
  var N = plan.trials.length;
  var step = Number(row.current_step);

  if (step === 0) {
    return { found: true, status: "in_progress", step: "familiarity", vocab: plan.vocab };
  }
  if (step >= 1 && step <= N) {
    var trial = plan.trials[step - 1];
    return {
      found: true, status: "in_progress", step: "trial",
      trialNumber: step, totalTrials: N, isFirstTrial: step === 1,
      options: trial.options
    };
  }
  if (step === N + 1) {
    return { found: true, status: "in_progress", step: "closing" };
  }
  return { found: true, status: "completed" }; // step >= N+2, safety fallback
}

function submitFamiliarity(pid, ratings) {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, pid);
    if (!row) return { ok: false, error: "Session not found." };
    if (row.status === "completed") return { ok: false, error: "Session already completed." };
    if (Number(row.current_step) !== 0) return { ok: true, alreadyRecorded: true }; // idempotent re-submit

    var plan = JSON.parse(row.plan_json);
    var familiaritySheet = masterSs.getSheetByName("familiarity");
    var now = new Date();
    plan.vocab.forEach(function (word) {
      var rating = ratings[word];
      upsertRowByKey2_(familiaritySheet, "participant_id", pid, "descriptor", word, {
        participant_id: pid, descriptor: word,
        familiarity_1to5: rating !== undefined ? Number(rating) : "",
        recorded_at: now
      });
    });

    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(1);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "status") + 1).setValue("in_progress");

    var participantsSheet = masterSs.getSheetByName("participants");
    upsertRowByKey_(participantsSheet, "participant_id", pid, { session_status: "in_progress" });

    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

function submitTrial(pid, trialNumber, selectedOption, confidence) {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, pid);
    if (!row) return { ok: false, error: "Session not found." };
    if (row.status === "completed") return { ok: false, error: "Session already completed." };

    var currentStep = Number(row.current_step);
    trialNumber = Number(trialNumber);
    if (trialNumber !== currentStep) {
      // Not the step the server thinks we're on -- either a stale
      // double-submit (trialNumber < currentStep, already recorded, treat
      // as idempotent success) or a client desync (trialNumber >
      // currentStep, reject rather than trust an out-of-order write).
      if (trialNumber < currentStep) return { ok: true, alreadyRecorded: true };
      return { ok: false, error: "Out of sequence submission." };
    }

    var plan = JSON.parse(row.plan_json);
    var trial = plan.trials[trialNumber - 1];
    var selectedIndex = trial.options.indexOf(selectedOption);
    var isCorrect = selectedIndex === trial.correctIndex;

    var familiaritySheet = masterSs.getSheetByName("familiarity");
    var famRow = findRowByKey2_(familiaritySheet, "participant_id", pid, "descriptor", trial.descriptor);
    var familiarity = famRow ? famRow.familiarity_1to5 : "";

    var trialsSheet = masterSs.getSheetByName("trials");
    upsertRowByKey2_(trialsSheet, "participant_id", pid, "trial_number", trialNumber, {
      participant_id: pid, trial_number: trialNumber, cluster: trial.cluster,
      descriptor: trial.descriptor,
      option_a: trial.options[0], option_b: trial.options[1],
      option_c: trial.options[2], option_d: trial.options[3],
      correct_index: trial.correctIndex, selected_index: selectedIndex,
      is_correct: isCorrect, confidence_1to5: Number(confidence),
      familiarity_1to5_for_descriptor: familiarity, response_timestamp: new Date(),
      form_id: "SESSION:" + pid, is_duplicate_submission: false
    });

    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1)
      .setValue(trialNumber + 1);

    return { ok: true, isLastTrial: trialNumber === plan.trials.length };
  } finally {
    lock.releaseLock();
  }
}

function submitClosing(pid, text) {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, pid);
    if (!row) return { ok: false, error: "Session not found." };
    if (row.status === "completed") return { ok: true, alreadyRecorded: true };

    var plan = JSON.parse(row.plan_json);
    var expectedStep = plan.trials.length + 1;
    if (Number(row.current_step) !== expectedStep) {
      return { ok: false, error: "Out of sequence submission." };
    }

    var now = new Date();
    var participantsSheet = masterSs.getSheetByName("participants");
    upsertRowByKey_(participantsSheet, "participant_id", pid, {
      overall_experience_open_response: text, submitted_at: now, session_status: "completed"
    });

    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "status") + 1).setValue("completed");
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1)
      .setValue(expectedStep + 1);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "completed_at") + 1).setValue(now);

    return { ok: true };
  } finally {
    lock.releaseLock();
  }
}

// ---- generic sheet upsert helpers (header-name-driven, so column order
// changes / migrations don't silently break these) ----

function headerIndex_(sheet, name) {
  var header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  return header.indexOf(name);
}

function upsertRowByKey_(sheet, keyCol, keyValue, updates) {
  var header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var keyIdx = header.indexOf(keyCol);
  var data = sheet.getDataRange().getValues();
  for (var r = 1; r < data.length; r++) {
    if (data[r][keyIdx] === keyValue) {
      Object.keys(updates).forEach(function (field) {
        var idx = header.indexOf(field);
        if (idx !== -1) sheet.getRange(r + 1, idx + 1).setValue(updates[field]);
      });
      return;
    }
  }
  var newRow = header.map(function (h) { return updates[h] !== undefined ? updates[h] : ""; });
  sheet.appendRow(newRow);
}

function findRowByKey2_(sheet, keyCol1, keyValue1, keyCol2, keyValue2) {
  var header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var idx1 = header.indexOf(keyCol1), idx2 = header.indexOf(keyCol2);
  var data = sheet.getDataRange().getValues();
  for (var r = 1; r < data.length; r++) {
    if (data[r][idx1] === keyValue1 && data[r][idx2] === keyValue2) {
      var record = {};
      header.forEach(function (h, i) { record[h] = data[r][i]; });
      return record;
    }
  }
  return null;
}

function upsertRowByKey2_(sheet, keyCol1, keyValue1, keyCol2, keyValue2, updates) {
  var header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var idx1 = header.indexOf(keyCol1), idx2 = header.indexOf(keyCol2);
  var data = sheet.getDataRange().getValues();
  for (var r = 1; r < data.length; r++) {
    if (data[r][idx1] === keyValue1 && data[r][idx2] === keyValue2) {
      Object.keys(updates).forEach(function (field) {
        var idx = header.indexOf(field);
        if (idx !== -1) sheet.getRange(r + 1, idx + 1).setValue(updates[field]);
      });
      return;
    }
  }
  var newRow = header.map(function (h) { return updates[h] !== undefined ? updates[h] : ""; });
  sheet.appendRow(newRow);
}
