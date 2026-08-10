/**
 * Web app entry point -- this is "the website." One deployment, three
 * possible pages depending on the query string, since a public "Anyone
 * with the link" web app (required so participants who aren't you can
 * open their session) has no other way to tell a participant apart from
 * you:
 *   ?pid=P007        -> that participant's session (Session.html)
 *   ?admin=<token>    -> the admin control panel (ControlPanel.html)
 *   anything else      -> a neutral page revealing nothing
 * The admin token lives in SessionEngine.gs's ADMIN_TOKEN constant --
 * bookmark the URL with it, never share that URL with a participant.
 */
function doGet(e) {
  var params = (e && e.parameter) || {};

  if (params.pid) {
    var masterSs = getOrCreateMasterSpreadsheet_();
    var sessionsSheet = masterSs.getSheetByName("sessions");
    var row = getSessionRow_(sessionsSheet, params.pid);
    if (!row) {
      return HtmlService.createHtmlOutput("<p>No session found for this link. Contact the study administrator.</p>");
    }
    var template = HtmlService.createTemplateFromFile("Session");
    template.pid = params.pid;
    return template.evaluate()
      .setTitle("AromaGen Study")
      .addMetaTag("viewport", "width=device-width, initial-scale=1");
  }

  if (params.admin === ADMIN_TOKEN) {
    return HtmlService.createHtmlOutputFromFile("ControlPanel")
      .setTitle("AromaGen Study 1 - Control Panel")
      .addMetaTag("viewport", "width=device-width, initial-scale=1");
  }

  return HtmlService.createHtmlOutput("<p>Not found.</p>");
}

/** Called from ControlPanel.html. participantIdsText: newline/comma
 * separated raw text from the textarea. */
function generateFormsForParticipants(participantIdsText, nExposures, seed) {
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

  // Lock around the whole read-tally / decide-who's-new / write-registry
  // sequence: without this, two people clicking Generate in overlapping
  // browser tabs (or you double-clicking) could both read the same tally
  // and same existingIds snapshot before either writes back, silently
  // colliding (duplicate forms, double-counted tally, or two forms
  // claiming the same descriptor slot). Single-experimenter sequential use
  // wouldn't hit this, but there's no reason to leave it unguarded.
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    // Skip IDs that already have a form -- protects against accidentally
    // re-pasting a full P1...P30 list after an earlier batch (e.g. P1-P4)
    // already ran: those would otherwise get a second, duplicate form and
    // silently double-count toward the descriptor tally.
    var linksSheet = masterSs.getSheetByName("form_links");
    var existingIds = {};
    var linksData = linksSheet.getDataRange().getValues();
    for (var i = 1; i < linksData.length; i++) { existingIds[linksData[i][0]] = true; }
    var newIds = uniqueIds.filter(function (id) { return !existingIds[id]; });
    var skippedIds = uniqueIds.filter(function (id) { return existingIds[id]; });

    if (newIds.length === 0) {
      return { forms: [], skipped: skippedIds, masterSpreadsheetUrl: masterSs.getUrl() };
    }

    // Tally is recomputed from the full history every call (see
    // computeDescriptorTally_) -- this is what makes generating a batch now
    // and another batch weeks from now still land on globally balanced
    // coverage, not just balanced within whichever IDs are in this one call.
    var tally = computeDescriptorTally_(masterSs);
    var assignment = buildAssignment(newIds, Number(nExposures), tally, seed ? Number(seed) : undefined);

    var results = [];
    var generatedAt = new Date();
    newIds.forEach(function (pid) {
      var trials = assignment[pid];
      var created = createParticipantForm_(pid, trials, Number(nExposures), masterSs);
      linksSheet.appendRow([pid, Number(nExposures), created.editUrl, created.viewUrl, generatedAt]);
      results.push({ participantId: pid, editUrl: created.editUrl, viewUrl: created.viewUrl });
    });

    return {
      forms: results,
      skipped: skippedIds,
      masterSpreadsheetUrl: masterSs.getUrl()
    };
  } finally {
    lock.releaseLock();
  }
}

function getSampleSizeReportForClient(evalsPerDescriptor) {
  return sampleSizeReport(evalsPerDescriptor ? Number(evalsPerDescriptor) : 30, 0.15);
}

function getRealisticCoverageForClient(nParticipants, nExposures) {
  return realisticCoverage(Number(nParticipants), Number(nExposures));
}

function getMasterSpreadsheetUrlForClient() {
  return getOrCreateMasterSpreadsheet_().getUrl();
}

/** Live per-descriptor coverage, grouped by cluster, for the control
 * panel's monitoring table -- lets you watch balance hold in real time
 * instead of trusting it blind. */
function getDescriptorTallyForClient() {
  var masterSs = getOrCreateMasterSpreadsheet_();
  var tally = computeDescriptorTally_(masterSs);
  var byCluster = [];
  for (var cluster in CLUSTERS) {
    byCluster.push({
      cluster: cluster,
      descriptors: CLUSTERS[cluster].map(function (d) { return { descriptor: d, count: tally[d] }; })
    });
  }
  return byCluster;
}

/** Ground-truth trial order for one or more participants -- what the
 * experimenter needs to know what to physically dispense at each trial.
 * Never shown to participants themselves (Session.html/getSessionState
 * deliberately withhold it). Read-only, doesn't touch any data. */
function getGroundTruthForClient(participantIdsText) {
  var pids = participantIdsText
    .split(/[\n,]/)
    .map(function (s) { return s.trim(); })
    .filter(function (s) { return s.length > 0; });
  return getGroundTruthForParticipants_(pids);
}
