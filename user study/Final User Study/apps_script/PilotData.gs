/**
 * Study vocabulary + odorant config for the Final User Study.
 * Ported 1:1 from ../pilot_config.py -- keep in sync if either changes.
 *
 * Single fixed 12-odorant set (no longer an A/B condition) used for every
 * participant. Each participant does ONE pass of 12 trials (one target
 * per cluster), plus a post-trial feedback sub-flow (freeform vs.
 * rating-scale, counterbalanced across participants) -- see PilotEngine.gs.
 *
 * Descriptor taxonomy: 12 clusters, 50 words -- its own list, separate
 * from both the Preliminary Study's and the Internal Pilot Study's
 * taxonomies (words differ even where cluster names repeat).
 */

var CLUSTERS = {
  "Floral": ["Lavender", "cherry blossom", "jasmine tea", "rose hand cream"],
  "Citrus": ["Orange", "mango", "Lemonade", "Lime soda (Sprite)"],
  "Woody & Resinous": ["Pine", "oak", "Wooden wine barrel", "Incense"],
  "Herbal & Cooling": ["Basil", "Cucumber", "Peppermint tea", "Mint chewing gum"],
  "Spice": ["Ginger", "Black pepper", "Chai latte", "Cinnamon roll"],
  "Sweet & Gourmand": ["Coke", "dark chocolate", "Apple pie", "Sweet popcorn", "Vanilla ice cream"],
  "Roasted & Smoky": ["Coffee", "Bacon", "barbeque ribs", "Hot dog with hot sauce"],
  "Fermented & Sour": ["Greek yogurt", "Pickled cucumber", "Fries with ranch sauce", "Nacho with sour cream"],
  "Putrid & Decay": ["Blue cheese", "durian", "Canned sardines", "Sticky tofu with chilli"],
  "Chemical & Solvent": ["Whiskey", "Tequila", "Mint Fluoride mouthwash", "Lavender nail polish remover"],
  "Perfumed & Clean": ["Aloe vera", "Hand sanitizer", "Mint fluoride toothpaste", "Almond oil shampoo"],
  "Savoury & Umami": ["Soy sauce", "Parmesan cheese", "Garlic", "Seasoned pull pork in bbq sauce", "Salty popcorn"]
};

var TRIALS_PER_PARTICIPANT = 12; // = Object.keys(CLUSTERS).length -- one target per cluster, one pass

// --- Distractor design: dynamic, balanced, randomized -- see
// pilot_config.py's comment for the full rationale. Near distractors: one
// word from each of the target's 2 ring-neighbor clusters, picked as the
// least-used-so-far candidate (random tie-break). Far distractor: least-
// used-so-far word from the OTHER family. All balanced against a running
// distractor-usage tally built at plan-generation time -- NOT a fixed
// per-target lookup table.
var FAMILY_A_RING = ["Floral", "Sweet & Gourmand", "Spice", "Woody & Resinous", "Herbal & Cooling", "Citrus"];
var FAMILY_B_RING = ["Chemical & Solvent", "Perfumed & Clean", "Roasted & Smoky", "Savoury & Umami", "Fermented & Sour", "Putrid & Decay"];

function ringNeighbors_(ring, cluster) {
  var i = ring.indexOf(cluster), n = ring.length;
  return [ring[(i - 1 + n) % n], ring[(i + 1) % n]];
}

var NEIGHBOR_CLUSTERS = {};
FAMILY_A_RING.forEach(function (c) { NEIGHBOR_CLUSTERS[c] = ringNeighbors_(FAMILY_A_RING, c); });
FAMILY_B_RING.forEach(function (c) { NEIGHBOR_CLUSTERS[c] = ringNeighbors_(FAMILY_B_RING, c); });

var FAMILY_OF_CLUSTER = {};
FAMILY_A_RING.forEach(function (c) { FAMILY_OF_CLUSTER[c] = "A"; });
FAMILY_B_RING.forEach(function (c) { FAMILY_OF_CLUSTER[c] = "B"; });

// --- The single fixed odorant set (no longer an A/B condition) ---
// Matches the current live AromaGen catalog (aromagen/cartridge_sets.json)
// exactly, including Seaweed Accord as the stand-in for the umami/savoury
// class.
var ODORANT_SET_ID = "fixed_set";
var BASE_ODORANT_SET = [
  "Benz Sal", "Sandalwood", "Clove Bud", "Lavender", "Orange", "Vanilla",
  "Birch tar oil", "Eucalyptus", "Cognac", "Vinegar", "Isovaleric acid",
  "Seaweed Accord"
];

var ODORANT_CATEGORY = {
  "Benz Sal": "Perfumed / Clean",
  "Sandalwood": "Woody / Resinous",
  "Clove Bud": "Spice",
  "Lavender": "Floral",
  "Orange": "Citrus",
  "Vanilla": "Sweet / Gourmand",
  "Birch tar oil": "Roasted / Smoky",
  "Eucalyptus": "Herbal / Cooling",
  "Cognac": "Chemical / Solvent",
  "Vinegar": "Fermented / Sour",
  "Isovaleric acid": "Animal / Body",
  "Seaweed Accord": "Umami / Savoury (stand-in)"
};

var ODORANT_VOLATILITY = {
  "Benz Sal": 4, "Sandalwood": 4, "Clove Bud": 6, "Lavender": 6,
  "Orange": 8, "Vanilla": 3, "Birch tar oil": 3, "Eucalyptus": 8,
  "Cognac": 8, "Vinegar": 8, "Isovaleric acid": 7, "Seaweed Accord": 5
};

// Brief sensory description per odorant, shown next to each name on the
// rating-scale feedback screen. Sourced from aromagen/cartridge_sets.json.
var ODORANT_DESCRIPTIONS = {
  "Benz Sal": "Sweet, balsamic, soft floral, powdery clean note",
  "Sandalwood": "Woody, creamy, soft, warm, slightly sweet base note",
  "Clove Bud": "Warm, pungent, spicy",
  "Lavender": "Floral, herbaceous-sweet, calming",
  "Orange": "Bright, citrus, sweet, juicy top note",
  "Vanilla": "Sweet, creamy, warm, gourmand",
  "Birch tar oil": "Smoky, tarry, leathery, medicinal-burnt",
  "Eucalyptus": "Cool, medicinal, camphoraceous, fresh herbal top note",
  "Cognac": "Sharp, alcoholic, boozy, solvent-like pungency",
  "Vinegar": "Sour, sharp, acetic, pungent",
  "Isovaleric acid": "Sweaty, cheesy, animalic",
  "Seaweed Accord": "Marine, salty, umami, savoury"
};

// --- Feedback-type condition ---
// Counterbalanced via participant-sequence parity: odd -> freeform, even
// -> rating_scale.
var FEEDBACK_TYPES = {
  "freeform": "Freeform feedback",
  "rating_scale": "Rating-scale feedback"
};
var MAX_FEEDBACK_ROUNDS = 5;

// --- Section 2: Freeform Aroma Recreation ---
// Each participant does this many separate freeform creations (each with
// its own intake + feedback sub-flow), not just one.
var SECTION2_CREATIONS_PER_PARTICIPANT = 5;

function feedbackTypeForParticipant_(seqIndex) {
  return (seqIndex % 2 === 1) ? "freeform" : "rating_scale";
}

function descriptorToCluster_() {
  var map = {};
  for (var cluster in CLUSTERS) {
    CLUSTERS[cluster].forEach(function (d) { map[d] = cluster; });
  }
  return map;
}

// --- Spreadsheet plumbing ---

var MASTER_SS_PROP_KEY = "AROMAGEN_FINAL_STUDY_MASTER_SPREADSHEET_ID";

function getOrCreatePilotMasterSpreadsheet_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty(MASTER_SS_PROP_KEY);
  var ss;
  if (id) {
    try {
      ss = SpreadsheetApp.openById(id);
    } catch (e) {
      ss = null; // fall through and recreate if it was deleted
    }
  }
  if (!ss) {
    ss = SpreadsheetApp.create("AromaGen Final User Study - Master Data");
    props.setProperty(MASTER_SS_PROP_KEY, ss.getId());
  }

  ensureSheetHeaders_(ss);
  return ss;
}

// Sheet name -> header row. Single source of truth for schema, used both
// to create sheets from scratch AND to repair a sheet whose header row
// got cleared/deleted by hand -- ensureSheetHeaders_ runs on EVERY call,
// not just at spreadsheet-creation time, so this self-heals rather than
// silently leaving row 1 blank forever.
var SHEET_SCHEMAS_ = {
  participants: ["participant_name", "seq_index", "odorant_set", "feedback_type",
    "status", "created_at", "completed_at"],
  sessions: ["participant_name", "plan_json", "status", "current_step", "trial_phase",
    "created_at", "completed_at", "section2_creations_json"],
  trials: ["participant_name", "odorant_set", "trial_index", "target", "cluster",
    "option_1", "option_2", "option_3", "option_4",
    "correct_slot", "familiarity_1to7", "selected_slot", "is_correct",
    "confidence_1to7", "response_timestamp", "llm_generated_base_odorant_ratio"],
  feedback: ["participant_name", "trial_index", "target", "odorant_set",
    "feedback_type", "round_number", "round_input_text", "round_ratios_json",
    "resulting_composition_json", "similarity_rating", "response_timestamp"],
  // Section 2, "Freeform Aroma Recreation" -- SECTION2_CREATIONS_PER_PARTICIPANT
  // separate creations per participant, each identified by creation_index
  // (1..SECTION2_CREATIONS_PER_PARTICIPANT), same round-based feedback shape
  // as `feedback` above but with its own request_text/ratio columns and a
  // match_rating_1to7 column instead of similarity_rating (there's no real
  // physical reference to compare against in Section 2, just "how well does
  // this match what was asked for"). See PilotEngine.gs's file-level comment
  // for the full state machine.
  "Freeform Creation": ["participant_name", "creation_index", "feedback_type",
    "request_text", "llm_generated_base_odorant_ratio", "round_number",
    "round_input_text", "round_ratios_json", "resulting_composition_json",
    "match_rating_1to7", "response_timestamp"]
};
var SHEET_ORDER_ = ["participants", "sessions", "trials", "feedback", "Freeform Creation"];

/**
 * Creates any missing sheet and rewrites its header row (positions 1..N,
 * N = SHEET_SCHEMAS_[name].length) whenever those cells don't EXACTLY
 * match the current schema -- covers first-time creation, someone
 * manually clearing the header row, and a schema that grew (a new
 * trailing column added). Idempotent: a no-op once row 1 already matches.
 *
 * NOTE on a real bug this replaced: an earlier version compared against
 * `sheet.getLastColumn()`, which reflects the sheet's widest-EVER-used
 * column, not row 1's actual current width -- it's sticky across schema
 * changes (Google Sheets doesn't shrink it just because a later header
 * rewrite only touched the first N cells, leaving stale "ghost" labels
 * from an older, wider schema sitting past column N). That made the old
 * migration compare the current schema's prefix against those ghost
 * cells, decide nothing needed fixing, and permanently skip adding
 * genuinely new columns (e.g. `llm_generated_base_odorant_ratio` never
 * got added to `trials` on a spreadsheet that pre-dated it). Comparing
 * directly against `header` (not the sheet's historical max width) and
 * always rewriting on ANY mismatch avoids that trap entirely, at the cost
 * of allowing legitimate hand-added extra columns to occasionally get
 * clobbered -- worth it here since no real participant data existed when
 * this was written.
 */
function ensureSheetHeaders_(ss) {
  SHEET_ORDER_.forEach(function (name, idx) {
    var sheet = ss.getSheetByName(name);
    if (!sheet) {
      sheet = (idx === 0 && ss.getSheets().length === 1 && ss.getSheets()[0].getName() === "Sheet1")
        ? ss.getSheets()[0].setName(name)
        : ss.insertSheet(name);
    }
    var header = SHEET_SCHEMAS_[name];
    var currentWidth = Math.max(sheet.getLastColumn(), header.length);
    var currentHeader = currentWidth > 0 ? sheet.getRange(1, 1, 1, currentWidth).getValues()[0] : [];
    var matches = header.every(function (h, i) { return currentHeader[i] === h; });
    if (!matches) {
      sheet.getRange(1, 1, 1, header.length).setValues([header]);
      sheet.setFrozenRows(1);
      if (currentWidth > header.length) {
        sheet.getRange(1, header.length + 1, 1, currentWidth - header.length).clearContent();
      }
    }
  });
}

/**
 * Parses free text like "Vanilla · 60% Orange · 40%" into
 * {odorantName: 0-1 ratio} by searching for each name in `names` next to a
 * percentage, in EITHER order ("Vanilla 60%" or "60% Vanilla") and with a
 * loose separator (·, :, -, (), or just whitespace) -- experimenters don't
 * always type the exact documented format, so this tries name-then-number
 * first and falls back to number-then-name. Names not mentioned are
 * omitted (caller decides the default, typically 0). A '%' sign is
 * required on the number (a bare "0.5" is ambiguous -- could mean 0.5% or
 * a 0-1 fraction -- so it's intentionally left unparsed rather than
 * guessed; the live "Parsed as:" preview next to each ratio input,
 * DataCollection.html, mirrors this exact logic so the experimenter sees
 * immediately if something didn't parse).
 *
 * Mirrors the client-side preview parser (parseRatioTextClient_ in
 * DataCollection.html) -- keep both in sync if this changes.
 */
function parseRatioText_(text, names) {
  var ratios = {};
  if (!text) return ratios;
  names.forEach(function (name) {
    var escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    var numberPattern = "(\\d+(?:\\.\\d+)?)\\s*%";
    var afterRe = new RegExp(escaped + "\\s*[\\u00b7:()-]?\\s*" + numberPattern, "i");
    var beforeRe = new RegExp(numberPattern + "\\s*[\\u00b7:()-]?\\s*" + escaped, "i");
    var m = text.match(afterRe) || text.match(beforeRe);
    if (m) {
      var v = Math.max(0, Math.min(1, Number(m[1]) / 100));
      ratios[name] = Math.round(v * 100) / 100;
    }
  });
  return ratios;
}

/**
 * Descriptor tallies computed fresh from every session's frozen plan_json
 * (assigned, not just completed). Returns
 * {targets: {descriptor: count}, distractors: {descriptor: count}}.
 */
function computePilotTallies_(masterSs) {
  var targetTally = {}, distractorTally = {};
  for (var cluster in CLUSTERS) {
    CLUSTERS[cluster].forEach(function (d) { targetTally[d] = 0; distractorTally[d] = 0; });
  }

  var sessionsSheet = masterSs.getSheetByName("sessions");
  var data = sessionsSheet.getDataRange().getValues();
  var header = data[0];
  var planCol = header.indexOf("plan_json");
  for (var r = 1; r < data.length; r++) {
    var planJson = data[r][planCol];
    if (!planJson) continue;
    var plan = JSON.parse(planJson);
    plan.trials.forEach(function (t) {
      if (targetTally[t.target] !== undefined) targetTally[t.target]++;
      t.options.forEach(function (o) {
        if (o.kind !== "aromagen_target" && distractorTally[o.word] !== undefined) {
          distractorTally[o.word]++;
        }
      });
    });
  }
  return { targets: targetTally, distractors: distractorTally };
}

/** Next 1-indexed sequence position = count of sessions ever created + 1.
 * Used for feedback-type counterbalancing (odd -> freeform, even ->
 * rating_scale) -- independent of whatever name string the experimenter
 * types. */
function nextSeqIndex_(masterSs) {
  var sessionsSheet = masterSs.getSheetByName("sessions");
  return sessionsSheet.getLastRow(); // header row = row 1, so lastRow - 1 + 1 = lastRow
}
