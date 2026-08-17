// Standalone logging endpoint for the real AromaGen product's "Log" button.
// Separate from the Final User Study's spreadsheet/tooling on purpose -- this
// captures live product usage, not study trial data. The target spreadsheet
// is created lazily on first request and its ID persisted in Script
// Properties, so no spreadsheet has to be pre-created/shared by hand.

var TOKEN = "REDACTED_SET_YOUR_OWN_TOKEN_HERE";
var SHEET_NAME = "Interaction Log";
var HEADERS = ["Timestamp", "Target smell", "AromaGen Ratio", "Similarity (1-7)", "Feedback", "Session ID"];

function getOrCreateSpreadsheet_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty("SPREADSHEET_ID");
  var ss = null;
  if (id) {
    try {
      ss = SpreadsheetApp.openById(id);
    } catch (e) {
      ss = null;
    }
  }
  if (!ss) {
    ss = SpreadsheetApp.create("AromaGen Production Interaction Log");
    props.setProperty("SPREADSHEET_ID", ss.getId());
  }
  return ss;
}

function getOrCreateSheet_(ss) {
  var sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = ss.getSheets()[0];
    sheet.setName(SHEET_NAME);
  }
  var firstRow = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  var hasHeaders = HEADERS.every(function (h, i) { return firstRow[i] === h; });
  if (!hasHeaders) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function jsonOutput_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// GET ?token=... -- health check / returns the spreadsheet URL, without writing a data row.
function doGet(e) {
  var token = e.parameter.token;
  if (token !== TOKEN) {
    return jsonOutput_({ error: "unauthorized" });
  }
  var ss = getOrCreateSpreadsheet_();
  var sheet = getOrCreateSheet_(ss);

  return jsonOutput_({
    status: "ok",
    spreadsheet_url: ss.getUrl(),
    spreadsheet_id: ss.getId(),
  });
}

// POST { token, target_smell, aromagen_ratio, similarity, feedback, session_id }
function doPost(e) {
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonOutput_({ error: "invalid JSON body" });
  }
  if (body.token !== TOKEN) {
    return jsonOutput_({ error: "unauthorized" });
  }

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var ss = getOrCreateSpreadsheet_();
    var sheet = getOrCreateSheet_(ss);
    var row = sheet.getLastRow() + 1;
    sheet.appendRow([
      new Date(),
      body.target_smell || "",
      body.aromagen_ratio || "",
      body.similarity != null ? body.similarity : "",
      body.feedback || "",
      body.session_id || "",
    ]);
    // appendRow can inherit date-category formatting from the row above for
    // any column, which silently corrupts numeric-looking values (seen
    // before with rating columns in the Final User Study sheets) -- force
    // the similarity column back to a plain number format after every write.
    sheet.getRange(row, 4).setNumberFormat("0");
  } finally {
    lock.releaseLock();
  }
  return jsonOutput_({ status: "ok" });
}
