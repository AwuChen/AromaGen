/**
 * Study vocabulary + odorant-set config for the Internal Pilot Study.
 * Ported 1:1 from ../pilot_config.py -- keep in sync if either changes.
 *
 * This study A/B tests two 12-odorant sets ("expert-chosen" vs.
 * "PCA-derived") against each other for overall accuracy, cluster-level
 * accuracy, and qualitative feedback.
 *
 * Descriptor taxonomy: 11 clusters, 46 words -- a SEPARATE list from the
 * Preliminary Study's 50-word/12-cluster taxonomy, scoped to this internal
 * pilot only. Drops "Body & Animalic" relative to the Preliminary Study's
 * 12 clusters. TRIALS_PER_BLOCK = 11 -- one target per cluster, two blocks
 * per participant = 22 total trials/participant.
 */

var CLUSTERS = {
  "Floral": ["honeysuckle", "gardenia", "lily", "magnolia"],
  "Citrus": ["Orange", "mango", "Bergamot", "Lime"],
  "Woody & Resinous": ["Balsam", "Incense", "Patchouli", "amber"],
  "Herbal & Cooling": ["Camphor", "cucumber", "sage", "basil"],
  "Spice": ["ginger", "mustard", "pepper", "Chilli"],
  "Sweet & Gourmand": ["Sweet popcorn", "Almond", "Strawberry", "Chocolate", "Peanut butter"],
  "Roasted & Smoky": ["Coffee", "cigarette", "Barbeque", "bacon"],
  "Fermented & Sour": ["Beewax", "Cheese", "Whiskey", "Pickle", "cider"],
  "Putrid & Decay": ["Guano", "Sulfur fertilizer", "Dead fish", "mud"],
  "Chemical & Solvent": ["acetate", "diesel", "gasoline", "alcohol"],
  "Perfumed & Clean": ["makeup", "sunscreen", "candle", "toothpaste"]
};

var TRIALS_PER_BLOCK = 11; // = Object.keys(CLUSTERS).length -- one target per cluster

// Distractor design mirrors the Preliminary Study's methodology (2 near-
// neighbor clusters per cluster within a family, 1 far distractor from the
// other family) -- see pilot_config.py's comment above this same table for
// the family/ring definitions, generation rule, and balance check.
var DISTRACTOR_TABLE = {
  "honeysuckle": ["Orange", "Sweet popcorn", "Coffee"],
  "gardenia": ["mango", "Almond", "cigarette"],
  "lily": ["Bergamot", "Strawberry", "Barbeque"],
  "magnolia": ["Lime", "Chocolate", "bacon"],
  "Sweet popcorn": ["honeysuckle", "ginger", "Beewax"],
  "Almond": ["gardenia", "mustard", "Cheese"],
  "Strawberry": ["lily", "pepper", "Whiskey"],
  "Chocolate": ["magnolia", "Chilli", "Pickle"],
  "Peanut butter": ["honeysuckle", "ginger", "cider"],
  "ginger": ["Peanut butter", "Balsam", "Guano"],
  "mustard": ["Sweet popcorn", "Incense", "Sulfur fertilizer"],
  "pepper": ["Almond", "Patchouli", "Dead fish"],
  "Chilli": ["Strawberry", "amber", "mud"],
  "Balsam": ["mustard", "Camphor", "acetate"],
  "Incense": ["pepper", "cucumber", "diesel"],
  "Patchouli": ["Chilli", "sage", "gasoline"],
  "amber": ["ginger", "basil", "alcohol"],
  "Camphor": ["Balsam", "Orange", "makeup"],
  "cucumber": ["Incense", "mango", "sunscreen"],
  "sage": ["Patchouli", "Bergamot", "candle"],
  "basil": ["amber", "Lime", "toothpaste"],
  "Orange": ["Camphor", "gardenia", "Coffee"],
  "mango": ["cucumber", "lily", "cigarette"],
  "Bergamot": ["sage", "magnolia", "Barbeque"],
  "Lime": ["basil", "honeysuckle", "bacon"],
  "makeup": ["acetate", "Coffee", "honeysuckle"],
  "sunscreen": ["diesel", "cigarette", "gardenia"],
  "candle": ["gasoline", "Barbeque", "lily"],
  "toothpaste": ["alcohol", "bacon", "magnolia"],
  "Coffee": ["makeup", "Beewax", "Orange"],
  "cigarette": ["sunscreen", "Cheese", "mango"],
  "Barbeque": ["candle", "Whiskey", "Bergamot"],
  "bacon": ["toothpaste", "Pickle", "Lime"],
  "Beewax": ["Coffee", "Guano", "Balsam"],
  "Cheese": ["cigarette", "Sulfur fertilizer", "Incense"],
  "Whiskey": ["Barbeque", "Dead fish", "Patchouli"],
  "Pickle": ["bacon", "mud", "amber"],
  "cider": ["Coffee", "Guano", "Camphor"],
  "Guano": ["cider", "acetate", "cucumber"],
  "Sulfur fertilizer": ["Beewax", "diesel", "sage"],
  "Dead fish": ["Cheese", "gasoline", "basil"],
  "mud": ["Whiskey", "alcohol", "ginger"],
  "acetate": ["Sulfur fertilizer", "makeup", "mustard"],
  "diesel": ["Dead fish", "sunscreen", "pepper"],
  "gasoline": ["mud", "candle", "Chilli"],
  "alcohol": ["Guano", "toothpaste", "Sweet popcorn"]
};

// [near_a, near_b, far] -> far (position 2) is always realized as a real
// physical object. Which of the 2 near distractors (positions 0/1) becomes
// the AromaGen composition vs. the real physical object is randomized per
// trial (coin flip in buildTrial_ in PilotAssignment.gs), not fixed by
// position.
var NEAR_INDEX_A = 0;
var NEAR_INDEX_B = 1;
var REAL_FAR_INDEX = 2;

// --- The two odorant sets under test ---
// PCA-DERIVED = the set currently live in aromagen/cartridge_sets.json.
// Re-synced 2026-08 after a 12th odorant (Seaweed Accord) was added.
// Re-sync again if the live catalog changes further.
var PCA_DERIVED_SET = [
  "Benz Sal", "Sandalwood", "Clove Bud", "Lavender", "Orange", "Vanilla",
  "Birch tar oil", "Eucalyptus", "Cognac", "Vinegar", "Isovaleric acid",
  "Seaweed Accord"
];

// EXPERT-CHOSEN = PLACEHOLDER NAMES pending the real 12 expert-chosen
// odorants -- replace before running any real session. See pilot_config.py.
var EXPERT_CHOSEN_SET = ["A", "B", "C", "D", "E", "f", "g", "h", "i", "j", "k", "l"];

var ODORANT_SETS = {
  "expert": EXPERT_CHOSEN_SET,
  "pca": PCA_DERIVED_SET
};

var ODORANT_SET_LABELS = {
  "expert": "Expert-chosen set",
  "pca": "PCA-derived set (current live AromaGen catalog)"
};

function descriptorToCluster_() {
  var map = {};
  for (var cluster in CLUSTERS) {
    CLUSTERS[cluster].forEach(function (d) { map[d] = cluster; });
  }
  return map;
}

// --- Spreadsheet plumbing (same "one shared master spreadsheet, ID cached
// in Script Properties" pattern as the Preliminary Study's FormBuilder.gs)
// ---

var MASTER_SS_PROP_KEY = "AROMAGEN_PILOT_MASTER_SPREADSHEET_ID";

function getOrCreatePilotMasterSpreadsheet_() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty(MASTER_SS_PROP_KEY);
  if (id) {
    try {
      return SpreadsheetApp.openById(id);
    } catch (e) {
      // fall through and recreate if it was deleted
    }
  }
  var ss = SpreadsheetApp.create("AromaGen Internal Pilot Study - Master Data");
  props.setProperty(MASTER_SS_PROP_KEY, ss.getId());

  var participants = ss.getSheets()[0].setName("participants");
  participants.appendRow([
    "participant_name", "seq_index", "block_order", "status",
    "created_at", "completed_at"
  ]);
  participants.setFrozenRows(1);

  var sessions = ss.insertSheet("sessions");
  sessions.appendRow([
    "participant_name", "plan_json", "status", "current_step",
    "created_at", "completed_at"
  ]);
  sessions.setFrozenRows(1);

  var trials = ss.insertSheet("trials");
  trials.appendRow([
    "participant_name", "block_index", "odorant_set", "trial_index_in_block",
    "target", "cluster",
    "option_1_kind", "option_1_word", "option_2_kind", "option_2_word",
    "option_3_kind", "option_3_word", "option_4_kind", "option_4_word",
    "correct_slot", "familiarity_1to7", "selected_slot", "is_correct",
    "confidence_1to7", "response_timestamp"
  ]);
  trials.setFrozenRows(1);

  return ss;
}

/**
 * Per-odorant-set descriptor tally, computed fresh from every session's
 * frozen plan_json (assigned, not just completed, same rationale as the
 * Preliminary Study: someone who never finishes a block still "used up"
 * that descriptor slot for balance purposes). Returns
 * {"expert": {descriptor: count}, "pca": {descriptor: count}}.
 */
function computePilotTallies_(masterSs) {
  var tallies = { expert: {}, pca: {} };
  for (var setId in ODORANT_SETS) {
    for (var cluster in CLUSTERS) {
      CLUSTERS[cluster].forEach(function (d) { tallies[setId][d] = 0; });
    }
  }

  var sessionsSheet = masterSs.getSheetByName("sessions");
  var data = sessionsSheet.getDataRange().getValues();
  var header = data[0];
  var planCol = header.indexOf("plan_json");
  for (var r = 1; r < data.length; r++) {
    var planJson = data[r][planCol];
    if (!planJson) continue;
    var plan = JSON.parse(planJson);
    for (var setId in plan.blocks) {
      plan.blocks[setId].forEach(function (t) {
        if (tallies[setId][t.target] !== undefined) tallies[setId][t.target]++;
      });
    }
  }
  return tallies;
}

/** Next 1-indexed sequence position = count of sessions ever created + 1.
 * Used for block-order counterbalancing (odd -> expert first, even -> pca
 * first) -- independent of whatever name string the experimenter types. */
function nextSeqIndex_(masterSs) {
  var sessionsSheet = masterSs.getSheetByName("sessions");
  return sessionsSheet.getLastRow(); // header row = row 1, so lastRow - 1 + 1 = lastRow
}
