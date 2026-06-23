const API_BASE = window.FREQUENCY_API_BASE || 'http://localhost:8000';

/**
 * Subtle chromatic emphasis on CTA hover
 */
document.querySelector('.cta-button')?.addEventListener('mouseenter', function () {
  this.style.setProperty('--chroma', '1');
});
document.querySelector('.cta-button')?.addEventListener('mouseleave', function () {
  this.style.setProperty('--chroma', '0.9');
});

document.getElementById('beginExperienceBtn')?.addEventListener('click', function (event) {
  event.preventDefault();
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'smooth' });
});

function bindImageUploadHandler(onImageSelected) {
  var imageInputEl = document.getElementById('frequencyImageInput');
  if (!imageInputEl || imageInputEl.dataset.bound === 'true') return;
  imageInputEl.dataset.bound = 'true';
  imageInputEl.addEventListener('change', function () {
    var file = imageInputEl.files && imageInputEl.files[0];
    imageInputEl.value = '';
    if (!file) return;
    onImageSelected(file);
  });
}

/**
 * Frequency section: record / stop button, then transcribe via OpenAI and show below circle
 */
(function () {
  var recordBtn = document.getElementById('frequencyRecordBtn');
  var transcriptionEl = document.getElementById('frequencyTranscriptionText');
  var statusEl = document.getElementById('frequencyTranscriptionStatus');
  var directTextInputEl = document.getElementById('frequencyDirectTextInput');
  var directSubmitBtnEl = document.getElementById('frequencyDirectSubmitBtn');
  if (!recordBtn) return;

  var micIcon = recordBtn.querySelector('.record-mic-icon');
  var stopIcon = recordBtn.querySelector('.record-stop-icon');
  var recordLabel = recordBtn.querySelector('.record-label');
  var mediaRecorder = null;
  var stream = null;
  var chunks = [];

  var progressEl = document.getElementById('frequencyProgress');
  var progressLabelEl = document.getElementById('frequencyProgressLabel');
  var progressFillEl = document.getElementById('frequencyProgressFill');

  function setRecording(recording) {
    recordBtn.classList.toggle('recording', recording);
    recordBtn.setAttribute('aria-label', recording ? 'Stop recording' : 'Record audio');
    if (recordLabel) recordLabel.textContent = recording ? 'Stop' : 'Record';
  }

  function setStatus(text, isError) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.style.color = isError ? 'rgba(255, 120, 120, 0.9)' : 'rgba(255, 255, 255, 0.5)';
  }

  function setTranscription(text) {
    if (transcriptionEl) transcriptionEl.textContent = text || '';
  }

  function showProgress(label, percent) {
    if (!progressEl || !progressFillEl) return;
    progressEl.classList.add('frequency-progress-visible');
    if (progressLabelEl && label) progressLabelEl.textContent = label;
    progressFillEl.style.width = (percent || 0) + '%';
  }

  function updateProgress(label, percent) {
    if (!progressEl || !progressFillEl) return;
    if (progressLabelEl && label) progressLabelEl.textContent = label;
    if (typeof percent === 'number') {
      progressFillEl.style.width = percent + '%';
    }
  }

  function hideProgress() {
    if (!progressEl || !progressFillEl) return;
    progressEl.classList.remove('frequency-progress-visible');
    progressFillEl.style.width = '0%';
    if (progressLabelEl) progressLabelEl.textContent = '';
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    if (stream) {
      stream.getTracks().forEach(function (t) { t.stop(); });
      stream = null;
    }
    setRecording(false);
  }

  function processInputText(text, opts) {
    var options = opts || {};
    var forceCompose = !!options.forceCompose;
    var trimmedText = (text || '').trim();
    if (!trimmedText) {
      setStatus('Please enter transcript or direct text.', true);
      return Promise.resolve();
    }

    setTranscription(trimmedText);
    updateProgress('Fetching database', 45);

    var scentPromise;
    if (!forceCompose && isInFeedbackMode) {
      updateProgress('Refining scent', 70);
      scentPromise = feedbackScent(trimmedText);
    } else {
      updateProgress('Composing scent', 70);
      scentPromise = composeScent(trimmedText);
    }

    return scentPromise.then(function (sequence) {
      setStatus('');
      if (sequence && sequence.length) {
        if (forceCompose || !isInFeedbackMode) {
          // Treat direct text as a fresh composition source.
          sessionHistory = [];
          sessionOriginalSentence = trimmedText;
          sessionOriginalSequence = sequence;
          isInFeedbackMode = true;
        }
        currentSequence = sequence;
        renderProfile(sequence);
        if (pendingCartridgeSwap && pendingCartridgeSwap.required) {
          updateProgress('Cartridge swap required', 100);
        } else {
          updateProgress('Complete', 100);
        }
        setTimeout(hideProgress, 800);
        return Promise.resolve();
      }

      setStatus('No scent sequence generated.');
      updateProgress('No scent generated', 100);
      setTimeout(hideProgress, 800);
      return Promise.resolve();
    });
  }

  function sendForTranscription(blob, mimeType) {
    showProgress('Transcribing', 20);
    setStatus('');
    setTranscription('');
    var form = new FormData();
    var ext = (mimeType || '').indexOf('webm') !== -1 ? 'webm' : 'ogg';
    form.append('audio', blob, 'recording.' + ext);
    if (sessionId) form.append('session_id', sessionId);

    fetch(API_BASE + '/transcribe', {
      method: 'POST',
      body: form
    })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (body) { throw new Error(body.detail || res.statusText); });
        return res.json();
      })
      .then(function (data) {
        var text = data.text || '';
        return processInputText(text);
      })
      .catch(function (err) {
        setStatus('Transcription failed: ' + (err.message || err));
        setTranscription('');
        hideProgress();
      });
  }

  function sendImageForDescription(file) {
    showProgress('Describing image', 20);
    setStatus('Analyzing image...');
    setTranscription('');
    var form = new FormData();
    form.append('image', file, file.name || 'upload.jpg');
    if (sessionId) form.append('session_id', sessionId);

    fetch(API_BASE + '/describe_image', {
      method: 'POST',
      body: form
    })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (body) { throw new Error(body.detail || res.statusText); });
        return res.json();
      })
      .then(function (data) {
        var text = data.text || '';
        if (!text) {
          throw new Error('No description returned');
        }
        if (!isInFeedbackMode) {
          renderProfile([]);
        }
        return processInputText(text, { forceCompose: true });
      })
      .catch(function (err) {
        setStatus('Image description failed: ' + (err.message || err), true);
        setTranscription('');
        hideProgress();
      });
  }

  bindImageUploadHandler(sendImageForDescription);

  recordBtn.addEventListener('click', function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (recordBtn.classList.contains('recording')) {
      stopRecording();
      return;
    }

    chunks = [];
    setRecording(true);
    // Reset UI for new run (only clear nodes on first compose, not during feedback)
    if (!isInFeedbackMode) {
      renderProfile([]);
    }
    hideProgress();
    setTranscription('');
    setStatus('');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setRecording(false);
      if (window.alert) window.alert('Your browser does not support recording. Try Chrome or Firefox.');
      return;
    }

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function (s) {
        stream = s;
        var options = { mimeType: 'audio/webm;codecs=opus' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          options = {};
        }
        mediaRecorder = new MediaRecorder(stream, options);
        mediaRecorder.ondataavailable = function (ev) {
          if (ev.data.size > 0) chunks.push(ev.data);
        };
        mediaRecorder.onstop = function () {
          if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
          }
          if (chunks.length) {
            var blob = new Blob(chunks, { type: mediaRecorder.mimeType || 'audio/webm' });
            sendForTranscription(blob, mediaRecorder.mimeType);
          }
        };
        mediaRecorder.start();
      })
      .catch(function (err) {
        console.warn('Recording not available:', err);
        setRecording(false);
        if (window.alert) {
          window.alert('Microphone access is needed to record. Please allow the site to use your microphone and try again.');
        }
      });
  });

  if (directSubmitBtnEl && directTextInputEl) {
    directSubmitBtnEl.addEventListener('click', function () {
      var directText = (directTextInputEl.value || '').trim();
      if (!directText) {
        setStatus('Please enter direct text before submitting.', true);
        return;
      }

      if (!isInFeedbackMode) {
        renderProfile([]);
      }
      showProgress('Composing from direct text', 25);
      setStatus('');
      processInputText(directText, { forceCompose: true }).catch(function (err) {
        setStatus('Direct input failed: ' + (err.message || err), true);
        hideProgress();
      });
    });

    directTextInputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        directSubmitBtnEl.click();
      }
    });
  }
})();

/*
Below is the original code for scent composition from death_sentence/script.js, now modified to take in the transcription and composed a scent sequence based on the transcription. 
*/

// Base notes are loaded from the cartridge API; fallback to scent_classification.json
const baseNotes = [];
let scentsData = {};
let cartridgeStatus = null;
let pendingCartridgeSwap = null;
let currentSequence = null; // Store the last generated sequence for playback

// Feedback loop session state
let sessionOriginalSentence = null;
let sessionOriginalSequence = null;
let sessionHistory = []; // Array of {feedback_text, changes_made, resulting_sequence}
let sessionId = null;
let isInFeedbackMode = false;

// Load active cartridge scents (slot locations reflect what is physically loaded)
function loadActiveCartridgeScents() {
  return fetch(API_BASE + '/cartridge/active')
    .then(function (res) {
      if (!res.ok) throw new Error('Cartridge API unavailable');
      return res.json();
    })
    .then(function (data) {
      scentsData = data.scents || {};
      cartridgeStatus = data.status || null;
      const names = Object.keys(scentsData);
      baseNotes.splice(0, baseNotes.length, ...names);
      renderCartridgeStatus();
      return data;
    })
    .catch(function (err) {
      console.warn('Cartridge API failed, falling back to scent_classification.json', err);
      return fetch('./scent_classification.json?v=' + Date.now())
        .then(function (r) { if (!r.ok) throw new Error('Missing scent_classification.json'); return r.json(); })
        .then(function (data) {
          scentsData = data || {};
          const names = Object.keys(scentsData);
          if (names.length === 0) throw new Error('scent_classification.json has no entries');
          baseNotes.splice(0, baseNotes.length, ...names);
        });
    });
}

loadActiveCartridgeScents();

function cartridgeShortLabel(label, setId) {
  if (!label) return setId || '';
  if (setId === 'perfume' || /perfume/i.test(label)) return 'Perfume';
  if (/food/i.test(label)) return 'Food';
  return label.replace(/\s*\(.*\)\s*/g, '').trim();
}

function renderCartridgeStatus() {
  var statusEl = document.getElementById('cartridgeStatusText');
  if (!statusEl || !cartridgeStatus) return;
  var left = cartridgeShortLabel(cartridgeStatus.left_label, cartridgeStatus.left_set);
  var right = cartridgeShortLabel(cartridgeStatus.right_label, cartridgeStatus.right_set);
  statusEl.textContent = 'L · ' + left + '  ·  R · ' + right;
}

function showCartridgeSwapNotice(swapInfo) {
  pendingCartridgeSwap = swapInfo || null;
  var blockEl = document.getElementById('cartridgeSwapBlock');
  var noticeEl = document.getElementById('cartridgeSwapNotice');
  var confirmBtn = document.getElementById('cartridgeConfirmSwapBtn');
  if (!blockEl || !noticeEl) return;

  if (!swapInfo || !swapInfo.required) {
    blockEl.hidden = true;
    noticeEl.textContent = '';
    return;
  }

  blockEl.hidden = false;
  noticeEl.textContent = swapInfo.instruction;
  if (confirmBtn) {
    confirmBtn.dataset.side = swapInfo.side_to_swap;
    confirmBtn.dataset.swapTo = swapInfo.swap_to_set;
  }
}

function applyCartridgeSwapState(side, swapToSet) {
  var leftSet = (cartridgeStatus && cartridgeStatus.left_set) || 'food_left';
  var rightSet = (cartridgeStatus && cartridgeStatus.right_set) || 'food_right';
  if (side === 'left') {
    leftSet = swapToSet;
  } else if (side === 'right') {
    rightSet = swapToSet;
  }

  return fetch(API_BASE + '/cartridge/state', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ left_set: leftSet, right_set: rightSet })
  })
    .then(function (res) {
      if (!res.ok) return res.json().then(function (body) { throw new Error(body.detail || res.statusText); });
      return res.json();
    })
    .then(function (data) {
      scentsData = data.scents || {};
      cartridgeStatus = data.status || null;
      renderCartridgeStatus();
      showCartridgeSwapNotice(null);
      alert('Cartridge state updated. You can play the sequence now.');
    })
    .catch(function (err) {
      alert('Could not update cartridge state: ' + err.message);
    });
}

document.getElementById('cartridgeConfirmSwapBtn')?.addEventListener('click', function () {
  var side = this.dataset.side;
  var swapTo = this.dataset.swapTo;
  if (!side || !swapTo) return;
  applyCartridgeSwapState(side, swapTo);
});

function handleComposeResponse(data) {
  if (data.session_id) sessionId = data.session_id;
  console.log('[Compose] Justification:', data.justification);
  if (data.cartridge_swap && data.cartridge_swap.required) {
    showCartridgeSwapNotice(data.cartridge_swap);
  } else {
    showCartridgeSwapNotice(null);
  }
  return data.scent_sequence || null;
}

async function composeScent(sentence) {
  try {
    const res = await fetch(API_BASE + '/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sentence })
    });
    if (!res.ok) {
      const msg = await res.text();
      alert(`Composition failed: ${msg}`);
      return null;
    }
    const data = await res.json();
    return handleComposeResponse(data);
  } catch (err) {
    console.error(err);
    alert('Network error calling composition service. Is the backend running on :8000?');
    return null;
  }
}

async function feedbackScent(feedbackText) {
  try {
    const res = await fetch(API_BASE + '/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        original_sentence: sessionOriginalSentence,
        original_sequence: sessionOriginalSequence,
        prior_rounds: sessionHistory,
        latest_feedback: feedbackText,
        session_id: sessionId
      })
    });
    if (!res.ok) {
      const msg = await res.text();
      alert(`Refinement failed: ${msg}`);
      return null;
    }
    const data = await res.json();
    if (data.scent_sequence) {
      if (data.session_id) sessionId = data.session_id;
      sessionHistory.push({
        feedback_text: feedbackText,
        changes_made: data.changes_made || '',
        resulting_sequence: data.scent_sequence
      });
    }
    console.log('[Feedback] Justification:', data.justification);
    console.log('[Feedback] Changes made:', data.changes_made);
    if (data.cartridge_swap && data.cartridge_swap.required) {
      showCartridgeSwapNotice(data.cartridge_swap);
    } else {
      showCartridgeSwapNotice(null);
    }
    return data.scent_sequence || null;
  } catch (err) {
    console.error(err);
    alert('Network error calling feedback service. Is the backend running on :8000?');
    return null;
  }
}

function resetSession() {
  sessionOriginalSentence = null;
  sessionOriginalSequence = null;
  sessionHistory = [];
  sessionId = null;
  isInFeedbackMode = false;
}

async function acceptScent() {
  if (!currentSequence || currentSequence.length === 0) {
    alert('No sequence to accept. Generate a scent sequence first!');
    return;
  }
  if (!sessionOriginalSentence) {
    alert('No session to accept. Compose or refine a sequence first.');
    return;
  }

  const acceptBtn = document.getElementById('acceptSequenceBtn');
  if (acceptBtn) acceptBtn.disabled = true;

  try {
    const res = await fetch(API_BASE + '/accept', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        original_sentence: sessionOriginalSentence,
        final_sequence: currentSequence,
        feedback_rounds: sessionHistory,
        session_id: sessionId
      })
    });
    if (!res.ok) {
      const msg = await res.text();
      alert(`Could not save composition: ${msg}`);
      return;
    }
    const data = await res.json();
    if (data.session_id) sessionId = data.session_id;
    alert('Saved! This composition will help improve future scent generation.');
    resetSession();
  } catch (err) {
    console.error(err);
    alert('Network error calling accept service. Is the backend running on :8000?');
  } finally {
    if (acceptBtn) acceptBtn.disabled = false;
  }
}

document.getElementById('acceptSequenceBtn')?.addEventListener('click', acceptScent);

function computeMortality(prompt) {
  const rng = mulberry32(hashString(prompt || 'default'));
  return Math.round(10 * (0.4 + rng() * 0.6)) / 1;
}

const NODE_ORDER = ['12', '130', '3', '430', '6', '730', '9', '1030'];

function setLoading(isLoading) {
  // No loader UI in business_demo; no-op
}

function renderProfile(sequence) {
  const nodes = NODE_ORDER.map(id => document.querySelector('.frequency-node-' + id)).filter(Boolean);
  nodes.forEach(node => {
    node.classList.remove('frequency-node-visible');
    const label = node.querySelector('.node-label');
    if (label) label.textContent = '';
  });

  sequence.slice(0, 8).forEach((item, i) => {
    const node = nodes[i];
    if (!node) return;
    const label = node.querySelector('.node-label');
    console.log(item.scent_name);
    if (label) label.textContent = item.scent_name || '';

    setTimeout(() => {
      node.classList.add('frequency-node-visible');
    }, i * 400);
  });
}

// Utils
function pickUnique(arr, count, rng) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1));[a[i], a[j]] = [a[j], a[i]]; }
  return a.slice(0, count);
}

function hashString(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(a) {
  return function () {
    let t = a += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// BLE Integration Functions
async function playSequenceOnDevice() {
  if (!currentSequence || currentSequence.length === 0) {
    alert('No sequence to play. Generate a scent sequence first!');
    return;
  }

  if (pendingCartridgeSwap && pendingCartridgeSwap.required) {
    alert('Cartridge swap required before playback:\n\n' + pendingCartridgeSwap.instruction);
    return;
  }

  // Refresh active scents so slot locations match the loaded cartridge halves
  try {
    await loadActiveCartridgeScents();
  } catch (e) {
    console.warn('Could not refresh cartridge scents', e);
  }

  // Convert scent names to scent_ids using the location field, skipping unknown scents
  const bleSequence = [];
  for (const item of currentSequence) {
    const meta = scentsData[item.scent_name];
    if (!meta || !meta.location) {
      console.warn(`Skipping scent with no device location: ${item.scent_name}`);
      continue;
    }
    const locId = parseInt(meta.location);
    if (locId < 1 || locId > 12) {
      console.warn(`Skipping scent outside device range (1-12): ${item.scent_name} (location=${locId})`);
      continue;
    }
    bleSequence.push({ scent_id: locId, duration: item.scent_duration });
  }

  if (bleSequence.length === 0) {
    alert('No playable scents in sequence (all scents are outside device range 1-12).');
    return;
  }

  try {
    setLoading(true);
    const playBtn = document.getElementById('playSequenceBtn');
    if (playBtn) playBtn.disabled = true;

    const response = await fetch('http://localhost:5001/play_sequence', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sequence: bleSequence })
    });

    const result = await response.json();

    if (result.status === 'success') {
      alert('✅ Sequence is playing on your device!');
    } else {
      alert(`❌ Error: ${result.message}`);
    }
  } catch (err) {
    console.error('BLE Error:', err);
    alert('❌ Could not connect to BLE device. Make sure:\n1. The Flask backend is running on :5001\n2. Your BLE device is powered on\n3. Device is in range');
  } finally {
    setLoading(false);
    const playBtn = document.getElementById('playSequenceBtn');
    if (playBtn) playBtn.disabled = false;
  }
}

async function testBLEConnection() {
  try {
    setLoading(true);
    const response = await fetch('http://localhost:5001/test_connection', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const result = await response.json();

    if (result.status === 'success') {
      alert(`✅ ${result.message}`);
    } else {
      alert(`❌ ${result.message}`);
    }
  } catch (err) {
    console.error('Connection test error:', err);
    alert('❌ Could not connect to BLE backend. Make sure the Flask server is running on :5001');
  } finally {
    setLoading(false);
  }
}
