/**
 * Web app entry point. Two admin-gated pages -- both require the token,
 * unlike the Preliminary Study's open `?pid=` participant links, because
 * every page here shows correct-answer detail and no real participant ever
 * opens either page themselves (they're blindfolded; the experimenter
 * operates everything):
 *
 *   ?admin=<token>              -> AdminPanel.html (generate participants,
 *                                  review descriptor coverage)
 *   ?admin=<token>&pid=<name>   -> DataCollection.html for that participant
 *                                  (the actual trial-running flow)
 *   anything else                -> a neutral page revealing nothing
 *
 * Generated once via `node -e "console.log(require('crypto').randomBytes(24).toString('hex'))"`.
 * REDACTED for version control -- set your own token here before deploying.
 */
var ADMIN_TOKEN = "REDACTED_SET_YOUR_OWN_TOKEN_HERE";

function doGet(e) {
  var params = (e && e.parameter) || {};

  if (params.admin !== ADMIN_TOKEN) {
    return HtmlService.createHtmlOutput("<p>Not found.</p>");
  }

  if (params.pid) {
    var template = HtmlService.createTemplateFromFile("DataCollection");
    template.pid = params.pid;
    return template.evaluate()
      .setTitle("AromaGen Internal Pilot Study - Data Collection")
      .addMetaTag("viewport", "width=device-width, initial-scale=1");
  }

  return HtmlService.createHtmlOutputFromFile("AdminPanel")
    .setTitle("AromaGen Internal Pilot Study - Admin Panel")
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

function getMasterSpreadsheetUrlForClient() {
  return getOrCreatePilotMasterSpreadsheet_().getUrl();
}

/** Live per-condition, per-cluster descriptor coverage -- lets the
 * experimenter watch balance hold in real time. */
function getPilotTallyForClient() {
  var masterSs = getOrCreatePilotMasterSpreadsheet_();
  var tallies = computePilotTallies_(masterSs);
  var result = {};
  for (var setId in tallies) {
    var byCluster = [];
    for (var cluster in CLUSTERS) {
      byCluster.push({
        cluster: cluster,
        descriptors: CLUSTERS[cluster].map(function (d) {
          return { descriptor: d, count: tallies[setId][d] };
        })
      });
    }
    result[setId] = { label: ODORANT_SET_LABELS[setId], byCluster: byCluster };
  }
  return result;
}
