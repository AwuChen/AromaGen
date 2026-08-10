/**
 * Balanced-coverage assignment engine. Ported 1:1 from
 * ../pilot_assignment.py -- that file is the validated prototype (run
 * `python3 pilot_assignment.py` there to see the coverage/counterbalance
 * checks); this is the same logic in Apps Script. Keep both in sync.
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
  candidates.sort(function (a, b) { return (tally[a] || 0) - (tally[b] || 0); });
  var picked = candidates[0];
  tally[picked] = (tally[picked] || 0) + 1;
  return picked;
}

/** Same as pickLeastUsedOne_ but over an explicit word list rather than a
 * named cluster (used for far-distractor selection across a family). */
function pickLeastUsedFrom_(words, tally, rng) {
  var candidates = shuffle_(words, rng);
  candidates.sort(function (a, b) { return (tally[a] || 0) - (tally[b] || 0); });
  var picked = candidates[0];
  tally[picked] = (tally[picked] || 0) + 1;
  return picked;
}

// LAZY, not an eagerly-evaluated top-level IIFE -- see allWords_() below for
// why that distinction is load-bearing here.
var ALL_WORDS_ = null;

/**
 * Returns the flat 50-word list, computing it on first call and caching it.
 *
 * This MUST be lazy. It used to be `var ALL_WORDS_ = (function () {...})();`
 * -- an IIFE that ran immediately when this file's top-level code executed.
 * Apps Script concatenates a project's .gs files and runs their top-level
 * statements in FILENAME-ALPHABETICAL order before any function is called:
 * "PilotAssignment.gs" sorts before "PilotData.gs" ('A' < 'D'), so that IIFE
 * ran while `CLUSTERS` (declared in PilotData.gs) was still `undefined` --
 * hoisted but not yet assigned. `for (var c in undefined)` doesn't throw, it
 * just iterates zero times, so `ALL_WORDS_` silently became `[]` forever.
 * Every far-distractor pick (`pickLeastUsedFrom_(ALL_WORDS_.filter(...), ...)`
 * in pickDistractors_ below) then filtered an empty array and returned
 * `undefined` -- which is why the `real_far` option kept showing up with no
 * `word` (`JSON.stringify` silently drops `undefined`-valued properties,
 * so it read as a plan with a `real_far` option missing its `word` key
 * entirely, e.g. rendered as literal "undefined (real far)" text).
 * Wrapping the same computation in a function instead means it only runs
 * the first time something actually CALLS allWords_() -- by then every
 * file's top-level code has already finished executing, in any file order,
 * so CLUSTERS is guaranteed to be assigned. Local Node.js simulations of
 * this logic never reproduced the bug because those test harnesses always
 * concatenated PilotData.gs before PilotAssignment.gs (the correct
 * dependency order) -- this is an Apps-Script-execution-model-specific
 * failure mode that a same-order Node simulation can't surface.
 */
function allWords_() {
  if (!ALL_WORDS_) {
    ALL_WORDS_ = [];
    for (var c in CLUSTERS) { ALL_WORDS_ = ALL_WORDS_.concat(CLUSTERS[c]); }
  }
  return ALL_WORDS_;
}

/** Dynamically chosen (not a fixed table), balanced against the running
 * distractorTally. Returns [nearA, nearB, far]. */
function pickDistractors_(target, cluster, distractorTally, rng, descToCluster) {
  var neighbors = NEIGHBOR_CLUSTERS[cluster];
  var nearA = pickLeastUsedOne_(neighbors[0], distractorTally, rng);
  var nearB = pickLeastUsedOne_(neighbors[1], distractorTally, rng);

  var family = FAMILY_OF_CLUSTER[cluster];
  var otherFamilyWords = allWords_().filter(function (w) {
    return FAMILY_OF_CLUSTER[descToCluster[w]] !== family;
  });
  var far = pickLeastUsedFrom_(otherFamilyWords, distractorTally, rng);

  return [nearA, nearB, far];
}

function buildTrial_(target, rng, distractorTally, descToCluster) {
  var cluster = descToCluster[target];
  var distractors = pickDistractors_(target, cluster, distractorTally, rng, descToCluster);
  var near1 = distractors[0], near2 = distractors[1], far = distractors[2];

  // Which of the 2 near-distractor words gets realized as the AromaGen
  // composition vs. the real physical object is randomized per trial.
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
    cluster: cluster,
    odorant_set: ODORANT_SET_ID,
    options: options,
    correct_slot: correctSlot
  };
}

function buildTrials_(targetTally, distractorTally, rng, descToCluster) {
  var targets = [];
  for (var cluster in CLUSTERS) {
    targets.push(pickLeastUsedOne_(cluster, targetTally, rng));
  }
  targets = shuffle_(targets, rng);
  return targets.map(function (t) { return buildTrial_(t, rng, distractorTally, descToCluster); });
}

/**
 * targetTally, distractorTally: {descriptor: count}, both mutated in
 * place -- pass the running tallies from every session ever created, same
 * "continues from the true running total" contract as the Preliminary
 * Study's buildAssignment().
 */
function buildParticipantPlan_(seqIndex, targetTally, distractorTally, seed) {
  var rng = mulberry32_(seed || Date.now());
  var descToCluster = descriptorToCluster_();
  return {
    seq_index: seqIndex,
    feedback_type: feedbackTypeForParticipant_(seqIndex),
    odorant_set: ODORANT_SET_ID,
    trials: buildTrials_(targetTally, distractorTally, rng, descToCluster)
  };
}
