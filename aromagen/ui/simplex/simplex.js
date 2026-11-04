const API_BASE = window.AROMAGEN_API_BASE || 'http://127.0.0.1:8000';

/** Must match SVG polygon vertex order: A (bottom), B (top-left), C (top-right). */
const TRIANGLE = {
  A: { x: 0.5, y: Math.sqrt(3) / 2 },
  B: { x: 0, y: 0 },
  C: { x: 1, y: 0 },
};

const CORNER_SNAP_RADIUS = 0.06;

function syncTriangleSvgGeometry() {
  const poly = document.getElementById('simplexFill');
  if (!poly) return;
  const pts = [TRIANGLE.A, TRIANGLE.B, TRIANGLE.C]
    .map(function (v) { return v.x + ',' + v.y; })
    .join(' ');
  poly.setAttribute('points', pts);
}

function assertBarycentricCornerMapping() {
  function near(a, b, eps) {
    return Math.abs(a - b) <= eps;
  }
  const eps = 0.02;
  const atA = barycentricFromPoint(TRIANGLE.A.x, TRIANGLE.A.y);
  const atB = barycentricFromPoint(TRIANGLE.B.x, TRIANGLE.B.y);
  const atC = barycentricFromPoint(TRIANGLE.C.x, TRIANGLE.C.y);
  if (!near(atA[0], 1, eps) || !near(atB[1], 1, eps) || !near(atC[2], 1, eps)) {
    console.error('[simplex] Barycentric corner mapping failed', { atA: atA, atB: atB, atC: atC });
  }
}

function snapToCorner(px, py) {
  const corners = [
    { key: 'A', v: TRIANGLE.A },
    { key: 'B', v: TRIANGLE.B },
    { key: 'C', v: TRIANGLE.C },
  ];
  let best = null;
  let bestDist = CORNER_SNAP_RADIUS;
  corners.forEach(function (c) {
    const dx = px - c.v.x;
    const dy = py - c.v.y;
    const d = Math.sqrt(dx * dx + dy * dy);
    if (d < bestDist) {
      bestDist = d;
      best = c.v;
    }
  });
  return best ? { x: best.x, y: best.y } : { x: px, y: py };
}

let anchors = [];
let centerSmell = null;
let scentsData = {};
let currentBlend = null;
let dragActive = false;

const els = {
  targetInput: document.getElementById('targetInput'),
  statusLine: document.getElementById('statusLine'),
  anchorsGrid: document.getElementById('anchorsGrid'),
  simplexSvg: document.getElementById('simplexSvg'),
  blendDot: document.getElementById('blendDot'),
  wA: document.getElementById('wA'),
  wB: document.getElementById('wB'),
  wC: document.getElementById('wC'),
  labelA: document.getElementById('labelA'),
  labelB: document.getElementById('labelB'),
  labelC: document.getElementById('labelC'),
  recipeOut: document.getElementById('recipeOut'),
  corpusNote: document.getElementById('corpusNote'),
  corpusNearest: document.getElementById('corpusNearest'),
};

function setStatus(text, isError) {
  if (!els.statusLine) return;
  els.statusLine.textContent = text || '';
  els.statusLine.classList.toggle('error', !!isError);
}

function explainFetchError(err, context) {
  const msg = String((err && err.message) || err || 'Failed to fetch');
  if (msg.toLowerCase().includes('failed to fetch') || err instanceof TypeError) {
    if (window.location.protocol === 'file:') {
      return (
        'This page was opened as a file, not from the local server. ' +
        'Run ./scripts/start_simplex_ui.sh and open http://127.0.0.1:8081'
      );
    }
    return (
      (context ? context + ': ' : '') +
      'Cannot reach the AI backend at ' + API_BASE + '. ' +
      'Check the “AI Backend (Port 8000)” tab or run ./restart_ai_backend.sh, ' +
      'then confirm http://127.0.0.1:8000/health returns OK.'
    );
  }
  if (msg.includes('BLE backend not reachable') || msg.includes('503')) {
    return msg;
  }
  return (context ? context + ': ' : '') + msg;
}

async function checkApiHealth() {
  const res = await fetch(API_BASE + '/health', { method: 'GET' });
  if (!res.ok) {
    throw new Error('AI backend health check returned HTTP ' + res.status);
  }
  return res.json();
}

function summarizeRecipe(sequence) {
  if (!sequence || !sequence.length) return '—';
  const total = sequence.reduce(function (sum, item) {
    return sum + (typeof item.ratio === 'number' ? item.ratio : 0);
  }, 0);
  return sequence.map(function (item) {
    const pct = total > 0 ? Math.round((item.ratio / total) * 100) + '%' : '';
    return (item.scent_name || '') + (pct ? ' · ' + pct : '');
  }).join('\n');
}

function barycentricFromPoint(px, py) {
  const a = TRIANGLE.A;
  const b = TRIANGLE.B;
  const c = TRIANGLE.C;
  const v0x = c.x - a.x;
  const v0y = c.y - a.y;
  const v1x = b.x - a.x;
  const v1y = b.y - a.y;
  const v2x = px - a.x;
  const v2y = py - a.y;
  const dot00 = v0x * v0x + v0y * v0y;
  const dot01 = v0x * v1x + v0y * v1y;
  const dot11 = v1x * v1x + v1y * v1y;
  const dot20 = v2x * v0x + v2y * v0y;
  const dot21 = v2x * v1x + v2y * v1y;
  const denom = dot00 * dot11 - dot01 * dot01;
  if (Math.abs(denom) < 1e-12) return [1 / 3, 1 / 3, 1 / 3];
  // p = A + w*(B-A) + v*(C-A)  =>  u*A + w*B + v*C
  const coeffC = (dot11 * dot20 - dot01 * dot21) / denom;
  const coeffB = (dot00 * dot21 - dot01 * dot20) / denom;
  let wA = Math.max(1 - coeffC - coeffB, 0);
  let wB = Math.max(coeffB, 0);
  let wC = Math.max(coeffC, 0);
  const s = wA + wB + wC || 1;
  return [wA / s, wB / s, wC / s];
}

function pointFromBarycentric(weights) {
  const w = weights;
  const s = w[0] + w[1] + w[2] || 1;
  const x = (w[0] / s) * TRIANGLE.A.x + (w[1] / s) * TRIANGLE.B.x + (w[2] / s) * TRIANGLE.C.x;
  const y = (w[0] / s) * TRIANGLE.A.y + (w[1] / s) * TRIANGLE.B.y + (w[2] / s) * TRIANGLE.C.y;
  return { x, y };
}

function updateWeightsDisplay(weights) {
  if (els.wA) els.wA.textContent = weights[0].toFixed(2);
  if (els.wB) els.wB.textContent = weights[1].toFixed(2);
  if (els.wC) els.wC.textContent = weights[2].toFixed(2);
}

/** Map click/drag to barycentric weights, then snap the dot to the nearest point inside the triangle. */
function setDotPosition(px, py) {
  const weights = barycentricFromPoint(px, py);
  const constrained = pointFromBarycentric(weights);
  if (els.blendDot) {
    els.blendDot.setAttribute('cx', constrained.x);
    els.blendDot.setAttribute('cy', constrained.y);
  }
  updateWeightsDisplay(weights);
  return weights;
}

function svgPointFromEvent(evt) {
  const svg = els.simplexSvg;
  const pt = svg.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  const ctm = svg.getScreenCTM();
  if (!ctm) return { x: 0.5, y: 0.288 };
  const local = pt.matrixTransform(ctm.inverse());
  return { x: local.x, y: local.y };
}

function renderAnchors() {
  if (!els.anchorsGrid) return;
  els.anchorsGrid.innerHTML = anchors.map(function (anchor, idx) {
    const label = anchor.label || ('Token ' + anchor.token);
    const recipe = summarizeRecipe(anchor.scent_sequence);
    return (
      '<article class="anchor-card">' +
      '<h3>' + escapeHtml(label) + '</h3>' +
      '<pre class="recipe">' + escapeHtml(recipe) + '</pre>' +
      '<button type="button" class="play-anchor" data-idx="' + idx + '">Smell anchor ' + escapeHtml(anchor.token) + '</button>' +
      '</article>'
    );
  }).join('');

  els.anchorsGrid.querySelectorAll('.play-anchor').forEach(function (btn) {
    btn.addEventListener('click', function () {
      const idx = parseInt(btn.getAttribute('data-idx'), 10);
      playAnchor(idx);
    });
  });

  if (els.labelA && anchors[0]) els.labelA.textContent = anchors[0].token || 'A';
  if (els.labelB && anchors[1]) els.labelB.textContent = anchors[1].token || 'B';
  if (els.labelC && anchors[2]) els.labelC.textContent = anchors[2].token || 'C';
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function loadCartridgeCatalog() {
  const res = await fetch(API_BASE + '/cartridge/active');
  if (!res.ok) throw new Error('Could not load cartridge catalog');
  const data = await res.json();
  scentsData = data.scents || {};
}

async function playPulseSequence(pulseSequence, fallbackSequence) {
  const source = pulseSequence && pulseSequence.length ? pulseSequence : fallbackSequence;
  if (!source || !source.length) {
    alert('Nothing to play.');
    return;
  }
  const bleSequence = [];
  for (const item of source) {
    const meta = scentsData[item.scent_name];
    if (!meta || !meta.location) continue;
    const locId = parseInt(meta.location, 10);
    if (locId < 1 || locId > 12) continue;
    bleSequence.push({ scent_id: locId, duration: item.scent_duration || 1 });
  }
  if (!bleSequence.length) {
    alert('No playable scents (check cartridge locations).');
    return;
  }
  let response;
  try {
    response = await fetch(API_BASE + '/device/play_sequence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence: bleSequence }),
    });
  } catch (err) {
    throw new Error(explainFetchError(err, 'Device playback'));
  }
  const result = await response.json().catch(function () {
    return { detail: 'HTTP ' + response.status };
  });
  if (!response.ok) {
    throw new Error(result.detail || result.message || 'Playback failed');
  }
  if (result.status !== 'success') {
    throw new Error(result.message || 'Playback failed');
  }
}

async function playAnchor(index) {
  const anchor = anchors[index];
  if (!anchor) return;
  try {
    setStatus('Playing anchor ' + anchor.token + '…');
    await playPulseSequence(anchor.pulse_sequence, anchor.scent_sequence);
    setStatus('Anchor ' + anchor.token + ' finished (or started on device).');
  } catch (err) {
    setStatus(explainFetchError(err, 'Smell anchor'), true);
  }
}

async function loadPresets() {
  setStatus('Loading demo anchors…');
  let res;
  try {
    res = await fetch(API_BASE + '/simplex/presets');
  } catch (err) {
    throw new Error(explainFetchError(err, 'Load presets'));
  }
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  anchors = data.anchors || [];
  centerSmell = null;
  renderCenter();
  renderAnchors();
  setStatus('Demo anchors ready. Smell A, B, C, then place your dot.');
}

function formatCenterSource(source, metadata) {
  const labels = {
    exact_log: 'Exact match in interaction log (best similarity round)',
    retrieved_log: 'Retrieved neighbor in log (highest similarity score)',
    retrieved_log_nearest: 'Retrieved neighbor in log (embedding match)',
    learned_example: 'Accept-bank example',
    composed_rag: 'New LLM compose with RAG (no strong log match)',
  };
  let text = labels[source] || source;
  if (metadata && metadata.matched_target) {
    text += ' · precedent: “' + metadata.matched_target + '”';
  }
  if (metadata && metadata.best_similarity != null) {
    text += ' · similarity ' + metadata.best_similarity;
  }
  return text;
}

function renderCenter() {
  const panel = document.getElementById('centerPanel');
  const metaEl = document.getElementById('centerMeta');
  const recipeEl = document.getElementById('centerRecipe');
  if (!centerSmell || !centerSmell.scent_sequence) {
    if (panel) panel.hidden = true;
    return;
  }
  if (panel) panel.hidden = false;
  if (metaEl) {
    metaEl.textContent = formatCenterSource(centerSmell.source, centerSmell.metadata || {});
  }
  if (recipeEl) {
    recipeEl.textContent = summarizeRecipe(centerSmell.scent_sequence);
  }
}

function getPrepareTriangleOptions() {
  const modeEl = document.querySelector('input[name="cornerMode"]:checked');
  const neutralEl = document.getElementById('neutralLabels');
  return {
    corner_mode: (modeEl && modeEl.value) || 'cluster',
    neutral_labels: !!(neutralEl && neutralEl.checked),
  };
}

async function prepareTriangle() {
  const target = (els.targetInput && els.targetInput.value.trim()) || '';
  if (!target) {
    setStatus('Enter a target smell first.', true);
    return;
  }
  const opts = getPrepareTriangleOptions();
  const btn = document.getElementById('prepareTriangleBtn');
  if (btn) btn.disabled = true;
  setStatus('Resolving center from log/RAG and building corners (' + opts.corner_mode + ')…');
  try {
    const res = await fetch(API_BASE + '/simplex/prepare_triangle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target: target,
        corner_mode: opts.corner_mode,
        neutral_labels: opts.neutral_labels,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    centerSmell = data.center || null;
    anchors = data.anchors || [];
    renderCenter();
    renderAnchors();
    centerDot();
    const spread = data.corner_min_pairwise_l2 != null ? data.corner_min_pairwise_l2 : '?';
    setStatus(
      'Triangle ready for “' + target + '”. Smell center, then A/B/C, then place your dot. ' +
      '(corner spread L2≈' + spread + ')'
    );
  } catch (err) {
    setStatus(explainFetchError(err, 'Prepare triangle'), true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function smellCenter() {
  if (!centerSmell) return;
  try {
    setStatus('Playing center…');
    await playPulseSequence(centerSmell.pulse_sequence, centerSmell.scent_sequence);
    setStatus('Center playing.');
  } catch (err) {
    setStatus(explainFetchError(err, 'Smell center'), true);
  }
}

async function generateAnchors() {
  const target = (els.targetInput && els.targetInput.value.trim()) || '';
  if (!target) {
    setStatus('Enter a target smell first.', true);
    return;
  }
  const btn = document.getElementById('generateAnchorsBtn');
  if (btn) btn.disabled = true;
  setStatus('Generating three anchor compositions (this may take a minute)…');
  try {
    const res = await fetch(API_BASE + '/simplex/prepare_anchors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      throw new Error(err.detail || res.statusText);
    }
    const data = await res.json();
    anchors = data.anchors || [];
    renderAnchors();
    setStatus('Anchors generated for “' + target + '”. Smell each corner, then click the triangle.');
  } catch (err) {
    setStatus(explainFetchError(err, 'Generate anchors'), true);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function mixFromCurrentPoint() {
  if (anchors.length !== 3) {
    setStatus('Load or generate three anchors first.', true);
    return;
  }
  const px = parseFloat(els.blendDot.getAttribute('cx'));
  const py = parseFloat(els.blendDot.getAttribute('cy'));
  setStatus('Blending recipes…');
  const res = await fetch(API_BASE + '/simplex/from_point', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      anchors: anchors,
      point_x: px,
      point_y: py,
      use_corpus_nearest: !!(els.corpusNearest && els.corpusNearest.checked),
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(function () { return {}; });
    throw new Error(err.detail || res.statusText);
  }
  currentBlend = await res.json();
  if (els.recipeOut) els.recipeOut.textContent = summarizeRecipe(currentBlend.scent_sequence);
  if (els.corpusNote) {
    if (currentBlend.source === 'corpus' && currentBlend.corpus_match) {
      els.corpusNote.textContent =
        'Used nearest corpus recipe: “' + (currentBlend.corpus_match.sentence || '') + '”.';
    } else {
      els.corpusNote.textContent = 'Linear blend r = w₁r_A + w₂r_B + w₃r_C (normalized).';
    }
  }
  updateWeightsDisplay(currentBlend.weights);
  return currentBlend;
}

async function mixAndPlay() {
  try {
    const blend = await mixFromCurrentPoint();
    setStatus('Playing blend on device…');
    await playPulseSequence(blend.pulse_sequence, blend.scent_sequence);
    setStatus('Blend playing. Nudge the dot and mix again, or start another round.');
  } catch (err) {
    setStatus(String(err.message || err), true);
  }
}

function releasePointerIfCaptured(evt) {
  const svg = els.simplexSvg;
  if (!svg || !evt || evt.pointerId == null) return;
  try {
    if (svg.hasPointerCapture && svg.hasPointerCapture(evt.pointerId)) {
      svg.releasePointerCapture(evt.pointerId);
    }
  } catch (e) { /* ignore */ }
}

function finishTriangleDrag(evt) {
  if (!dragActive) return;
  dragActive = false;
  releasePointerIfCaptured(evt);
  if (!evt) return;
  const raw = svgPointFromEvent(evt);
  const snapped = snapToCorner(raw.x, raw.y);
  setDotPosition(snapped.x, snapped.y);
}

function bindTriangle() {
  if (!els.simplexSvg) return;
  const svg = els.simplexSvg;

  function onPointerDown(evt) {
    if (evt.button !== 0) return;
    dragActive = true;
    svg.setPointerCapture(evt.pointerId);
    const raw = svgPointFromEvent(evt);
    setDotPosition(raw.x, raw.y);
  }

  function onPointerMove(evt) {
    if (!dragActive) return;
    if ((evt.buttons & 1) === 0) {
      finishTriangleDrag(evt);
      return;
    }
    const raw = svgPointFromEvent(evt);
    setDotPosition(raw.x, raw.y);
  }

  svg.addEventListener('pointerdown', onPointerDown);
  svg.addEventListener('pointermove', onPointerMove);
  svg.addEventListener('pointerup', finishTriangleDrag);
  svg.addEventListener('pointercancel', finishTriangleDrag);
  window.addEventListener('pointerup', finishTriangleDrag);
  window.addEventListener('pointercancel', finishTriangleDrag);

  setDotPosition(0.5, 0.288);
}

function centerDot() {
  setDotPosition(0.5, 0.288);
  if (els.recipeOut) els.recipeOut.textContent = '—';
  if (els.corpusNote) els.corpusNote.textContent = '';
  currentBlend = null;
  setStatus('Dot centered (equal weights).');
}

function anotherRound() {
  centerDot();
  setStatus('New round: same anchors. Smell corners again if you want, then place the dot.');
}

document.getElementById('loadPresetsBtn')?.addEventListener('click', function () {
  loadPresets().catch(function (err) { setStatus(String(err.message || err), true); });
});
document.getElementById('prepareTriangleBtn')?.addEventListener('click', prepareTriangle);
document.getElementById('smellCenterBtn')?.addEventListener('click', smellCenter);
document.getElementById('generateAnchorsBtn')?.addEventListener('click', generateAnchors);
document.getElementById('mixPlayBtn')?.addEventListener('click', mixAndPlay);
document.getElementById('resetDotBtn')?.addEventListener('click', centerDot);
document.getElementById('anotherRoundBtn')?.addEventListener('click', anotherRound);

syncTriangleSvgGeometry();
assertBarycentricCornerMapping();
bindTriangle();

if (window.location.protocol === 'file:') {
  setStatus(
    'Open http://127.0.0.1:8081 after running ./scripts/start_simplex_ui.sh (not the HTML file directly).',
    true
  );
} else {
  checkApiHealth()
    .then(function () { return loadCartridgeCatalog(); })
    .then(function () { return loadPresets(); })
    .catch(function (err) {
      setStatus(explainFetchError(err, 'Startup'), true);
    });
}
