/**
 * Session state machine for the Internal Pilot Study.
 *
 * Two-page architecture, same split as the Preliminary Study:
 *   - AdminPanel.html (?admin=<token>) -- where you key in P1/P2/P3 etc
 *     (individually or as a batch), overview descriptor coverage, and get
 *     back a direct link per participant.
 *   - DataCollection.html (?admin=<token>&pid=<name>) -- the actual trial-
 *     running flow for ONE participant, opened via the link the admin
 *     panel gave you. Requires the admin token too (not just `pid` alone,
 *     unlike the Preliminary Study's open participant links) because this
 *     page shows full trial detail including correct answers -- nobody
 *     but the experimenter should ever open it, there's no legitimate
 *     "participant opens their own link" case here (they're blindfolded
 *     and never touch a screen), so there's no reason to leave it
 *     unauthenticated.
 *
 * Every screen shows full trial detail (target, correct slot, which
 * physical object or AromaGen composition each option needs) -- the
 * experimenter needs that information to actually conduct the trial.
 *
 * Step numbering (stored in sessions.current_step) -- derived from
 * TRIALS_PER_BLOCK (PilotData.gs) rather than hardcoded, so this doesn't
 * silently break if the descriptor list's cluster count ever changes
 * again (it already has once -- see STEP_* constants below):
 *   0                                  = briefing screen
 *   1                                  = cartridge-check screen for block_order[0]
 *   2..(1+TRIALS_PER_BLOCK)            = trial N of block_order[0]
 *   (2+TRIALS_PER_BLOCK)               = cartridge-check/rest screen for block_order[1]
 *   (3+TRIALS_PER_BLOCK)..(2+2*TRIALS_PER_BLOCK) = trial N of block_order[1]
 *   (3+2*TRIALS_PER_BLOCK)             = done
 *
 * IMPORTANT LIMITATION, stated rather than hidden: this Apps Script web app
 * cannot trigger the real AromaGen device (Apps Script runs in Google's
 * cloud; it has no network path to your local AromaGen backend or its
 * Bluetooth hardware). Every screen that requires an AromaGen composition
 * ("aromagen_target" / "aromagen_near" options) tells the experimenter
 * exactly what to compose (the target word) so they can trigger it
 * themselves on the actual AromaGen frontend/device, running side-by-side
 * with this control panel -- this app handles sequencing, balancing,
 * counterbalancing, timing, and data logging, not hardware control.
 */

var STEP_BRIEFING = 0;
var STEP_CARTRIDGE_1 = 1;
var STEP_BLOCK1_TRIAL_START = 2;
var STEP_BLOCK1_TRIAL_END = STEP_BLOCK1_TRIAL_START + TRIALS_PER_BLOCK - 1;
var STEP_CARTRIDGE_2 = STEP_BLOCK1_TRIAL_END + 1;
var STEP_BLOCK2_TRIAL_START = STEP_CARTRIDGE_2 + 1;
var STEP_BLOCK2_TRIAL_END = STEP_BLOCK2_TRIAL_START + TRIALS_PER_BLOCK - 1;
var STEP_DONE = STEP_BLOCK2_TRIAL_END + 1;

/** Creates a session row for `name` if one doesn't already exist (idempotent
 * -- safe to call for a name that's already been generated, just returns
 * without changes). `tallies` is mutated in place as new plans are built,
 * same "pass the running tally, keep mutating across calls" contract as
 * elsewhere in this project. Returns {created: bool, blockOrder or null}. */
function ensureSession_(masterSs, name, tallies, seqIndex) {
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var existing = getSessionRow_(sessionsSheet, name);
  if (existing) {
    var existingPlan = JSON.parse(existing.plan_json);
    return { created: false, blockOrder: existingPlan.block_order };
  }

  var plan = buildParticipantPlan_(seqIndex, tallies, seqIndex * 7919 + Date.now() % 100000);
  var now = new Date();
  sessionsSheet.appendRow([name, JSON.stringify(plan), "in_progress", 0, now, ""]);

  var participantsSheet = masterSs.getSheetByName("participants");
  participantsSheet.appendRow([name, seqIndex, plan.block_order.join(","), "in_progress", now, ""]);

  return { created: true, blockOrder: plan.block_order };
}

function pilotDataCollectionLink_(name) {
  return ScriptApp.getService().getUrl() + "?admin=" + ADMIN_TOKEN + "&pid=" + encodeURIComponent(name);
}

/**
 * Called from AdminPanel.html. namesText: newline/comma-separated raw text
 * from the textarea -- works identically for one name or many ("the system
 * should be able to tell when I am generating multiple" = just splits on
 * newlines/commas and loops). Already-generated names are skipped (not
 * re-randomized/duplicated) but still get their link returned, so
 * re-submitting a bigger list that includes earlier names is safe and
 * idempotent -- same pattern as the Preliminary Study's
 * generateFormsForParticipants/generateSessionsForParticipants.
 */
function generateParticipantsBatch(namesText) {
  var names = (namesText || "")
    .split(/[\n,]/)
    .map(function (s) { return s.trim(); })
    .filter(function (s) { return s.length > 0; });
  if (names.length === 0) throw new Error("No participant names provided.");
  var uniqueNames = Array.from(new Set(names));
  if (uniqueNames.length !== names.length) {
    throw new Error("Duplicate participant names in the input -- each name must be unique.");
  }

  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var tallies = computePilotTallies_(masterSs);
    var nextSeq = nextSeqIndex_(masterSs);

    var results = uniqueNames.map(function (name) {
      var result = ensureSession_(masterSs, name, tallies, nextSeq);
      if (result.created) nextSeq += 1; // only consume a sequence slot for genuinely new sessions
      return {
        name: name,
        link: pilotDataCollectionLink_(name),
        blockOrder: result.blockOrder,
        status: result.created ? "generated" : "already_existed"
      };
    });

    return results;
  } finally {
    lock.releaseLock();
  }
}

/** Used by DataCollection.html on load: ensures a session exists for this
 * participant (creating one on the fly if they were never generated via
 * the admin panel -- e.g. someone opened a hand-typed link) and returns
 * the current screen view. Idempotent -- safe to call every time the page
 * loads/reloads, including mid-session resume. */
function startPilotSession(participantName) {
  participantName = (participantName || "").trim();
  if (!participantName) throw new Error("Participant name is required.");

  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var tallies = computePilotTallies_(masterSs);
    var seqIndex = nextSeqIndex_(masterSs);
    ensureSession_(masterSs, participantName, tallies, seqIndex);
    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

function getSessionRow_(sheet, participantName) {
  var data = sheet.getDataRange().getValues();
  var header = data[0];
  var nameCol = header.indexOf("participant_name");
  for (var r = 1; r < data.length; r++) {
    if (data[r][nameCol] === participantName) {
      var record = {};
      header.forEach(function (h, i) { record[h] = data[r][i]; });
      record._rowIndex = r + 1;
      return record;
    }
  }
  return null;
}

function headerIndex_(sheet, name) {
  var header = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  return header.indexOf(name);
}

/** Builds the view for whatever screen `current_step` currently points at.
 * Safe to call repeatedly / on page reload -- purely reads state, no
 * mutation. */
function getPilotSessionView(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var row = getSessionRow_(sessionsSheet, participantName);
  if (!row) return { found: false };

  var plan = JSON.parse(row.plan_json);
  var step = Number(row.current_step);
  var blockOrder = plan.block_order;

  if (row.status === "completed" || step >= STEP_DONE) {
    return { found: true, screen: "done", participantName: participantName };
  }

  if (step === STEP_BRIEFING) {
    return { found: true, screen: "briefing", participantName: participantName };
  }

  if (step === STEP_CARTRIDGE_1 || step === STEP_CARTRIDGE_2) {
    var blockNumber = (step === STEP_CARTRIDGE_1) ? 1 : 2;
    var setId = blockOrder[blockNumber - 1];
    return {
      found: true,
      screen: "cartridge_check",
      participantName: participantName,
      blockNumber: blockNumber,
      odorantSetId: setId,
      odorantSetLabel: ODORANT_SET_LABELS[setId],
      odorants: ODORANT_SETS[setId],
      targets: plan.blocks[setId].map(function (t) { return { target: t.target, cluster: t.cluster }; }),
      isRestBreak: (step === STEP_CARTRIDGE_2)
    };
  }

  var blockNumber2, trialIndexInBlock, setId2;
  if (step >= STEP_BLOCK1_TRIAL_START && step <= STEP_BLOCK1_TRIAL_END) {
    blockNumber2 = 1;
    trialIndexInBlock = step - STEP_BLOCK1_TRIAL_START + 1; // 1..TRIALS_PER_BLOCK
  } else {
    blockNumber2 = 2;
    trialIndexInBlock = step - STEP_BLOCK2_TRIAL_START + 1; // 1..TRIALS_PER_BLOCK
  }
  setId2 = blockOrder[blockNumber2 - 1];
  var trial = plan.blocks[setId2][trialIndexInBlock - 1];

  return {
    found: true,
    screen: "trial",
    participantName: participantName,
    blockNumber: blockNumber2,
    trialNumber: trialIndexInBlock,
    totalTrialsInBlock: TRIALS_PER_BLOCK,
    odorantSetId: setId2,
    odorantSetLabel: ODORANT_SET_LABELS[setId2],
    target: trial.target,
    cluster: trial.cluster,
    options: trial.options,      // [{kind, word}, ...] in presentation (1..4) order
    correctSlot: trial.correct_slot // 0-indexed
  };
}

function submitBriefingAck(participantName) {
  return advanceStep_(participantName, 0, 1);
}

function submitCartridgeCheckAck(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var row = getSessionRow_(sessionsSheet, participantName);
  if (!row) throw new Error("Session not found.");
  var step = Number(row.current_step);
  if (step === STEP_CARTRIDGE_1) return advanceStep_(participantName, STEP_CARTRIDGE_1, STEP_BLOCK1_TRIAL_START);
  if (step === STEP_CARTRIDGE_2) return advanceStep_(participantName, STEP_CARTRIDGE_2, STEP_BLOCK2_TRIAL_START);
  throw new Error("Not at a cartridge-check step (current_step=" + step + ").");
}

/**
 * familiarity/confidence: 1-7 integers. selectedSlot: 1-4 (which of the 4
 * presented smells the participant picked, as numbered on screen).
 * Appends one row to `trials` immediately, then advances current_step.
 */
function submitTrial(participantName, familiarity, selectedSlot, confidence) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var inBlock1 = (step >= STEP_BLOCK1_TRIAL_START && step <= STEP_BLOCK1_TRIAL_END);
    var inBlock2 = (step >= STEP_BLOCK2_TRIAL_START && step <= STEP_BLOCK2_TRIAL_END);
    if (!(inBlock1 || inBlock2)) {
      throw new Error("Not at a trial step (current_step=" + step + ").");
    }

    var plan = JSON.parse(row.plan_json);
    var blockNumber, trialIndexInBlock;
    if (inBlock1) {
      blockNumber = 1; trialIndexInBlock = step - STEP_BLOCK1_TRIAL_START + 1;
    } else {
      blockNumber = 2; trialIndexInBlock = step - STEP_BLOCK2_TRIAL_START + 1;
    }
    var setId = plan.block_order[blockNumber - 1];
    var trial = plan.blocks[setId][trialIndexInBlock - 1];

    var selectedIndex = Number(selectedSlot) - 1; // 0-indexed
    var isCorrect = (selectedIndex === trial.correct_slot);

    var trialsSheet = masterSs.getSheetByName("trials");
    var opts = trial.options;
    trialsSheet.appendRow([
      participantName, blockNumber, setId, trialIndexInBlock,
      trial.target, trial.cluster,
      opts[0].kind, opts[0].word, opts[1].kind, opts[1].word,
      opts[2].kind, opts[2].word, opts[3].kind, opts[3].word,
      trial.correct_slot + 1, Number(familiarity), selectedIndex + 1, isCorrect,
      Number(confidence), new Date()
    ]);

    var nextStep = step + 1;
    var isSessionDone = (nextStep === STEP_DONE);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(nextStep);
    if (isSessionDone) {
      sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "status") + 1).setValue("completed");
      sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "completed_at") + 1).setValue(new Date());
      var participantsSheet = masterSs.getSheetByName("participants");
      var pRow = getSessionRow_(participantsSheet, participantName);
      if (pRow) {
        participantsSheet.getRange(pRow._rowIndex, headerIndex_(participantsSheet, "status") + 1).setValue("completed");
        participantsSheet.getRange(pRow._rowIndex, headerIndex_(participantsSheet, "completed_at") + 1).setValue(new Date());
      }
    }

    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

function advanceStep_(participantName, expectedStep, nextStep) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    if (step !== expectedStep) {
      // Idempotent: if we're already past this step (e.g. a double-click),
      // just return the current view instead of erroring.
      if (step > expectedStep) return getPilotSessionView(participantName);
      throw new Error("Unexpected step: expected " + expectedStep + ", found " + step);
    }
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(nextStep);
    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}
