/**
 * Balanced-coverage assignment engine.
 *
 * IMPORTANT CHANGE from the first version: the original buildAssignment()
 * balanced coverage only WITHIN a single call -- if you generated 4
 * participants today and 26 more next week, the second call had no idea
 * what the first 4 had already been assigned, so global balance across all
 * 30 was never guaranteed unless every participant was generated in one
 * call. That's now fixed: assignment is greedy against a *tally* (how many
 * times each descriptor has already been used as a target, across every
 * participant ever generated -- computed fresh from form_registry in
 * FormBuilder.gs's computeDescriptorTally_, not a separately-maintained
 * counter that could drift out of sync). Every new batch, regardless of
 * batch size or how many prior batches came before it, picks each
 * participant's descriptors from whichever are currently least-used in
 * their cluster. This is what makes "generate 4 now, generate 26 later"
 * behave the same as "generate all 30 at once."
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

/** Picks the r least-used descriptors in a cluster, ties broken randomly.
 * Mutates `tally` in place so the next call (next cluster, next
 * participant) sees the updated counts -- this is what keeps a whole batch
 * internally balanced, not just balanced against history. */
function pickLeastUsed_(cluster, r, tally, rng) {
  var candidates = shuffle_(CLUSTERS[cluster], rng);
  candidates.sort(function (a, b) { return tally[a] - tally[b]; });
  var picked = candidates.slice(0, r);
  picked.forEach(function (d) { tally[d] = (tally[d] || 0) + 1; });
  return picked;
}

function isPleasant_(cluster) {
  return PLEASANT_CLUSTERS.indexOf(cluster) !== -1;
}

/**
 * Returns { participantId: [ {descriptor, cluster, options, correctIndex}, ... ] }.
 * `tally`: descriptor -> current global usage count (from
 * computeDescriptorTally_ in FormBuilder.gs) -- mutated in place as this
 * batch is assigned. n_exposures must be 12 or 24. Trial order per
 * participant: all 6 pleasant-cluster trials first (shuffled among
 * themselves), then all 6 unpleasant-cluster trials (shuffled among
 * themselves) -- confirmed design, a hard split, not a smooth gradient.
 */
function buildAssignment(participantIds, nExposures, tally, seed) {
  if (nExposures !== 12 && nExposures !== 24) {
    throw new Error("nExposures must be 12 or 24");
  }
  var r = nExposures / 12;
  var rng = mulberry32_(seed || Date.now());

  var assignments = {};
  participantIds.forEach(function (pid) {
    var pleasantTrials = [];
    var unpleasantTrials = [];
    for (var cluster in CLUSTERS) {
      var picks = pickLeastUsed_(cluster, r, tally, rng);
      picks.forEach(function (target) {
        var distractors = DISTRACTOR_TABLE[target];
        var options = shuffle_(distractors.concat([target]), rng);
        var trial = {
          descriptor: target,
          cluster: cluster,
          options: options,
          correctIndex: options.indexOf(target)
        };
        (isPleasant_(cluster) ? pleasantTrials : unpleasantTrials).push(trial);
      });
    }
    var ordered = shuffle_(pleasantTrials, rng).concat(shuffle_(unpleasantTrials, rng));
    assignments[pid] = ordered;
  });
  return assignments;
}

function sampleSizeReport(evalsPerDescriptor, buffer) {
  evalsPerDescriptor = evalsPerDescriptor || 30;
  buffer = buffer === undefined ? 0.15 : buffer;
  var totalTrialsNeeded = 50 * evalsPerDescriptor;
  var report = {};
  [12, 24].forEach(function (n) {
    var participantsNeeded = Math.ceil(totalTrialsNeeded / n);
    report[n] = {
      participantsNeeded: participantsNeeded,
      recruitWithBuffer: Math.ceil(participantsNeeded * (1 + buffer))
    };
  });
  return report;
}

function realisticCoverage(nParticipants, nExposures) {
  return (nParticipants * nExposures / 50);
}
