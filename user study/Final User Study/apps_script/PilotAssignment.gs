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
 * (eligibleDistractorWords_, PilotData.gs). THREE layered rules, given
 * STRICT priority in this order (a lower-priority rule yields when it
 * conflicts with a higher one, never the reverse):
 *
 * 1. HARD per-PARTICIPANT non-repeat, never relaxed: `usedThisParticipant`
 *    tracks every word already used as a distractor ANYWHERE in this
 *    participant's own session so far (any trial, any cluster) -- fresh/
 *    empty at the start of each participant. If this cluster's eligible
 *    pool has fewer than 2 words not yet used this session, returns null
 *    -- the caller (buildTrials_) must retry the whole session with
 *    different random target/order choices; it must NOT relax this rule
 *    to paper over the conflict.
 * 2. HARD per-cluster non-repeat cycle, subordinate to rule 1:
 *    `clusterUsedSets[cluster]` tracks every word already used as a
 *    distractor for THIS cluster across every participant so far. A word
 *    already in that set is excluded UNLESS doing so would leave fewer
 *    than 2 session-eligible candidates, in which case the cycle resets
 *    (cleared) rather than blocking the pick -- the global smoothing goal
 *    yields to the per-participant guarantee, not the other way around.
 * 3. Among whatever's left, least-used-first (global distractorTally,
 *    random tie-break).
 *
 * See PilotData.gs's computeClusterUsedSets_ for how `clusterUsedSets` is
 * reconstructed fresh from history before each new plan is built.
 */
function pickDistractors_(target, cluster, distractorTally, rng, descToCluster, clusterUsedSets, usedThisParticipant) {
  var eligibleWords = eligibleDistractorWords_(cluster);

  var sessionAvailable = eligibleWords.filter(function (w) { return !usedThisParticipant[w]; });
  if (sessionAvailable.length < 2) {
    return null;
  }

  var usedSet = clusterUsedSets[cluster] || (clusterUsedSets[cluster] = {});
  var cycleAvailable = sessionAvailable.filter(function (w) { return !usedSet[w]; });
  var available;
  if (cycleAvailable.length < 2) {
    for (var k in usedSet) delete usedSet[k];
    available = sessionAvailable;
  } else {
    available = cycleAvailable;
  }

  var nearA = pickLeastUsedFrom_(available, distractorTally, rng);
  var remaining = available.filter(function (w) { return w !== nearA; });
  var nearB = pickLeastUsedFrom_(remaining, distractorTally, rng);

  usedSet[nearA] = true;
  usedSet[nearB] = true;
  usedThisParticipant[nearA] = true;
  usedThisParticipant[nearB] = true;

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

/** Returns null (propagated from pickDistractors_) if this cluster's
 * eligible pool is exhausted for the current session -- the caller
 * (buildTrials_) must treat that as a failed attempt and retry. */
function buildTrial_(target, rng, distractorTally, descToCluster, clusterUsedSets, usedThisParticipant) {
  var cluster = descToCluster[target];
  var distractors = pickDistractors_(target, cluster, distractorTally, rng, descToCluster, clusterUsedSets, usedThisParticipant);
  if (distractors === null) return null;
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

function copyTally_(tally) {
  var copy = {};
  for (var k in tally) copy[k] = tally[k];
  return copy;
}

function copyClusterUsedSets_(clusterUsedSets) {
  var copy = {};
  for (var cluster in clusterUsedSets) {
    var copySet = {};
    for (var w in clusterUsedSets[cluster]) copySet[w] = true;
    copy[cluster] = copySet;
  }
  return copy;
}

function commitInto_(target, source) {
  for (var k in target) delete target[k];
  for (var k in source) target[k] = source[k];
}

var MAX_TRIAL_BUILD_ATTEMPTS_ = 200;

/**
 * Greedy trial-by-trial generation has no lookahead, so a single pass can
 * leave a later trial's eligible pool exhausted by earlier trials in the
 * same session even though pickDistractors_ tries its best in the moment.
 * Detect that after the fact and retry the WHOLE session against copies of
 * the running state, only committing mutations back to the real
 * targetTally/distractorTally/clusterUsedSets once a fully repeat-free
 * session is found -- a failed attempt must never leak into the real
 * running state, or coverage balancing across participants would be
 * thrown off by a discarded attempt's tally increments.
 */
function buildTrials_(targetTally, distractorTally, rng, descToCluster, clusterUsedSets) {
  for (var attempt = 0; attempt < MAX_TRIAL_BUILD_ATTEMPTS_; attempt++) {
    var ttCopy = copyTally_(targetTally);
    var dtCopy = copyTally_(distractorTally);
    var cusCopy = copyClusterUsedSets_(clusterUsedSets);
    var usedThisParticipant = {};

    var targets = [];
    for (var cluster in CLUSTERS) {
      targets.push(pickLeastUsedOne_(cluster, ttCopy, rng));
    }
    targets = shuffle_(targets, rng);

    var trials = [];
    var ok = true;
    for (var i = 0; i < targets.length; i++) {
      var trial = buildTrial_(targets[i], rng, dtCopy, descToCluster, cusCopy, usedThisParticipant);
      if (trial === null) { ok = false; break; }
      trials.push(trial);
    }
    if (!ok) continue;

    var allDistractors = [];
    trials.forEach(function (t) {
      t.options.forEach(function (o) {
        if (o.kind !== "aromagen_target") allDistractors.push(o.word);
      });
    });
    var uniqueDistractors = {};
    allDistractors.forEach(function (w) { uniqueDistractors[w] = true; });
    if (Object.keys(uniqueDistractors).length === allDistractors.length) {
      commitInto_(targetTally, ttCopy);
      commitInto_(distractorTally, dtCopy);
      commitInto_(clusterUsedSets, cusCopy);
      return trials;
    }
  }

  throw new Error(
    "Could not build a repeat-free trial session after " + MAX_TRIAL_BUILD_ATTEMPTS_ + " attempts -- " +
    "this should be astronomically unlikely; if this ever actually fires, the exclusion list or " +
    "cluster sizes have likely changed enough to make a repeat-free session mathematically impossible."
  );
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
