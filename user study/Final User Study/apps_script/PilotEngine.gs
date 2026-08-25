/**
 * Session state machine for the Final User Study.
 *
 * Two-page architecture, same split as before:
 *   - AdminPanel.html (?admin=<token>) -- where you key in P1/P2/P3 etc
 *     (individually or as a batch), overview descriptor coverage, and get
 *     back a direct link per participant.
 *   - DataCollection.html (?admin=<token>&pid=<name>) -- the actual trial-
 *     running flow for ONE participant, opened via the link the admin
 *     panel gave you. Requires the admin token too, same reasoning as
 *     before (every screen reveals correct answers; no participant ever
 *     opens either page themselves).
 *
 * SINGLE FIXED ODORANT SET: unlike the Internal Pilot Study, there is no
 * odorant-set condition to counterbalance anymore -- every participant
 * uses the same BASE_ODORANT_SET (PilotData.gs). Each participant does
 * ONE PASS of TRIALS_PER_PARTICIPANT trials (12, one per cluster), not two
 * blocks. `odorant_set` is still recorded on every trial/feedback row
 * (constant value) for logging consistency, per explicit instruction.
 *
 * Feedback sub-flow, per trial (unchanged from the Internal Pilot Study):
 *   1. Initial similarity (1-7): real physical reference vs. the ORIGINAL
 *      AromaGen target reconstruction. Logged as round_number = 0, with
 *      round_input_text fixed to "THIS IS THE INITIAL ROUND FROM SYSTEM
 *      WITHOUT ANY FEEDBACK" (round 0 always exists for every trial).
 *   2. Up to MAX_FEEDBACK_ROUNDS (5) rounds of iterative refinement.
 *   All similarity ratings (round 0 and rounds 1-5) share ONE column,
 *   `similarity_rating`, in the feedback sheet -- not two separate columns.
 *
 * TWO SECTIONS: Section 1 is everything above (12 3-AFC trials, each with
 * its own feedback sub-flow). Section 2, "Freeform Aroma Recreation", runs
 * once a participant finishes all of Section 1: a briefing, then
 * SECTION2_CREATIONS_PER_PARTICIPANT (PilotData.gs, currently 5) separate
 * creations, each its own intake (what the participant asked AromaGen to
 * create + the base odorant ratio AromaGen produced for it) followed
 * DIRECTLY by up to MAX_FEEDBACK_ROUNDS rounds of freeform feedback
 * (rating-scale condition has been removed; every participant is freeform) --
 * UNLIKE Section 1, there is no "initial rating" step before the first
 * feedback round: no real physical reference exists yet to compare
 * against at that point, so intake leads straight into round 1. (Each
 * feedback round still ends in its own rating, same as Section 1.) Logged
 * to its own `Freeform Creation` sheet (PilotData.gs), keyed by
 * creation_index (1..SECTION2_CREATIONS_PER_PARTICIPANT), not
 * `trials`/`feedback`.
 *
 * Step numbering (stored in sessions.current_step) -- derived from
 * TRIALS_PER_PARTICIPANT and SECTION2_CREATIONS_PER_PARTICIPANT:
 *   0                                       = Section 1 briefing screen
 *   1                                       = cartridge-check screen (once, no swap)
 *   2..(1+TRIALS_PER_PARTICIPANT)           = Section 1 trial N
 *   (2+TRIALS_PER_PARTICIPANT)              = Section 2 briefing screen
 *   (3+TRIALS_PER_PARTICIPANT)..
 *   (2+TRIALS_PER_PARTICIPANT+SECTION2_CREATIONS_PER_PARTICIPANT)
 *                                           = Section 2 creation N (intake,
 *                                              then feedback -- same
 *                                              current_step per creation,
 *                                              distinguished by trial_phase,
 *                                              exactly like a Section 1
 *                                              trial's afc->feedback toggle)
 *   (3+TRIALS_PER_PARTICIPANT+SECTION2_CREATIONS_PER_PARTICIPANT)
 *                                           = done
 *
 * IMPORTANT LIMITATION, stated rather than hidden: this Apps Script web app
 * cannot trigger the real AromaGen device or read its frontend live (Apps
 * Script runs in Google's cloud; no network path to your local AromaGen
 * backend/frontend or the device's Bluetooth hardware). Applies to the
 * 3-AFC trial's AromaGen options, the feedback sub-flow's "resulting
 * composition"/starting ratios, AND Section 2's intake (request + ratio)
 * -- the experimenter reads these off the real AromaGen frontend and
 * enters/adjusts them here. Every such field is editable afterward.
 */

var STEP_BRIEFING = 0;
var STEP_CARTRIDGE_CHECK = 1;
var STEP_TRIAL_START = 2;
var STEP_TRIAL_END = STEP_TRIAL_START + TRIALS_PER_PARTICIPANT - 1;
var STEP_SECTION2_BRIEFING = STEP_TRIAL_END + 1;
var STEP_SECTION2_START = STEP_SECTION2_BRIEFING + 1;
var STEP_SECTION2_END = STEP_SECTION2_START + SECTION2_CREATIONS_PER_PARTICIPANT - 1;
var STEP_DONE = STEP_SECTION2_END + 1;

var TRIAL_PHASE_AFC = "afc";
var TRIAL_PHASE_FEEDBACK = "feedback";
var PHASE_INTAKE = "intake"; // Section 2 main step's pre-feedback phase

var KIND_LABEL_ = {
  aromagen_target: "aromagen target",
  aromagen_near: "aromagen near",
  real_near: "real near"
};

function formatOption_(opt) {
  return opt.word + " (" + KIND_LABEL_[opt.kind] + ")";
}

/** Creates a session row for `name` if one doesn't already exist (idempotent).
 * `targetTally`/`distractorTally`/`clusterUsedSets` mutated in place as new
 * plans are built. Returns {created: bool, feedbackType}. */
function ensureSession_(masterSs, name, targetTally, distractorTally, seqIndex, clusterUsedSets, condition) {
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var existing = getSessionRow_(sessionsSheet, name);
  if (existing) {
    var existingPlan = JSON.parse(existing.plan_json);
    return { created: false, feedbackType: existingPlan.feedback_type, condition: existingPlan.condition || DEFAULT_CONDITION };
  }

  var plan = buildParticipantPlan_(seqIndex, targetTally, distractorTally, seqIndex * 7919 + Date.now() % 100000, clusterUsedSets, condition);
  var now = new Date();
  sessionsSheet.appendRow([name, JSON.stringify(plan), "in_progress", 0, TRIAL_PHASE_AFC, now, ""]);

  var participantsSheet = masterSs.getSheetByName("participants");
  participantsSheet.appendRow([
    name, seqIndex, plan.odorant_set, plan.feedback_type,
    "in_progress", now, "", plan.condition
  ]);

  return { created: true, feedbackType: plan.feedback_type, condition: plan.condition };
}

function pilotDataCollectionLink_(name) {
  return ScriptApp.getService().getUrl() + "?admin=" + ADMIN_TOKEN + "&pid=" + encodeURIComponent(name);
}

/**
 * Called from AdminPanel.html. namesText: newline/comma-separated raw text
 * from the textarea -- works identically for one name or many. Already-
 * generated names are skipped (not re-randomized/duplicated) but still get
 * their link returned, so re-submitting a bigger list that includes
 * earlier names is safe and idempotent.
 */
/** condition: "ai" or "expert" (Admin Panel toggle) -- applied to every
 * NEWLY generated name in this batch; already-existing sessions keep
 * whatever condition they were originally generated under. */
function generateParticipantsBatch(namesText, condition) {
  var names = (namesText || "")
    .split(/[\n,]/)
    .map(function (s) { return s.trim(); })
    .filter(function (s) { return s.length > 0; });
  if (names.length === 0) throw new Error("No participant names provided.");
  var uniqueNames = Array.from(new Set(names));
  if (uniqueNames.length !== names.length) {
    throw new Error("Duplicate participant names in the input -- each name must be unique.");
  }
  if (condition && !CONDITIONS[condition]) {
    throw new Error("Unknown condition: " + condition);
  }

  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var tallies = computePilotTallies_(masterSs);
    var clusterUsedSets = computeClusterUsedSets_(masterSs);
    var nextSeq = nextSeqIndex_(masterSs);

    var results = uniqueNames.map(function (name) {
      var result = ensureSession_(masterSs, name, tallies.targets, tallies.distractors, nextSeq, clusterUsedSets, condition);
      if (result.created) nextSeq += 1; // only consume a sequence slot for genuinely new sessions
      return {
        name: name,
        link: pilotDataCollectionLink_(name),
        feedbackType: result.feedbackType,
        condition: result.condition,
        status: result.created ? "generated" : "already_existed"
      };
    });

    return results;
  } finally {
    lock.releaseLock();
  }
}

/** Used by DataCollection.html on load: ensures a session exists for this
 * participant and returns the current screen view. Idempotent -- safe to
 * call every time the page loads/reloads, including mid-session resume. */
function startPilotSession(participantName) {
  participantName = (participantName || "").trim();
  if (!participantName) throw new Error("Participant name is required.");

  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var tallies = computePilotTallies_(masterSs);
    var clusterUsedSets = computeClusterUsedSets_(masterSs);
    var seqIndex = nextSeqIndex_(masterSs);
    ensureSession_(masterSs, participantName, tallies.targets, tallies.distractors, seqIndex, clusterUsedSets);
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

/**
 * Forces a cell's number format to plain integer ("0"), overriding any
 * stale/inherited date-time formatting. Without this, small integers
 * (1-7 rating values) written into these columns can get silently
 * reinterpreted by Sheets as date serial numbers -- e.g. a rating of 5
 * displaying (and reading back via getValues(), which returns a JS Date
 * for any date-formatted cell regardless of the stored value) as
 * "01/04/1900", since day 5 after the Sheets epoch (Dec 30, 1899) is Jan
 * 4, 1900. The underlying number is never lost, but downstream reads
 * (this app's own re-reads of roundsSoFar, or anyone opening the sheet
 * directly) would misinterpret it without this. Call on every write to a
 * ratings column (row 1-indexed, col 1-indexed).
 */
function forceNumberFormat_(sheet, row, col) {
  if (col > 0) sheet.getRange(row, col).setNumberFormat("0");
}

/** Rounds already submitted for one trial, keyed by round_number (0 =
 * initial similarity). Used both to resume a reloaded page mid-feedback
 * and to decide the next round number to submit. */
function getFeedbackRoundsSoFar_(masterSs, participantName, trialIndex) {
  var sheet = masterSs.getSheetByName("feedback");
  var data = sheet.getDataRange().getValues();
  var header = data[0];
  var nameCol = header.indexOf("participant_name");
  var trialCol = header.indexOf("trial_index");
  var rounds = [];
  for (var r = 1; r < data.length; r++) {
    if (data[r][nameCol] === participantName && Number(data[r][trialCol]) === trialIndex) {
      var record = {};
      header.forEach(function (h, i) { record[h] = data[r][i]; });
      rounds.push(record);
    }
  }
  rounds.sort(function (a, b) { return Number(a.round_number) - Number(b.round_number); });
  return rounds;
}

/** Same idea as getFeedbackRoundsSoFar_ but for Section 2's "Freeform
 * Creation" sheet, filtered by (participant, creation_index) since each
 * participant now does SECTION2_CREATIONS_PER_PARTICIPANT creations. */
function getFreeformCreationRoundsSoFar_(masterSs, participantName, creationIndex) {
  var sheet = masterSs.getSheetByName("Freeform Creation");
  var data = sheet.getDataRange().getValues();
  var header = data[0];
  var nameCol = header.indexOf("participant_name");
  var creationCol = header.indexOf("creation_index");
  var rounds = [];
  for (var r = 1; r < data.length; r++) {
    if (data[r][nameCol] === participantName && Number(data[r][creationCol]) === creationIndex) {
      var record = {};
      header.forEach(function (h, i) { record[h] = data[r][i]; });
      rounds.push(record);
    }
  }
  rounds.sort(function (a, b) { return Number(a.round_number) - Number(b.round_number); });
  return rounds;
}

/** Even-split starting ratios for the base odorant set -- fallback only,
 * used when this trial's llm_generated_base_odorant_ratio text (captured
 * on the trial screen, see submitTrial) is blank or didn't parse. */
function evenSplitRatios_(names) {
  var n = names.length;
  var each = Math.round((1 / n) * 100) / 100;
  var ratios = {};
  names.forEach(function (name) { ratios[name] = each; });
  return ratios;
}

/** Reads back the llm_generated_base_odorant_ratio text this trial's
 * experimenter typed on the trial screen (submitTrial), for the rating-
 * scale feedback screen to auto-initialize its sliders from -- NOT a live
 * fetch from AromaGen (see IMPORTANT LIMITATION at the top of this file),
 * just reading what was already captured by hand for this same trial. */
function getTrialLlmRatioText_(masterSs, participantName, trialIndex) {
  var sheet = masterSs.getSheetByName("trials");
  var data = sheet.getDataRange().getValues();
  var header = data[0];
  var nameCol = header.indexOf("participant_name");
  var trialCol = header.indexOf("trial_index");
  var ratioCol = header.indexOf("llm_generated_base_odorant_ratio");
  if (ratioCol === -1) return "";
  for (var r = data.length - 1; r >= 1; r--) {
    if (data[r][nameCol] === participantName && Number(data[r][trialCol]) === trialIndex) {
      return data[r][ratioCol] || "";
    }
  }
  return "";
}

/** Starting ratios for the rating-scale feedback screen: parsed from this
 * trial's captured llm_generated_base_odorant_ratio text if present and it
 * parsed to at least one odorant, otherwise an even split. */
function startingRatiosForTrial_(masterSs, participantName, trialIndex) {
  var text = getTrialLlmRatioText_(masterSs, participantName, trialIndex);
  var parsed = parseRatioText_(text, BASE_ODORANT_SET);
  if (Object.keys(parsed).length === 0) return evenSplitRatios_(BASE_ODORANT_SET);
  var ratios = {};
  BASE_ODORANT_SET.forEach(function (name) { ratios[name] = parsed[name] !== undefined ? parsed[name] : 0; });
  return ratios;
}

/** Section 2 equivalent of startingRatiosForTrial_: parses this creation's
 * captured ratio text (see submitSection2Intake / getSection2Intake_) the
 * same way, falling back to an even split. */
function startingRatiosForSection2_(section2LlmRatio) {
  var parsed = parseRatioText_(section2LlmRatio, BASE_ODORANT_SET);
  if (Object.keys(parsed).length === 0) return evenSplitRatios_(BASE_ODORANT_SET);
  var ratios = {};
  BASE_ODORANT_SET.forEach(function (name) { ratios[name] = parsed[name] !== undefined ? parsed[name] : 0; });
  return ratios;
}

/**
 * Section 2's per-creation intake (request_text + llm_ratio) is stored as
 * one JSON blob on the session row, `section2_creations_json`, keyed by
 * creation_index string ("1".."SECTION2_CREATIONS_PER_PARTICIPANT") --
 * NOT one flat column pair like the earlier single-creation design, since
 * there are now several independent creations per participant. Parsed
 * fresh from the session row's raw JSON text every time rather than
 * cached, since sessions rows are re-fetched per request anyway.
 */
function getSection2CreationsMap_(row) {
  if (!row.section2_creations_json) return {};
  try {
    return JSON.parse(row.section2_creations_json) || {};
  } catch (e) {
    return {};
  }
}

/** This creation's stored {requestText, llmRatioText}, or nulls if the
 * intake screen for it hasn't been submitted yet. */
function getSection2Intake_(row, creationIndex) {
  var entry = getSection2CreationsMap_(row)[String(creationIndex)];
  return entry || { requestText: "", llmRatioText: "" };
}

/** Builds the view for whatever screen `current_step`/`trial_phase`
 * currently point at. Safe to call repeatedly / on page reload -- purely
 * reads state, no mutation. */
function getPilotSessionView(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var sessionsSheet = masterSs.getSheetByName("sessions");
  var row = getSessionRow_(sessionsSheet, participantName);
  if (!row) return { found: false };

  var plan = JSON.parse(row.plan_json);
  var step = Number(row.current_step);
  var phase = row.trial_phase || TRIAL_PHASE_AFC;
  var feedbackType = plan.feedback_type;
  var condition = plan.condition || DEFAULT_CONDITION;

  if (row.status === "completed" || step >= STEP_DONE) {
    return { found: true, screen: "done", participantName: participantName };
  }

  if (step === STEP_BRIEFING) {
    return { found: true, screen: "briefing", participantName: participantName };
  }

  if (step === STEP_CARTRIDGE_CHECK) {
    return {
      found: true,
      screen: "cartridge_check",
      participantName: participantName,
      odorants: BASE_ODORANT_SET,
      condition: condition,
      targets: plan.trials.map(function (t) {
        return { target: t.target, cluster: t.cluster, expertRatio: condition === "expert" ? expertRatioFor_(t.target) : null };
      })
    };
  }

  if (step >= STEP_TRIAL_START && step <= STEP_TRIAL_END) {
    var trialIndex = step - STEP_TRIAL_START + 1; // 1..TRIALS_PER_PARTICIPANT
    var trial = plan.trials[trialIndex - 1];
    // In the "expert" condition, every option (target AND distractors alike)
    // gets its expert-derived reference ratio attached so the experimenter
    // can see it next to the word wherever it's shown -- real_near options
    // are real physical objects, not AromaGen compositions, but a lookup is
    // harmless/null for those too since EXPERT_RATIOS is only ever keyed by
    // the 50 study descriptors, not by odorant names.
    var optionsWithRatios = trial.options.map(function (o) {
      return { kind: o.kind, word: o.word, expertRatio: condition === "expert" ? expertRatioFor_(o.word) : null };
    });

    if (phase === TRIAL_PHASE_AFC) {
      return {
        found: true,
        screen: "trial",
        participantName: participantName,
        trialNumber: trialIndex,
        totalTrials: TRIALS_PER_PARTICIPANT,
        target: trial.target,
        cluster: trial.cluster,
        condition: condition,
        targetExpertRatio: condition === "expert" ? expertRatioFor_(trial.target) : null,
        options: optionsWithRatios,      // [{kind, word, expertRatio}, ...] in presentation (1..3) order
        correctSlot: trial.correct_slot, // 0-indexed
        odorantNames: BASE_ODORANT_SET // for the ratio field's live "Parsed as:" preview
      };
    }

    // phase === feedback
    var odorantsWithDescriptions = BASE_ODORANT_SET.map(function (name) {
      return { name: name, description: ODORANT_DESCRIPTIONS[name] || "" };
    });
    var roundsSoFar = getFeedbackRoundsSoFar_(masterSs, participantName, trialIndex);
    var initialRound = roundsSoFar.filter(function (r) { return Number(r.round_number) === 0; })[0] || null;
    var feedbackRounds = roundsSoFar.filter(function (r) { return Number(r.round_number) > 0; });
    var nextRoundNumber = feedbackRounds.length > 0
      ? Math.max.apply(null, feedbackRounds.map(function (r) { return Number(r.round_number); })) + 1
      : 1;

    // Rating-scale sliders for the NEXT round should start from wherever the
    // most recent round left off (its saved ratios = the resulting
    // composition after that round's feedback was applied), not reset back
    // to the trial screen's original ratio every round. Only round 1 (no
    // prior rounds saved yet) uses the trial-screen ratio.
    var latestRound = feedbackRounds.length > 0
      ? feedbackRounds[feedbackRounds.length - 1] // getFeedbackRoundsSoFar_ returns them sorted by round_number
      : null;
    var defaultRatios;
    if (latestRound && latestRound.round_ratios_json) {
      try {
        defaultRatios = JSON.parse(latestRound.round_ratios_json);
      } catch (e) {
        defaultRatios = null;
      }
    }
    if (!defaultRatios) {
      defaultRatios = startingRatiosForTrial_(masterSs, participantName, trialIndex);
    }

    return {
      found: true,
      screen: "feedback",
      participantName: participantName,
      trialNumber: trialIndex,
      totalTrials: TRIALS_PER_PARTICIPANT,
      target: trial.target,
      cluster: trial.cluster,
      condition: condition,
      targetExpertRatio: condition === "expert" ? expertRatioFor_(trial.target) : null,
      feedbackType: feedbackType,
      feedbackTypeLabel: FEEDBACK_TYPES[feedbackType],
      maxRounds: MAX_FEEDBACK_ROUNDS,
      odorants: odorantsWithDescriptions,
      defaultRatios: defaultRatios,
      // The ratio the experimenter typed on the trial screen for this same
      // trial (see getTrialLlmRatioText_) -- shown again here so they can
      // reliably re-trigger the exact same AromaGen composition on the
      // device before rating initial similarity, without having to recall
      // or scroll back to what they entered a screen ago.
      llmRatioText: getTrialLlmRatioText_(masterSs, participantName, trialIndex),
      initialSimilaritySubmitted: !!initialRound,
      initialSimilarity: initialRound ? Number(initialRound.similarity_rating) : null,
      roundsSoFar: feedbackRounds.map(function (r) {
        return {
          roundNumber: Number(r.round_number),
          inputText: r.round_input_text,
          ratiosJson: r.round_ratios_json,
          resultingCompositionJson: r.resulting_composition_json,
          similarity: Number(r.similarity_rating)
        };
      }),
      nextRoundNumber: nextRoundNumber
    };
  }

  if (step === STEP_SECTION2_BRIEFING) {
    return { found: true, screen: "section2_briefing", participantName: participantName };
  }

  // step in [STEP_SECTION2_START, STEP_SECTION2_END]
  var creationIndex = step - STEP_SECTION2_START + 1; // 1..SECTION2_CREATIONS_PER_PARTICIPANT

  if (phase !== TRIAL_PHASE_FEEDBACK) {
    // Default/intake phase -- covers PHASE_INTAKE and any leftover phase
    // value from Section 1 (harmless, just means "not yet in feedback").
    return {
      found: true,
      screen: "section2_intake",
      participantName: participantName,
      creationNumber: creationIndex,
      totalCreations: SECTION2_CREATIONS_PER_PARTICIPANT,
      odorantNames: BASE_ODORANT_SET
    };
  }

  // No "initial match rating" STEP for Section 2 -- unlike Section 1 (which
  // compares to a real physical reference before any feedback), Section 2
  // goes straight from intake into feedback round 1. round_number 0 DOES
  // still exist in the Freeform Creation sheet (submitSection2Intake logs
  // it -- the initial AromaGen-generated composition itself, for a
  // complete record), it's just excluded here from the UI-facing
  // roundsSoFar/nextRoundNumber so it never appears as an editable
  // "Feedback 0" step.
  var s2Intake = getSection2Intake_(row, creationIndex);
  var s2OdorantsWithDescriptions = BASE_ODORANT_SET.map(function (name) {
    return { name: name, description: ODORANT_DESCRIPTIONS[name] || "" };
  });
  var s2AllRounds = getFreeformCreationRoundsSoFar_(masterSs, participantName, creationIndex);
  var s2FeedbackRounds = s2AllRounds.filter(function (r) { return Number(r.round_number) > 0; });
  var s2NextRoundNumber = s2FeedbackRounds.length > 0
    ? Math.max.apply(null, s2FeedbackRounds.map(function (r) { return Number(r.round_number); })) + 1
    : 1;

  var s2LatestRound = s2FeedbackRounds.length > 0
    ? s2FeedbackRounds[s2FeedbackRounds.length - 1]
    : null;
  var s2DefaultRatios;
  if (s2LatestRound && s2LatestRound.round_ratios_json) {
    try {
      s2DefaultRatios = JSON.parse(s2LatestRound.round_ratios_json);
    } catch (e) {
      s2DefaultRatios = null;
    }
  }
  if (!s2DefaultRatios) {
    s2DefaultRatios = startingRatiosForSection2_(s2Intake.llmRatioText || "");
  }

  return {
    found: true,
    screen: "section2_feedback",
    participantName: participantName,
    creationNumber: creationIndex,
    totalCreations: SECTION2_CREATIONS_PER_PARTICIPANT,
    requestText: s2Intake.requestText || "",
    feedbackType: feedbackType,
    feedbackTypeLabel: FEEDBACK_TYPES[feedbackType],
    maxRounds: MAX_FEEDBACK_ROUNDS,
    odorants: s2OdorantsWithDescriptions,
    defaultRatios: s2DefaultRatios,
    roundsSoFar: s2FeedbackRounds.map(function (r) {
      return {
        roundNumber: Number(r.round_number),
        inputText: r.round_input_text,
        ratiosJson: r.round_ratios_json,
        resultingCompositionJson: r.resulting_composition_json,
        similarity: Number(r.match_rating_1to7)
      };
    }),
    nextRoundNumber: s2NextRoundNumber
  };
}

function submitBriefingAck(participantName) {
  return advanceStep_(participantName, STEP_BRIEFING, STEP_CARTRIDGE_CHECK);
}

/**
 * TESTING ONLY escape hatch, reachable only from the Section 1 briefing
 * screen: jumps straight to the Section 2 briefing screen, skipping all 12
 * Section 1 trials, so Section 2 (Freeform Aroma Recreation) can be tested
 * in isolation without running a full session first. Only valid from
 * STEP_BRIEFING -- does nothing useful (and isn't exposed in the UI) once
 * a session is already underway elsewhere.
 */
function skipToSection2ForTesting(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    if (step !== STEP_BRIEFING) {
      throw new Error("Skip-to-Section-2 is only available from the Section 1 briefing screen (current_step=" + step + ").");
    }
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(STEP_SECTION2_BRIEFING);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "trial_phase") + 1).setValue(TRIAL_PHASE_AFC);
    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

function submitCartridgeCheckAck(participantName) {
  return advanceStep_(participantName, STEP_CARTRIDGE_CHECK, STEP_TRIAL_START);
}

/**
 * familiarity/confidence: 1-7 integers. selectedSlot: 1-3 (which of the 3
 * presented smells the participant picked, as numbered on screen).
 * llmRatioText: free text the experimenter reads off the AromaGen frontend
 * for this trial's target reconstruction, e.g. "Vanilla · 60% Orange ·
 * 40%" -- stored as-is in `trials.llm_generated_base_odorant_ratio` and
 * later parsed (parseRatioText_, PilotData.gs) to auto-initialize the
 * rating-scale feedback screen's sliders for this same trial.
 * Appends one row to `trials` immediately, then moves this trial into its
 * feedback phase (does NOT advance current_step -- see finishTrialFeedback
 * for the actual advance to the next trial).
 */
function submitTrial(participantName, familiarity, selectedSlot, confidence, llmRatioText) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var phase = row.trial_phase || TRIAL_PHASE_AFC;
    var inTrialRange = (step >= STEP_TRIAL_START && step <= STEP_TRIAL_END);
    if (!(inTrialRange && phase === TRIAL_PHASE_AFC)) {
      throw new Error("Not at a trial (3-AFC) step (current_step=" + step + ", trial_phase=" + phase + ").");
    }

    var plan = JSON.parse(row.plan_json);
    var trialIndex = step - STEP_TRIAL_START + 1;
    var trial = plan.trials[trialIndex - 1];

    var selectedIndex = Number(selectedSlot) - 1; // 0-indexed
    var isCorrect = (selectedIndex === trial.correct_slot);

    var trialsSheet = masterSs.getSheetByName("trials");
    var opts = trial.options;
    trialsSheet.appendRow([
      participantName, plan.odorant_set, trialIndex,
      trial.target, trial.cluster,
      formatOption_(opts[0]), formatOption_(opts[1]), formatOption_(opts[2]),
      trial.correct_slot + 1, Number(familiarity), selectedIndex + 1, isCorrect,
      Number(confidence), new Date(), (llmRatioText || "").trim()
    ]);
    var trialsWrittenRow = trialsSheet.getLastRow();
    forceNumberFormat_(trialsSheet, trialsWrittenRow, headerIndex_(trialsSheet, "familiarity_1to7") + 1);
    forceNumberFormat_(trialsSheet, trialsWrittenRow, headerIndex_(trialsSheet, "confidence_1to7") + 1);

    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "trial_phase") + 1).setValue(TRIAL_PHASE_FEEDBACK);

    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

/** Step 1 of the feedback sub-flow: initial similarity between the real
 * physical reference and the ORIGINAL AromaGen target reconstruction.
 * similarity1to7: 1-7 integer. Always logged as round_number = 0 with a
 * fixed marker in round_input_text. */
function submitInitialSimilarity(participantName, similarity1to7) {
  return appendFeedbackRow_(participantName, {
    roundNumber: 0,
    inputText: "THIS IS THE INITIAL ROUND FROM SYSTEM WITHOUT ANY FEEDBACK",
    similarity: Number(similarity1to7)
  });
}

/**
 * One feedback round. roundNumber: 1..MAX_FEEDBACK_ROUNDS. inputText: free
 * text (freeform type) or "" (rating_scale type). ratiosJson: JSON string
 * of {odorantName: ratio} (rating_scale type) or "" (freeform type).
 * resultingCompositionJson: JSON string of the base odorants actually
 * selected after this round's feedback was applied. similarity1to7: 1-7
 * integer. Saved immediately, does not advance current_step.
 */
function submitFeedbackRound(participantName, roundNumber, inputText, ratiosJson, resultingCompositionJson, similarity1to7) {
  roundNumber = Number(roundNumber);
  if (roundNumber < 1 || roundNumber > MAX_FEEDBACK_ROUNDS) {
    throw new Error("roundNumber must be between 1 and " + MAX_FEEDBACK_ROUNDS + ".");
  }
  return appendFeedbackRow_(participantName, {
    roundNumber: roundNumber,
    inputText: inputText || "",
    ratiosJson: ratiosJson || "",
    resultingCompositionJson: resultingCompositionJson || "",
    similarity: Number(similarity1to7)
  });
}

/** Upsert, not append-only: if a row already exists for this exact
 * (participant, trial, round_number), it's UPDATED in place rather than
 * duplicated -- satisfies "people controlling the data collection panel
 * should be able to change the content" for any round, including
 * re-submitting the initial similarity (round 0). */
function appendFeedbackRow_(participantName, fields) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var phase = row.trial_phase || TRIAL_PHASE_AFC;
    var inTrialRange = (step >= STEP_TRIAL_START && step <= STEP_TRIAL_END);
    if (!(inTrialRange && phase === TRIAL_PHASE_FEEDBACK)) {
      throw new Error("Not at a feedback step (current_step=" + step + ", trial_phase=" + phase + ").");
    }

    var plan = JSON.parse(row.plan_json);
    var trialIndex = step - STEP_TRIAL_START + 1;
    var trial = plan.trials[trialIndex - 1];

    var feedbackSheet = masterSs.getSheetByName("feedback");
    var newRow = [
      participantName, trialIndex, trial.target, plan.odorant_set,
      plan.feedback_type, fields.roundNumber,
      fields.inputText || "", fields.ratiosJson || "",
      fields.resultingCompositionJson || "",
      fields.similarity,
      new Date()
    ];

    var data = feedbackSheet.getDataRange().getValues();
    var header = data[0];
    var nameCol = header.indexOf("participant_name");
    var trialCol = header.indexOf("trial_index");
    var roundCol = header.indexOf("round_number");
    var similarityCol = header.indexOf("similarity_rating");
    var existingRowIndex = -1;
    for (var r = 1; r < data.length; r++) {
      if (data[r][nameCol] === participantName &&
          Number(data[r][trialCol]) === trialIndex &&
          Number(data[r][roundCol]) === fields.roundNumber) {
        existingRowIndex = r + 1; // 1-indexed sheet row
        break;
      }
    }

    var writtenRow;
    if (existingRowIndex !== -1) {
      feedbackSheet.getRange(existingRowIndex, 1, 1, newRow.length).setValues([newRow]);
      writtenRow = existingRowIndex;
    } else {
      feedbackSheet.appendRow(newRow);
      writtenRow = feedbackSheet.getLastRow();
    }
    forceNumberFormat_(feedbackSheet, writtenRow, similarityCol + 1);

    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

/** Ends this trial's feedback sub-flow (regardless of how many of the
 * MAX_FEEDBACK_ROUNDS rounds were actually used) and advances to the next
 * trial, resetting trial_phase back to "afc". Once ALL Section 1 trials are
 * done this naturally lands on STEP_SECTION2_BRIEFING -- Section 1
 * finishing does NOT mark the session completed anymore, since Section 2
 * (Freeform Aroma Recreation) still follows; see finishSection2Feedback
 * for the actual session-completion point. */
function finishTrialFeedback(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var phase = row.trial_phase || TRIAL_PHASE_AFC;
    if (phase !== TRIAL_PHASE_FEEDBACK) {
      throw new Error("Not at a feedback step (current_step=" + step + ", trial_phase=" + phase + ").");
    }

    var nextStep = step + 1;
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(nextStep);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "trial_phase") + 1).setValue(TRIAL_PHASE_AFC);

    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

function submitSection2BriefingAck(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    if (step !== STEP_SECTION2_BRIEFING) {
      if (step > STEP_SECTION2_BRIEFING) return getPilotSessionView(participantName);
      throw new Error("Unexpected step: expected " + STEP_SECTION2_BRIEFING + ", found " + step);
    }
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(STEP_SECTION2_START);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "trial_phase") + 1).setValue(PHASE_INTAKE);
    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

/**
 * Section 2 intake for the CURRENT creation (creationIndex derived from
 * current_step, like a Section 1 trial's index): requestText is what the
 * participant asked AromaGen to create, in their own words (experimenter-
 * transcribed). llmRatioText is the base odorant ratio AromaGen produced
 * for it, same format as the Section 1 trial screen's ratio field (e.g.
 * "Vanilla · 60% Orange · 40%") -- used to auto-initialize the rating-scale
 * feedback screen's sliders for round 1, exactly like startingRatiosForTrial_
 * does for Section 1. Stored in the session row's section2_creations_json
 * blob, keyed by creation_index (see getSection2CreationsMap_).
 *
 * Also immediately logs round_number = 0 to the Freeform Creation sheet:
 * the initial AromaGen-generated composition itself, before any feedback,
 * together with initialRating1to7 (1 = extremely dissimilar/not a match, 7
 * = extremely similar/exact match -- same scale as every later round's
 * rating) as that row's match_rating_1to7. Combined with rounds 1..
 * MAX_FEEDBACK_ROUNDS (appendFreeformCreationRow_), this gives a complete
 * per-creation trail in that one sheet -- what AromaGen first produced and
 * how well it matched, then every round of feedback and its resulting
 * composition + rating. This rating is collected on the SAME intake
 * screen (not a separate page) -- see the file-level comment above for why
 * there's no separate "initial rating" screen here.
 */
function submitSection2Intake(participantName, requestText, llmRatioText, initialRating1to7) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var phase = row.trial_phase || "";
    var inSection2Range = (step >= STEP_SECTION2_START && step <= STEP_SECTION2_END);
    if (!(inSection2Range && phase !== TRIAL_PHASE_FEEDBACK)) {
      throw new Error("Not at a Section 2 intake step (current_step=" + step + ", trial_phase=" + phase + ").");
    }
    var rating = Number(initialRating1to7);
    if (!(rating >= 1 && rating <= 7)) {
      throw new Error("initialRating1to7 must be between 1 and 7.");
    }
    var creationIndex = step - STEP_SECTION2_START + 1;
    var cleanRequestText = (requestText || "").trim();
    var cleanLlmRatioText = (llmRatioText || "").trim();

    var creationsMap = getSection2CreationsMap_(row);
    creationsMap[String(creationIndex)] = {
      requestText: cleanRequestText,
      llmRatioText: cleanLlmRatioText
    };
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "section2_creations_json") + 1).setValue(JSON.stringify(creationsMap));
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "trial_phase") + 1).setValue(TRIAL_PHASE_FEEDBACK);

    var plan = JSON.parse(row.plan_json);
    var ratiosJson = JSON.stringify(parseRatioText_(cleanLlmRatioText, BASE_ODORANT_SET));
    var freeformSheet = masterSs.getSheetByName("Freeform Creation");
    var round0Row = [
      participantName, creationIndex, plan.feedback_type,
      cleanRequestText, cleanLlmRatioText,
      0,
      "THIS IS THE INITIAL AROMAGEN GENERATION BASED ON THE PARTICIPANT'S REQUEST, BEFORE ANY FEEDBACK",
      ratiosJson, ratiosJson,
      rating,
      new Date()
    ];
    upsertFreeformCreationRow_(freeformSheet, round0Row, participantName, creationIndex, 0);

    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

/** Section 2 equivalent of submitFeedbackRound. See that function's doc
 * comment -- identical shape, just written to the Freeform Creation sheet
 * instead of feedback, with no trial_index (only one creation/participant). */
function submitSection2FeedbackRound(participantName, roundNumber, inputText, ratiosJson, resultingCompositionJson, match1to7) {
  roundNumber = Number(roundNumber);
  if (roundNumber < 1 || roundNumber > MAX_FEEDBACK_ROUNDS) {
    throw new Error("roundNumber must be between 1 and " + MAX_FEEDBACK_ROUNDS + ".");
  }
  return appendFreeformCreationRow_(participantName, {
    roundNumber: roundNumber,
    inputText: inputText || "",
    ratiosJson: ratiosJson || "",
    resultingCompositionJson: resultingCompositionJson || "",
    match: Number(match1to7)
  });
}

/** Section 2 equivalent of appendFeedbackRow_ -- same upsert-by-key
 * behavior (here the key is participant + creation_index + round_number),
 * writing to the Freeform Creation sheet and pulling this creation's
 * request_text/llm_generated_base_odorant_ratio back from the session
 * row's creations map (set by submitSection2Intake) rather than storing
 * them again per round. */
function appendFreeformCreationRow_(participantName, fields) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var phase = row.trial_phase || "";
    var inSection2Range = (step >= STEP_SECTION2_START && step <= STEP_SECTION2_END);
    if (!(inSection2Range && phase === TRIAL_PHASE_FEEDBACK)) {
      throw new Error("Not at a Section 2 feedback step (current_step=" + step + ", trial_phase=" + phase + ").");
    }
    var creationIndex = step - STEP_SECTION2_START + 1;
    var intake = getSection2Intake_(row, creationIndex);

    var plan = JSON.parse(row.plan_json);
    var sheet = masterSs.getSheetByName("Freeform Creation");
    var newRow = [
      participantName, creationIndex, plan.feedback_type,
      intake.requestText || "", intake.llmRatioText || "",
      fields.roundNumber,
      fields.inputText || "", fields.ratiosJson || "",
      fields.resultingCompositionJson || "",
      fields.match,
      new Date()
    ];
    upsertFreeformCreationRow_(sheet, newRow, participantName, creationIndex, fields.roundNumber);

    return getPilotSessionView(participantName);
  } finally {
    lock.releaseLock();
  }
}

/** Upsert one row into the Freeform Creation sheet, keyed by (participant,
 * creation_index, round_number) -- shared by submitSection2Intake (writes
 * round 0, the initial AromaGen-generated composition) and
 * appendFreeformCreationRow_ (writes rounds 1..MAX_FEEDBACK_ROUNDS,
 * feedback). Updates the matching row in place if one already exists
 * rather than duplicating it. */
function upsertFreeformCreationRow_(sheet, newRow, participantName, creationIndex, roundNumber) {
  var data = sheet.getDataRange().getValues();
  var header = data[0];
  var nameCol = header.indexOf("participant_name");
  var creationCol = header.indexOf("creation_index");
  var roundCol = header.indexOf("round_number");
  var matchCol = header.indexOf("match_rating_1to7");
  var existingRowIndex = -1;
  for (var r = 1; r < data.length; r++) {
    if (data[r][nameCol] === participantName &&
        Number(data[r][creationCol]) === creationIndex &&
        Number(data[r][roundCol]) === roundNumber) {
      existingRowIndex = r + 1; // 1-indexed sheet row
      break;
    }
  }

  var writtenRow;
  if (existingRowIndex !== -1) {
    sheet.getRange(existingRowIndex, 1, 1, newRow.length).setValues([newRow]);
    writtenRow = existingRowIndex;
  } else {
    sheet.appendRow(newRow);
    writtenRow = sheet.getLastRow();
  }
  forceNumberFormat_(sheet, writtenRow, matchCol + 1);
}

/** Ends the CURRENT creation's feedback sub-flow (regardless of how many
 * of the MAX_FEEDBACK_ROUNDS rounds were actually used) and advances to
 * the next creation's intake, resetting trial_phase to PHASE_INTAKE --
 * mirrors finishTrialFeedback's per-trial advance in Section 1. Only once
 * the LAST creation (STEP_SECTION2_END) finishes does this mark the
 * session/participant completed -- the true end of the study. */
function finishSection2Feedback(participantName) {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, participantName);
    if (!row) throw new Error("Session not found.");
    var step = Number(row.current_step);
    var phase = row.trial_phase || "";
    var inSection2Range = (step >= STEP_SECTION2_START && step <= STEP_SECTION2_END);
    if (!(inSection2Range && phase === TRIAL_PHASE_FEEDBACK)) {
      throw new Error("Not at a Section 2 feedback step (current_step=" + step + ", trial_phase=" + phase + ").");
    }

    var nextStep = step + 1;
    var isSessionDone = (nextStep > STEP_SECTION2_END);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "current_step") + 1).setValue(nextStep);
    sessionsSheet.getRange(row._rowIndex, headerIndex_(sessionsSheet, "trial_phase") + 1).setValue(PHASE_INTAKE);

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
