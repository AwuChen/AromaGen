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

/**
 * Picks 2 distinct distractor words for a target whose cluster is
 * `cluster`, from the EXCLUDED_CLUSTERS-derived eligible pool
 * (eligibleDistractorWords_, PilotData.gs) -- NOT a fixed ring-neighbor
 * pair anymore. Two layered rules, per explicit instruction:
 *
 * 1. HARD per-cluster non-repeat cycle: `clusterUsedSets[cluster]` tracks
 *    every word already used as a distractor for THIS target cluster,
 *    across every participant so far. A word already in that set cannot be
 *    picked again for this cluster until the set is exhausted (fewer than
 *    2 eligible words remain unused), at which point it resets to empty
 *    and a fresh cycle begins. Mutated in place -- same "continues from
 *    the true running total" contract as targetTally/distractorTally.
 * 2. Among whatever's left after rule 1, least-used-first (global
 *    distractorTally, random tie-break) -- the same balancing principle
 *    used throughout this project, so usage stays even across all 50
 *    words as distractors, not just non-repeating per cluster.
 *
 * See PilotData.gs's computeClusterUsedSets_ for how `clusterUsedSets` is
 * reconstructed fresh from history before each new plan is built -- the
 * reset-check here must stay in sync with that replay logic (checked once
 * per trial, as a unit, not per individual word).
 */
function pickDistractors_(target, cluster, distractorTally, rng, descToCluster, clusterUsedSets) {
  var eligibleWords = eligibleDistractorWords_(cluster);
  var usedSet = clusterUsedSets[cluster] || (clusterUsedSets[cluster] = {});

  var available = eligibleWords.filter(function (w) { return !usedSet[w]; });
  if (available.length < 2) {
    for (var k in usedSet) delete usedSet[k];
    available = eligibleWords.slice();
  }

  var nearA = pickLeastUsedFrom_(available, distractorTally, rng);
  var remaining = available.filter(function (w) { return w !== nearA; });
  var nearB = pickLeastUsedFrom_(remaining, distractorTally, rng);

  usedSet[nearA] = true;
  usedSet[nearB] = true;

  return [nearA, nearB];
}

/** Same as pickLeastUsedOne_ but over an explicit word list rather than a
 * named cluster (used for distractor selection, whose eligible pool spans
 * several clusters at once, not just one). */
function pickLeastUsedFrom_(words, tally, rng) {
  var candidates = shuffle_(words, rng);
  candidates.sort(function (a, b) { return (tally[a] || 0) - (tally[b] || 0); });
  var picked = candidates[0];
  tally[picked] = (tally[picked] || 0) + 1;
  return picked;
}

function buildTrial_(target, rng, distractorTally, descToCluster, clusterUsedSets) {
  var cluster = descToCluster[target];
  var distractors = pickDistractors_(target, cluster, distractorTally, rng, descToCluster, clusterUsedSets);
  var near1 = distractors[0], near2 = distractors[1];

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
    { kind: "real_near", word: realNearWord }
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

function buildTrials_(targetTally, distractorTally, rng, descToCluster, clusterUsedSets) {
  var targets = [];
  for (var cluster in CLUSTERS) {
    targets.push(pickLeastUsedOne_(cluster, targetTally, rng));
  }
  targets = shuffle_(targets, rng);
  return targets.map(function (t) { return buildTrial_(t, rng, distractorTally, descToCluster, clusterUsedSets); });
}

/**
 * targetTally, distractorTally, clusterUsedSets: all mutated in place --
 * pass the running state from every session ever created, same "continues
 * from the true running total" contract as the Preliminary Study's
 * buildAssignment().
 */
function buildParticipantPlan_(seqIndex, targetTally, distractorTally, seed, clusterUsedSets) {
  var rng = mulberry32_(seed || Date.now());
  var descToCluster = descriptorToCluster_();
  return {
    seq_index: seqIndex,
    feedback_type: feedbackTypeForParticipant_(seqIndex),
    odorant_set: ODORANT_SET_ID,
    trials: buildTrials_(targetTally, distractorTally, rng, descToCluster, clusterUsedSets || {})
  };
}
