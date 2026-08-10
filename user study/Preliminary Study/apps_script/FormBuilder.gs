/**
 * Builds one Google Form per participant from their assigned trial list,
 * and wires it to write into ONE shared master spreadsheet instead of the
 * per-form spreadsheet Google Forms creates by default -- that's what
 * satisfies "I want all data stored in the same place."
 *
 * How centralization works: each generated form gets an installable
 * onFormSubmit trigger (onAromaGenFormSubmit_). That trigger doesn't read
 * the form's own auto-created response sheet at all -- it reads the
 * FormResponse directly out of the submit event, looks up what each
 * answered item MEANS via a registry (written to the master spreadsheet's
 * "form_registry" tab at generation time, keyed by itemId), and appends one
 * normalized row per trial (plus one row of demographics/closing) into the
 * master spreadsheet's "trials" / "participants" tabs. The form's own
 * default response sheet is never used for analysis.
 *
 * Known Google Forms limitations, stated rather than silently worked
 * around: Forms cannot enforce a hard 30-second wait between pages (no
 * native timer/lock) -- the physical odor delivery already paces
 * participants in practice since the experimenter administers each
 * stimulus manually before advancing; and Forms cannot prevent a
 * participant from clicking "Back" to revisit an earlier page.
 *
 * NOTE: demographics/screening questions (Age, Gender, etc.) were removed
 * from new forms per user request -- the form now goes straight from the
 * description to the familiarity check. Forms already generated before
 * this change (e.g. the first 4 participants) still have those questions
 * baked in since they were already created; onAromaGenFormSubmit_ still
 * knows how to parse them if present, purely for backward compatibility
 * with those earlier forms, not because new forms will send them.
 */

var MASTER_SS_PROP_KEY = "AROMAGEN_MASTER_SPREADSHEET_ID";

function getOrCreateMasterSpreadsheet_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty(MASTER_SS_PROP_KEY);
  if (id) {
    try {
      var existing = SpreadsheetApp.openById(id);
      migrateSchema_(existing);
      return existing;
    } catch (e) {
      // fall through and recreate if it was deleted
    }
  }
  var ss = SpreadsheetApp.create("AromaGen User Study 1 - Master Data");
  props.setProperty(MASTER_SS_PROP_KEY, ss.getId());

  var trials = ss.getSheets()[0].setName("trials");
  trials.appendRow([
    "participant_id", "trial_number", "cluster", "descriptor",
    "option_a", "option_b", "option_c", "option_d",
    "correct_index", "selected_index", "is_correct",
    "confidence_1to5", "familiarity_1to5_for_descriptor",
    "response_timestamp", "form_id", "is_duplicate_submission"
  ]);
  trials.setFrozenRows(1);

  var participants = ss.insertSheet("participants");
  participants.appendRow([
    "participant_id", "n_exposures_condition", "age", "gender_sex",
    "primary_language", "cultural_geographic_background",
    "smell_relevant_medical_conditions", "fragrance_expertise",
    "overall_experience_open_response", "submitted_at", "form_id", "form_url",
    "is_duplicate_submission"
  ]);
  participants.setFrozenRows(1);

  var registry = ss.insertSheet("form_registry");
  registry.appendRow([
    "form_id", "item_id", "role", "participant_id", "trial_number",
    "descriptor", "cluster", "option_a", "option_b", "option_c", "option_d",
    "correct_index"
  ]);
  registry.setFrozenRows(1);

  var links = ss.insertSheet("form_links");
  links.appendRow(["participant_id", "n_exposures", "form_edit_url", "form_view_url", "generated_at"]);
  links.setFrozenRows(1);

  migrateSchema_(ss);
  return ss;
}

/**
 * Adds any header columns / sheets a schema change introduced after this
 * spreadsheet was first created -- e.g. is_duplicate_submission (added
 * after the first participants' Google Forms already existed), and the
 * whole sessions/familiarity sheets + participants.session_status column
 * (added when the participant-facing UI moved from Google Forms to a
 * custom web app, so quitting mid-session no longer loses everything --
 * see SessionEngine.gs). Only ever appends missing header cells or missing
 * sheets, never touches existing columns/data/rows -- safe to call on
 * every access.
 */
function migrateSchema_(ss) {
  var trials = ss.getSheetByName("trials");
  if (trials && trials.getRange(1, trials.getLastColumn()).getValue() !== "is_duplicate_submission") {
    trials.getRange(1, trials.getLastColumn() + 1).setValue("is_duplicate_submission");
  }

  var participants = ss.getSheetByName("participants");
  if (participants) {
    var headers = participants.getRange(1, 1, 1, participants.getLastColumn()).getValues()[0];
    if (headers.indexOf("is_duplicate_submission") === -1) {
      participants.getRange(1, participants.getLastColumn() + 1).setValue("is_duplicate_submission");
    }
    headers = participants.getRange(1, 1, 1, participants.getLastColumn()).getValues()[0];
    if (headers.indexOf("session_status") === -1) {
      participants.getRange(1, participants.getLastColumn() + 1).setValue("session_status");
    }
  }

  if (!ss.getSheetByName("sessions")) {
    var sessions = ss.insertSheet("sessions");
    sessions.appendRow([
      "participant_id", "n_exposures", "plan_json", "status", "current_step",
      "session_url", "created_at", "completed_at"
    ]);
    sessions.setFrozenRows(1);
  }

  if (!ss.getSheetByName("familiarity")) {
    var familiarity = ss.insertSheet("familiarity");
    familiarity.appendRow(["participant_id", "descriptor", "familiarity_1to5", "recorded_at"]);
    familiarity.setFrozenRows(1);
  }
}

function uniqueVocabulary_(trials) {
  var seen = {};
  var vocab = [];
  trials.forEach(function (t) {
    t.options.forEach(function (opt) {
      if (!seen[opt]) { seen[opt] = true; vocab.push(opt); }
    });
  });
  return vocab;
}

/**
 * How many times each descriptor has already been ASSIGNED as a target
 * across EVERY participant ever generated, from BOTH delivery paths that
 * have existed in this project:
 *   - legacy Google Forms path: form_registry's "identification" rows
 *   - current session-engine path: sessions.plan_json's trials[].descriptor
 * Counting ASSIGNMENT (not submission) matters for both: someone who never
 * finishes their form/session still "used up" their descriptor slots, so
 * the next batch must see that or coverage silently drifts. Missing either
 * source here would make balance quietly break the moment both delivery
 * modes are in use at once -- this must stay a UNION of both, not just
 * whichever path is currently active.
 */
function computeDescriptorTally_(masterSs) {
  var tally = {};
  for (var cluster in CLUSTERS) {
    CLUSTERS[cluster].forEach(function (d) { tally[d] = 0; });
  }

  var registrySheet = masterSs.getSheetByName("form_registry");
  var regData = registrySheet.getDataRange().getValues();
  var regHeader = regData[0];
  var roleCol = regHeader.indexOf("role");
  var descCol = regHeader.indexOf("descriptor");
  for (var r = 1; r < regData.length; r++) {
    if (regData[r][roleCol] === "identification") {
      var d = regData[r][descCol];
      if (tally[d] !== undefined) tally[d]++;
    }
  }

  var sessionsSheet = masterSs.getSheetByName("sessions");
  if (sessionsSheet) {
    var sessData = sessionsSheet.getDataRange().getValues();
    var sessHeader = sessData[0];
    var planCol = sessHeader.indexOf("plan_json");
    for (var s = 1; s < sessData.length; s++) {
      var planJson = sessData[s][planCol];
      if (!planJson) continue;
      var plan = JSON.parse(planJson);
      plan.trials.forEach(function (t) {
        if (tally[t.descriptor] !== undefined) tally[t.descriptor]++;
      });
    }
  }

  return tally;
}

/**
 * Creates one participant's form, registers every scoreable item in the
 * master spreadsheet's form_registry tab, and installs the centralized
 * onFormSubmit trigger. Returns {form, editUrl, viewUrl}.
 */
function createParticipantForm_(participantId, trials, nExposures, masterSs) {
  var form = FormApp.create("AromaGen Study 1 - " + participantId)
    .setIsQuiz(true)
    .setProgressBar(true)
    .setDescription(
      "Participant ID: " + participantId + "\n" +
      "You will smell a series of odors administered by the experimenter. " +
      "After each odor, choose the description that best matches what you " +
      "smelled, then rate your confidence. You must choose one option even " +
      "if unsure. You can ask the experimenter to re-present the odor if needed."
    );

  var registryRows = [];

  // --- Familiarity pre-block (straight after the description, no
  // demographics/screening section) ---
  var vocab = uniqueVocabulary_(trials);
  form.addSectionHeaderItem().setTitle("Familiarity check").setHelpText(
    "Before smelling anything, rate how familiar you are with each of the " +
    "following smell concepts, based on the word alone.");
  var grid = form.addGridItem()
    .setTitle("How familiar are you with each of these smells?")
    .setRows(vocab)
    .setColumns(["1 - Very unfamiliar", "2 - Unfamiliar", "3 - Neutral", "4 - Familiar", "5 - Very familiar"])
    .setRequired(true);
  // Grid rows aren't individually addressable items with their own IDs in
  // the submit event the way single-question items are -- the submit
  // handler parses this response by matching each row label back to vocab.
  registryRows.push([form.getId(), String(grid.getId()), "familiarity_grid",
    participantId, "", "", "", "", "", "", "", ""]);

  // --- Trial blocks ---
  // Each trial gets TWO pages: a non-answerable interstitial (recovery /
  // "get ready") page, then the response page. This means after a
  // participant answers trial k and clicks Next, they land on a page with
  // nothing to click through but the recovery notice -- the NEXT trial's
  // 4 answer choices only become visible once they click Next again from
  // there, so there's no way to see (or be biased by) the upcoming
  // options while still notionally "recovering."
  for (var i = 0; i < trials.length; i++) {
    var trial = trials[i];
    var trialNum = i + 1;

    if (i === 0) {
      form.addPageBreakItem()
        .setTitle("Get ready")
        .setHelpText("The experimenter will now present the first odor. Wait for it, then click Next to answer.");
    } else {
      form.addPageBreakItem()
        .setTitle("Recovery")
        .setHelpText("Please wait at least 30 seconds while the experimenter prepares the next odor. Click Next when you are ready to continue.");
    }

    form.addPageBreakItem().setTitle("Smell " + trialNum + " of " + trials.length);

    var mc = form.addMultipleChoiceItem()
      .setTitle("Which option best describes the odor you just smelled?")
      .setPoints(1)
      .setRequired(true);
    var choices = trial.options.map(function (opt, idx) {
      return mc.createChoice(opt, idx === trial.correctIndex);
    });
    mc.setChoices(choices);

    var conf = form.addScaleItem()
      .setTitle("How confident are you in your answer? (1 = not at all, 5 = extremely confident)")
      .setBounds(1, 5)
      .setRequired(true);

    registryRows.push([form.getId(), String(mc.getId()), "identification",
      participantId, trialNum, trial.descriptor, trial.cluster,
      trial.options[0], trial.options[1], trial.options[2], trial.options[3],
      trial.correctIndex]);
    registryRows.push([form.getId(), String(conf.getId()), "confidence",
      participantId, trialNum, trial.descriptor, trial.cluster, "", "", "", "", ""]);
  }

  // --- Closing ---
  form.addSectionHeaderItem().setTitle("Almost done");
  var closing = form.addParagraphTextItem()
    .setTitle("Overall, what is your experience with the AromaGen system and its generated smell?")
    .setRequired(true);
  registryRows.push([form.getId(), String(closing.getId()), "closing_open_response",
    participantId, "", "", "", "", "", "", "", ""]);
  registryRows.push([form.getId(), String(grid.getId()) + "_meta", "meta_n_exposures",
    participantId, nExposures, "", "", "", "", "", "", ""]);

  var registrySheet = masterSs.getSheetByName("form_registry");
  registrySheet.getRange(registrySheet.getLastRow() + 1, 1, registryRows.length, 12)
    .setValues(registryRows);

  ScriptApp.newTrigger("onAromaGenFormSubmit_")
    .forForm(form)
    .onFormSubmit()
    .create();

  return {
    form: form,
    editUrl: form.getEditUrl(),
    viewUrl: form.getPublishedUrl()
  };
}

/**
 * Installable trigger handler, fires once per participant when they submit
 * their (single, multi-page) form. Reads the whole response, joins it
 * against form_registry, and appends normalized rows to trials/participants.
 */
function onAromaGenFormSubmit_(e) {
  // Guards two real risks: (1) two submissions landing in the same
  // execution window racing on getLastRow()-based appends and silently
  // overwriting each other's rows; (2) needed for the duplicate-submission
  // check below to be race-free (two triggers for the same form firing
  // near-simultaneously must not both see "no prior submission").
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    onAromaGenFormSubmit__(e);
  } finally {
    lock.releaseLock();
  }
}

function onAromaGenFormSubmit__(e) {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var registrySheet = masterSs.getSheetByName("form_registry");
  var registryData = registrySheet.getDataRange().getValues();
  var header = registryData[0];
  var formId = e.source.getId();

  // Nothing in this project restricts a form to one submission per person
  // (no Google-account sign-in is required, deliberately, so participants
  // don't need to log into a personal account on a shared study laptop).
  // That means nothing natively stops a double-click or a participant
  // re-opening the link from creating a second full response. Rather than
  // silently doubling that participant's rows (which would corrupt every
  // "one row per participant-trial" analysis downstream), tag it loudly.
  var participantsSheetForCheck = masterSs.getSheetByName("participants");
  var lastRowForCheck = participantsSheetForCheck.getLastRow();
  var priorFormIds = lastRowForCheck < 2 ? [] :
    participantsSheetForCheck.getRange(2, 11, lastRowForCheck - 1, 1).getValues().map(function (r) { return r[0]; });
  var isDuplicateSubmission = priorFormIds.indexOf(formId) !== -1;

  var byItemId = {};
  var metaNExposures = null;
  var participantId = null;
  for (var r = 1; r < registryData.length; r++) {
    var row = registryData[r];
    if (row[0] !== formId) continue;
    var record = {};
    header.forEach(function (h, i) { record[h] = row[i]; });
    if (record.role === "meta_n_exposures") {
      metaNExposures = row[4];
      participantId = record.participant_id;
      continue;
    }
    participantId = record.participant_id;
    byItemId[record.item_id] = record;
  }

  var itemResponses = e.response.getItemResponses();
  var vocabFamiliarity = {}; // descriptor -> 1..5
  var trialData = {}; // trial_number -> {selected_index, confidence}
  // Demographics fields only exist on forms generated before that section
  // was removed -- harmless no-op matching on new forms.
  var demographics = { age: "", gender_sex: "", primary_language: "",
    cultural_geographic_background: "", medical: "", expertise: "" };
  var closingResponse = "";

  itemResponses.forEach(function (ir) {
    var itemId = String(ir.getItem().getId());
    var response = ir.getResponse();

    // Registry-driven matching (robust to future title wording edits) for
    // everything that was actually registered at generation time.
    var meta = byItemId[itemId];
    if (meta) {
      if (meta.role === "identification") {
        var selectedIndex = trial_options_index_(meta, response);
        if (!trialData[meta.trial_number]) trialData[meta.trial_number] = {};
        trialData[meta.trial_number].selectedIndex = selectedIndex;
        trialData[meta.trial_number].descriptor = meta.descriptor;
        trialData[meta.trial_number].cluster = meta.cluster;
        trialData[meta.trial_number].options = [meta.option_a, meta.option_b, meta.option_c, meta.option_d];
        trialData[meta.trial_number].correctIndex = Number(meta.correct_index);
      } else if (meta.role === "confidence") {
        if (!trialData[meta.trial_number]) trialData[meta.trial_number] = {};
        trialData[meta.trial_number].confidence = Number(response);
      } else if (meta.role === "closing_open_response") {
        closingResponse = response;
      } else if (meta.role === "familiarity_grid") {
        // response is an array of column values aligned to the grid's row
        // order (Apps Script GridItem.getResponse() -> array of strings,
        // one per row, in the same order as asGridItem().getRows()).
        var rows = ir.getItem().asGridItem().getRows();
        var values = response;
        for (var i = 0; i < rows.length; i++) {
          var scoreMatch = /^(\d)/.exec(values[i] || "");
          vocabFamiliarity[rows[i]] = scoreMatch ? Number(scoreMatch[1]) : "";
        }
      }
      return;
    }

    // Fallback: demographics questions only exist on forms generated
    // before that section was removed (the first few participants) --
    // those items have no registry entry at all, so title-matching is the
    // only way to catch them. Not fragile in the same way as before: this
    // path only ever runs for a small, known, already-frozen set of old
    // forms, not for anything newly generated going forward.
    var title = ir.getItem().getTitle();
    if (title === "Age") { demographics.age = response; return; }
    if (title === "Gender / sex") { demographics.gender_sex = response; return; }
    if (title === "Primary language") { demographics.primary_language = response; return; }
    if (title === "Cultural / geographic background") { demographics.cultural_geographic_background = response; return; }
    if (title.indexOf("prior medical conditions") !== -1) { demographics.medical = response; return; }
    if (title.indexOf("Fragrance / perfume expertise") !== -1) { demographics.expertise = response; return; }
  });

  var timestamp = new Date();
  var trialsSheet = masterSs.getSheetByName("trials");
  var outRows = [];
  Object.keys(trialData).forEach(function (trialNum) {
    var t = trialData[trialNum];
    var fam = vocabFamiliarity[t.descriptor] !== undefined ? vocabFamiliarity[t.descriptor] : "";
    outRows.push([
      participantId, Number(trialNum), t.cluster, t.descriptor,
      t.options[0], t.options[1], t.options[2], t.options[3],
      t.correctIndex, t.selectedIndex, t.selectedIndex === t.correctIndex,
      t.confidence, fam, timestamp, formId, isDuplicateSubmission
    ]);
  });
  if (outRows.length) {
    trialsSheet.getRange(trialsSheet.getLastRow() + 1, 1, outRows.length, outRows[0].length)
      .setValues(outRows);
  }

  var participantsSheet = masterSs.getSheetByName("participants");
  participantsSheet.appendRow([
    participantId, metaNExposures, demographics.age, demographics.gender_sex,
    demographics.primary_language, demographics.cultural_geographic_background,
    demographics.medical, demographics.expertise, closingResponse, timestamp,
    formId, e.source.getPublishedUrl(), isDuplicateSubmission
  ]);
}

function trial_options_index_(meta, selectedText) {
  var options = [meta.option_a, meta.option_b, meta.option_c, meta.option_d];
  return options.indexOf(selectedText);
}
