/**
 * Balanced-coverage + counterbalanced-order assignment engine. Ported 1:1
 * from ../pilot_assignment.py -- that file is the validated prototype
 * (run `python3 pilot_assignment.py` there to see the balance/counterbalance
 * checks); this is the same logic in Apps Script. Keep both in sync if the
 * design changes.
 */

function mulberry32_(seed) {
  var a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    var t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle_(array, rng) {
  var a = array.slice();
  for (var i = a.length - 1; i > 0; i--) {
    var j = Math.floor(rng() * (i + 1));
    var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
  }
  return a;
}

/** Picks the single least-used descriptor in `cluster` per `tally`, ties
 * broken randomly. Mutates `tally` in place. */
function pickLeastUsedOne_(cluster, tally, rng) {
  var candidates = shuffle_(CLUSTERS[cluster], rng);
  candidates.sort(function (a, b) { return tally[a] - tally[b]; });
  var picked = candidates[0];
  tally[picked] = (tally[picked] || 0) + 1;
  return picked;
}

/** 1-indexed sequence position -> [firstSetId, secondSetId]. Odd position
 * = expert-chosen first; even position = PCA-derived first. */
function blockOrderForParticipant_(seqIndex) {
  return (seqIndex % 2 === 1) ? ["expert", "pca"] : ["pca", "expert"];
}

function buildTrial_(target, setId, rng, descToCluster) {
  var distractors = DISTRACTOR_TABLE[target];
  var near1 = distractors[NEAR_INDEX_A];
  var near2 = distractors[NEAR_INDEX_B];
  var far = distractors[REAL_FAR_INDEX];

  // Which of the 2 near-distractor words gets realized as the AromaGen
  // composition vs. the real physical object is randomized per trial (was
  // fixed near1->AromaGen, near2->real; now a coin flip each time).
  var aromagenNearWord, realNearWord;
  if (rng() < 0.5) {
    aromagenNearWord = near1; realNearWord = near2;
  } else {
    aromagenNearWord = near2; realNearWord = near1;
  }

  var unshuffled = [
    { kind: "aromagen_target", word: target },
    { kind: "aromagen_near", word: aromagenNearWord },
    { kind: "real_near", word: realNearWord },
    { kind: "real_far", word: far }
  ];
  var options = shuffle_(unshuffled, rng);
  var correctSlot = 0;
  for (var i = 0; i < options.length; i++) {
    if (options[i].kind === "aromagen_target") { correctSlot = i; break; }
  }

  return {
    target: target,
    cluster: descToCluster[target],
    odorant_set: setId,
    options: options,
    correct_slot: correctSlot
  };
}

function buildBlock_(setId, tally, rng, descToCluster) {
  var targets = [];
  for (var cluster in CLUSTERS) {
    targets.push(pickLeastUsedOne_(cluster, tally, rng));
  }
  targets = shuffle_(targets, rng);
  return targets.map(function (t) { return buildTrial_(t, setId, rng, descToCluster); });
}

/**
 * tallies: {"expert": {descriptor: count}, "pca": {descriptor: count}},
 * mutated in place. Same "pass in the running tally computed from every
 * session ever created" contract as the Preliminary Study's
 * buildAssignment().
 */
function buildParticipantPlan_(seqIndex, tallies, seed) {
  var rng = mulberry32_(seed || Date.now());
  var descToCluster = descriptorToCluster_();
  var order = blockOrderForParticipant_(seqIndex);
  var firstSet = order[0], secondSet = order[1];

  var blocks = {};
  blocks[firstSet] = buildBlock_(firstSet, tallies[firstSet], rng, descToCluster);
  blocks[secondSet] = buildBlock_(secondSet, tallies[secondSet], rng, descToCluster);

  return {
    seq_index: seqIndex,
    block_order: order,
    blocks: blocks
  };
}
