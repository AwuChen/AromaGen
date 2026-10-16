const API_BASE = window.FREQUENCY_API_BASE || 'http://localhost:8000';
const SCENE_IMAGE_PREF_KEY = 'aromagen_scene_image_enabled';

var uploadedImageObjectUrl = null;
var transcriptHiddenForImageUpload = false;
var imageTranscriptVisible = false;

function isSceneImageEnabled() {
  var stored = localStorage.getItem(SCENE_IMAGE_PREF_KEY);
  if (stored === null) return true;
  return stored === 'true';
}

function setSceneImageEnabled(enabled) {
  localStorage.setItem(SCENE_IMAGE_PREF_KEY, enabled ? 'true' : 'false');
  var btn = document.getElementById('sceneImageToggleBtn');
  if (btn) btn.classList.toggle('is-active', enabled);
  if (!enabled) {
    cancelSceneImagePoll();
    showGeneratedSceneImage(null);
  }
}

const LOG_SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1TBswegffpBQL_AAeMdSgM6qz9V1eC9aK09OAR_m5Ys4/edit';

function openLogSheet() {
  window.open(LOG_SPREADSHEET_URL, '_blank', 'noopener');
}

async function submitLogInteraction() {
  const statusEl = document.getElementById('logInteractionStatus');
  const setLogStatus = function (text, isError) {
    if (!statusEl) return;
    statusEl.textContent = text;
    statusEl.style.color = isError ? '#ff8080' : 'rgba(255, 255, 255, 0.5)';
  };

  if (!currentSequence || currentSequence.length === 0) {
    setLogStatus('No generated scent to log yet -- generate one first.', true);
    return;
  }

  const similarityInputEl = document.getElementById('logSimilarityInput');
  const feedbackInputEl = document.getElementById('logFeedbackInput');
  const submitBtnEl = document.getElementById('logInteractionSubmitBtn');

  const similarity = parseInt((similarityInputEl && similarityInputEl.value) || '', 10);
  if (isNaN(similarity) || similarity < 1 || similarity > 7) {
    setLogStatus('Enter a similarity rating from 1 to 7 before submitting.', true);
    return;
  }

  const transcriptionEl = document.getElementById('frequencyTranscriptionText');
  const targetSmell = sessionOriginalSentence || (transcriptionEl && transcriptionEl.textContent) || '';
  if (!targetSmell) {
    setLogStatus('No target smell text found to log.', true);
    return;
  }

  const payload = {
    target_smell: targetSmell,
    aromagen_ratio: summarizeRecipe(currentSequence),
    similarity: similarity,
    feedback: (feedbackInputEl && feedbackInputEl.value.trim()) || '',
    session_id: sessionId || null,
  };

  try {
    if (submitBtnEl) submitBtnEl.disabled = true;
    setLogStatus('Logging...');
    const response = await fetch(API_BASE + '/log_interaction', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errBody = await response.json().catch(function () { return {}; });
      throw new Error(errBody.detail || ('HTTP ' + response.status));
    }
    setLogStatus('Logged to sheet.');
    if (feedbackInputEl) feedbackInputEl.value = '';
    if (similarityInputEl) similarityInputEl.value = '';
  } catch (err) {
    setLogStatus('Failed to log: ' + (err.message || err), true);
  } finally {
    if (submitBtnEl) submitBtnEl.disabled = false;
  }
}

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
  var textualFeedbackToggleBtnEl = document.getElementById('textualFeedbackToggleBtn');
  var textualFeedbackRowEl = document.getElementById('textualFeedbackRow');
  var textualFeedbackInputEl = document.getElementById('textualFeedbackInput');
  var textualFeedbackSubmitBtnEl = document.getElementById('textualFeedbackSubmitBtn');
  var durationToggleBtnEl = document.getElementById('durationToggleBtn');
  var durationRowEl = document.getElementById('durationRow');
  var logInteractionToggleBtnEl = document.getElementById('logInteractionToggleBtn');
  var logInteractionRowEl = document.getElementById('logInteractionRow');
  var logSimilarityInputEl = document.getElementById('logSimilarityInput');
  var logFeedbackInputEl = document.getElementById('logFeedbackInput');
  var logInteractionSubmitBtnEl = document.getElementById('logInteractionSubmitBtn');
  var logInteractionStatusEl = document.getElementById('logInteractionStatus');

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

  function updateImageTranscriptToggleBtn() {
    var btn = document.getElementById('imageTranscriptToggleBtn');
    if (!btn) return;
    btn.classList.toggle('is-active', imageTranscriptVisible);
    btn.style.display = transcriptHiddenForImageUpload ? '' : 'none';
  }

  function updateTranscriptionVisibility() {
    if (!transcriptionEl) return;
    if (transcriptHiddenForImageUpload && !imageTranscriptVisible) {
      transcriptionEl.style.display = 'none';
    } else if (transcriptionEl.textContent) {
      transcriptionEl.style.display = '';
    } else {
      transcriptionEl.style.display = 'none';
    }
  }

  function setTranscription(text, opts) {
    if (!transcriptionEl) return;
    var options = opts || {};
    transcriptionEl.textContent = text || '';
    if (options.fromImageUpload) {
      transcriptHiddenForImageUpload = true;
      imageTranscriptVisible = false;
    } else if (text) {
      transcriptHiddenForImageUpload = false;
      imageTranscriptVisible = false;
    }
    updateImageTranscriptToggleBtn();
    updateTranscriptionVisibility();
  }

  function showUploadedImagePreview(file) {
    if (!file) return;
    showUploadedImagePreviewFromBlob(file, file.name || 'frame.jpg');
  }

  function showUploadedImagePreviewFromBlob(blob, filename) {
    var wrap = document.getElementById('uploadedImageWrap');
    var img = document.getElementById('uploadedSceneImg');
    if (!wrap || !img || !blob) return;
    if (uploadedImageObjectUrl) {
      URL.revokeObjectURL(uploadedImageObjectUrl);
    }
    uploadedImageObjectUrl = URL.createObjectURL(blob);
    img.src = uploadedImageObjectUrl;
    img.alt = filename ? 'Analyzed frame: ' + filename : 'Analyzed video frame';
    wrap.style.display = 'flex';
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

    setTranscription(trimmedText, options.fromImageUpload ? { fromImageUpload: true } : undefined);
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
        recordHistoryEntry(trimmedText, sequence, currentPulseSequence);
        if (window.composeAwaitingSceneImage) {
          updateProgress('Generating image', 85);
        } else {
          updateProgress('Complete', 100);
          setTimeout(hideProgress, 800);
        }
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

  function hideUploadedImagePreview() {
    var wrap = document.getElementById('uploadedImageWrap');
    var img = document.getElementById('uploadedSceneImg');
    if (wrap) wrap.style.display = 'none';
    if (img) img.removeAttribute('src');
    if (uploadedImageObjectUrl) {
      URL.revokeObjectURL(uploadedImageObjectUrl);
      uploadedImageObjectUrl = null;
    }
  }

  function getCachedGeneratedSceneImagePath() {
    var img = document.getElementById('generatedSceneImg');
    var wrap = document.getElementById('generatedSceneWrap');
    if (!img || !wrap || wrap.style.display === 'none' || !img.src) return null;
    if (img.src.indexOf(API_BASE) === 0) return img.src.slice(API_BASE.length);
    return null;
  }

  function saveVideoClipAnalysisResult(clipIndex, descriptionText) {
    var clip = videoClips[clipIndex];
    if (!clip || !currentSequence || !currentSequence.length) return;
    clip.analysisResult = {
      descriptionText: descriptionText || '',
      sequence: JSON.parse(JSON.stringify(currentSequence)),
      pulseSequence: currentPulseSequence ? JSON.parse(JSON.stringify(currentPulseSequence)) : null,
      sessionId: sessionId,
      sessionOriginalSentence: sessionOriginalSentence,
      sessionOriginalSequence: sessionOriginalSequence
        ? JSON.parse(JSON.stringify(sessionOriginalSequence))
        : null,
      sessionHistory: JSON.parse(JSON.stringify(sessionHistory)),
      isInFeedbackMode: isInFeedbackMode,
      generatedImageUrl: getCachedGeneratedSceneImagePath()
    };
  }

  function restoreVideoClipAnalysisResult(clip) {
    var result = clip && clip.analysisResult;
    if (!result || !result.sequence || !result.sequence.length) return false;

    cancelSceneImagePoll();
    window.composeAwaitingSceneImage = false;
    setTranscription(result.descriptionText || '', { fromImageUpload: true });
    sessionId = result.sessionId;
    sessionOriginalSentence = result.sessionOriginalSentence;
    sessionOriginalSequence = result.sessionOriginalSequence
      ? JSON.parse(JSON.stringify(result.sessionOriginalSequence))
      : null;
    sessionHistory = result.sessionHistory ? JSON.parse(JSON.stringify(result.sessionHistory)) : [];
    isInFeedbackMode = !!result.isInFeedbackMode;
    currentSequence = JSON.parse(JSON.stringify(result.sequence));
    currentPulseSequence = result.pulseSequence
      ? JSON.parse(JSON.stringify(result.pulseSequence))
      : null;
    renderProfile(currentSequence);
    showGeneratedSceneImage(result.generatedImageUrl || null);
    setStatus('Clip restored — using previous analysis and scent.');
    hideProgress();
    return true;
  }

  window.persistVideoClipSceneImageForSession = function (composeSessionId, relativeUrl) {
    if (!composeSessionId) return;
    for (var i = 0; i < videoClips.length; i++) {
      var cached = videoClips[i].analysisResult;
      if (cached && cached.sessionId === composeSessionId) {
        cached.generatedImageUrl = relativeUrl || null;
        if (i === videoClipIndex) {
          showGeneratedSceneImage(relativeUrl || null);
        }
        break;
      }
    }
  };

  function sendFrameForDescription(imageBlob, filename, opts) {
    var options = opts || {};
    if (options.hidePreview) {
      hideUploadedImagePreview();
    } else {
      showUploadedImagePreviewFromBlob(imageBlob, filename);
    }
    showProgress('Analyzing frame', 20);
    setStatus('Analyzing visual smell cues...');
    setTranscription('', { fromImageUpload: true });
    var form = new FormData();
    form.append('image', imageBlob, filename || 'frame.jpg');
    if (sessionId) form.append('session_id', sessionId);

    return fetch(API_BASE + '/describe_image', {
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
        return processInputText(text, { forceCompose: true, fromImageUpload: true }).then(function () {
          if (typeof options.clipIndex === 'number') {
            saveVideoClipAnalysisResult(options.clipIndex, text.trim());
          }
        });
      })
      .catch(function (err) {
        setStatus('Frame analysis failed: ' + (err.message || err), true);
        setTranscription('');
        hideProgress();
      });
  }

  function sendVideoFileForDescription(file, opts) {
    var options = opts || {};
    showProgress('Extracting frame', 25);
    setStatus('Server extracting mid-clip frame...');
    setTranscription('', { fromImageUpload: true });
    var form = new FormData();
    form.append('video', file, file.name || 'clip.mp4');
    if (sessionId) form.append('session_id', sessionId);

    return fetch(API_BASE + '/describe_video', { method: 'POST', body: form })
      .then(function (res) {
        if (!res.ok) return res.json().then(function (body) { throw new Error(body.detail || res.statusText); });
        return res.json();
      })
      .then(function (data) {
        var text = data.text || '';
        if (!text) throw new Error('No description returned');
        if (!isInFeedbackMode) renderProfile([]);
        return processInputText(text, { forceCompose: true, fromImageUpload: true }).then(function () {
          if (typeof options.clipIndex === 'number') {
            saveVideoClipAnalysisResult(options.clipIndex, text.trim());
          }
        });
      });
  }

  function sendImageForDescription(file) {
    clearVideoClipQueue();
    hideVideoClipPanel();
    sendFrameForDescription(file, file.name || 'upload.jpg');
  }

  bindImageUploadHandler(sendImageForDescription);

  var videoClips = [];
  var videoClipIndex = 0;
  var videoClipUrls = [];
  var videoClipAnalyzing = false;
  var videoClipLoadTimeout = null;
  var videoClipAnalyzeGeneration = 0;
  var hiddenVideoCaptureEl = null;
  var VIDEO_SERVER_FRAME_BYTES = 28 * 1024 * 1024;

  function getHiddenVideoCaptureElement() {
    if (!hiddenVideoCaptureEl) {
      hiddenVideoCaptureEl = document.createElement('video');
      hiddenVideoCaptureEl.setAttribute('playsinline', '');
      hiddenVideoCaptureEl.muted = true;
      hiddenVideoCaptureEl.preload = 'auto';
      hiddenVideoCaptureEl.setAttribute('aria-hidden', 'true');
      hiddenVideoCaptureEl.style.cssText =
        'position:fixed;width:1px;height:1px;opacity:0;pointer-events:none;left:-9999px;top:0';
      document.body.appendChild(hiddenVideoCaptureEl);
    }
    return hiddenVideoCaptureEl;
  }

  function resetHiddenVideoCaptureElement(video) {
    if (!video) return;
    try {
      video.pause();
    } catch (e) { /* ignore */ }
    video.removeAttribute('src');
    try {
      video.load();
    } catch (e2) { /* ignore */ }
  }

  function isVideoFile(file) {
    if (!file) return false;
    if (file.type && file.type.indexOf('video/') === 0) return true;
    var name = (file.name || '').toLowerCase();
    return /\.(mp4|webm|mov|m4v|mkv|avi)$/.test(name);
  }

  function hideVideoClipPanel() {
    var panel = document.getElementById('videoClipPanel');
    var player = document.getElementById('videoClipPlayer');
    if (player) {
      player.pause();
      player.removeAttribute('src');
      player.load();
    }
    if (panel) panel.style.display = 'none';
  }

  function showVideoClipPanel() {
    var panel = document.getElementById('videoClipPanel');
    if (panel) panel.style.display = 'flex';
  }

  function clearVideoClipQueue() {
    videoClips = [];
    videoClipIndex = 0;
    videoClipUrls.forEach(function (url) { URL.revokeObjectURL(url); });
    videoClipUrls = [];
    var counter = document.getElementById('videoClipCounter');
    if (counter) counter.textContent = '';
  }

  function updateVideoClipCounter() {
    var counter = document.getElementById('videoClipCounter');
    if (!counter) return;
    if (!videoClips.length) {
      counter.textContent = '';
      return;
    }
    counter.textContent = 'Clip ' + (videoClipIndex + 1) + ' / ' + videoClips.length;
  }

  function midFrameSampleTimes(video) {
    var d = video && video.duration;
    if (d && isFinite(d) && d > 0.15) {
      var mid = d / 2;
      var lo = 0.05;
      var hi = Math.max(lo, d - 0.05);
      return [
        mid,
        Math.max(lo, mid - 0.033),
        Math.min(hi, mid + 0.033),
        Math.max(lo, mid - 0.1),
        Math.min(hi, mid + 0.1)
      ];
    }
    return [0.5, 1, 2, 0.25];
  }

  function captureMidFrameFromVideo(video) {
    var sampleTimes = midFrameSampleTimes(video);
    var timeIdx = 0;

    return new Promise(function (resolve, reject) {
      if (!video || !video.videoWidth) {
        reject(new Error('Video not ready for frame capture'));
        return;
      }

      function tryNextTime() {
        if (timeIdx >= sampleTimes.length) {
          reject(new Error('Could not capture a frame from this clip'));
          return;
        }
        var target = sampleTimes[timeIdx++];

        function onSeeked() {
          video.removeEventListener('seeked', onSeeked);
          var canvas = document.createElement('canvas');
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          var ctx = canvas.getContext('2d');
          if (!ctx) {
            tryNextTime();
            return;
          }
          ctx.drawImage(video, 0, 0);
          canvas.toBlob(function (blob) {
            if (blob && blob.size > 400) {
              resolve(blob);
            } else {
              tryNextTime();
            }
          }, 'image/jpeg', 0.92);
        }

        video.addEventListener('seeked', onSeeked);
        try {
          video.currentTime = target;
        } catch (e) {
          video.removeEventListener('seeked', onSeeked);
          tryNextTime();
        }
      }

      tryNextTime();
    });
  }

  function captureMidFrameFromClipUrl(url) {
    var video = getHiddenVideoCaptureElement();
    return new Promise(function (resolve, reject) {
      var settled = false;

      function finish(err, blob) {
        if (settled) return;
        settled = true;
        video.removeEventListener('loadeddata', onReady);
        video.removeEventListener('error', onError);
        resetHiddenVideoCaptureElement(video);
        if (err) reject(err);
        else resolve(blob);
      }

      function onError() {
        finish(new Error('Could not load video for frame capture'));
      }

      function onReady() {
        if (!video.videoWidth) return;
        captureMidFrameFromVideo(video)
          .then(function (blob) { finish(null, blob); })
          .catch(function (err) { finish(err); });
      }

      resetHiddenVideoCaptureElement(video);
      video.addEventListener('error', onError);
      video.addEventListener('loadeddata', onReady);
      video.src = url;
      video.load();
    });
  }

  function analyzeCurrentVideoClip() {
    if (!videoClips.length || videoClipAnalyzing) return;
    var clipIndex = videoClipIndex;
    var clip = videoClips[clipIndex];
    if (!clip || !clip.url) return;
    if (clip.analysisResult && clip.analysisResult.sequence && clip.analysisResult.sequence.length) {
      return;
    }

    videoClipAnalyzing = true;
    var generation = ++videoClipAnalyzeGeneration;
    setStatus('Analyzing clip ' + (clipIndex + 1) + ' in the background…');

    captureMidFrameFromClipUrl(clip.url)
      .then(function (blob) {
        if (generation !== videoClipAnalyzeGeneration || clipIndex !== videoClipIndex) return;
        var frameName = (clip.name || 'clip').replace(/\.[^.]+$/, '') + '_frame.jpg';
        return sendFrameForDescription(blob, frameName, {
          hidePreview: true,
          clipIndex: clipIndex
        });
      })
      .catch(function (err) {
        if (generation !== videoClipAnalyzeGeneration || clipIndex !== videoClipIndex) return;
        return sendVideoFileForDescription(clip.file, { clipIndex: clipIndex }).catch(function (serverErr) {
          setStatus(
            'Video frame capture failed: ' + (err.message || err) +
            (serverErr ? ' (' + serverErr.message + ')' : ''),
            true
          );
          hideProgress();
        });
      })
      .finally(function () {
        if (generation === videoClipAnalyzeGeneration) {
          videoClipAnalyzing = false;
        }
      });
  }

  function loadVideoClip(index) {
    var player = document.getElementById('videoClipPlayer');
    if (!player || !videoClips.length) return;
    if (index < 0 || index >= videoClips.length) return;

    if (videoClipLoadTimeout) {
      clearTimeout(videoClipLoadTimeout);
      videoClipLoadTimeout = null;
    }

    videoClipIndex = index;
    updateVideoClipCounter();

    var clip = videoClips[videoClipIndex];
    showProgress('Loading video clip', 12);
    setStatus('Loading clip ' + (videoClipIndex + 1) + '…');

    if (clip.file && clip.file.size >= VIDEO_SERVER_FRAME_BYTES) {
      showVideoClipPanel();
      if (restoreVideoClipAnalysisResult(clip)) {
        return;
      }
      setStatus('Large clip — extracting frame on server…');
      sendVideoFileForDescription(clip.file, { clipIndex: videoClipIndex }).catch(function (err) {
        setStatus('Video failed: ' + (err.message || err), true);
        hideProgress();
      });
      return;
    }

    player.onerror = function () {
      if (clip.analysisResult && clip.analysisResult.sequence) return;
      setStatus('Browser could not play this clip; trying server extraction…', true);
      sendVideoFileForDescription(clip.file, { clipIndex: videoClipIndex }).catch(function (err) {
        setStatus('Video failed: ' + (err.message || err), true);
        hideProgress();
      });
    };

    showVideoClipPanel();
    player.src = clip.url;
    player.load();

    var started = false;
    var onReady = function () {
      if (started) return;
      started = true;
      player.removeEventListener('loadedmetadata', onReady);
      player.removeEventListener('loadeddata', onReady);
      if (videoClipLoadTimeout) {
        clearTimeout(videoClipLoadTimeout);
        videoClipLoadTimeout = null;
      }
      player.currentTime = 0;
      var playPromise = player.play();
      if (playPromise && playPromise.catch) {
        playPromise.catch(function () { /* autoplay blocked — user can press play */ });
      }
      if (restoreVideoClipAnalysisResult(clip)) {
        return;
      }
      updateProgress('Extracting frame', 35);
      analyzeCurrentVideoClip();
    };

    player.addEventListener('loadedmetadata', onReady);
    player.addEventListener('loadeddata', onReady);

    videoClipLoadTimeout = setTimeout(function () {
      videoClipLoadTimeout = null;
      if (clip.analysisResult && clip.analysisResult.sequence) return;
      setStatus('Clip is taking long to load; trying server extraction…', true);
      sendVideoFileForDescription(clip.file, { clipIndex: videoClipIndex }).catch(function (err) {
        setStatus('Video failed: ' + (err.message || err), true);
        hideProgress();
      });
    }, 45000);
  }

  function enqueueVideoFiles(fileList) {
    if (!fileList || !fileList.length) return;
    showProgress('Reading videos', 8);
    setStatus('Adding video clips…');
    var controls = document.getElementById('frequencyControls');
    if (controls && controls.scrollIntoView) {
      controls.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    clearVideoClipQueue();
    hideVideoClipPanel();
    hideUploadedImagePreview();

    for (var i = 0; i < fileList.length; i++) {
      var file = fileList[i];
      if (!isVideoFile(file)) continue;
      var url = URL.createObjectURL(file);
      videoClipUrls.push(url);
      videoClips.push({ file: file, url: url, name: file.name || 'clip.mp4' });
    }

    if (!videoClips.length) {
      setStatus('No supported video files (try MP4, MOV, or WebM).', true);
      hideProgress();
      return;
    }

    showVideoClipPanel();
    var panel = document.getElementById('videoClipPanel');
    if (panel && panel.scrollIntoView) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    if (!isInFeedbackMode) {
      renderProfile([]);
    }
    loadVideoClip(0);
  }

  function bindVideoUploadHandler() {
    var videoInputEl = document.getElementById('frequencyVideoInput');
    if (!videoInputEl || videoInputEl.dataset.bound === 'true') return;
    videoInputEl.dataset.bound = 'true';
    videoInputEl.addEventListener('change', function () {
      var files = Array.from(videoInputEl.files || []);
      videoInputEl.value = '';
      enqueueVideoFiles(files);
    });

    var prevBtn = document.getElementById('videoClipPrevBtn');
    var nextBtn = document.getElementById('videoClipNextBtn');
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        if (!videoClips.length) return;
        var nextIndex = videoClipIndex - 1;
        if (nextIndex < 0) nextIndex = videoClips.length - 1;
        loadVideoClip(nextIndex);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        if (!videoClips.length) return;
        var nextIndex = (videoClipIndex + 1) % videoClips.length;
        loadVideoClip(nextIndex);
      });
    }
  }

  bindVideoUploadHandler();

  if (recordBtn) recordBtn.addEventListener('click', function (e) {
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

  // Textual feedback: an alternate input path for the SAME feedback loop
  // that voice recording feeds (via processInputText -> feedbackScent when
  // isInFeedbackMode is true) -- just typed instead of spoken/transcribed.
  // Deliberately does NOT pass forceCompose, so it gets exactly the same
  // downstream treatment as transcribed voice feedback: routes to
  // feedbackScent() if already in feedback mode, or starts a fresh
  // composition otherwise, identical to what a transcribed recording would
  // do at the same point in the session.
  if (textualFeedbackToggleBtnEl && textualFeedbackRowEl) {
    textualFeedbackToggleBtnEl.addEventListener('click', function () {
      var isHidden = textualFeedbackRowEl.style.display === 'none';
      textualFeedbackRowEl.style.display = isHidden ? 'block' : 'none';
      textualFeedbackToggleBtnEl.classList.toggle('is-active', isHidden);
      if (isHidden && textualFeedbackInputEl) textualFeedbackInputEl.focus();
    });
  }

  if (durationToggleBtnEl && durationRowEl) {
    durationToggleBtnEl.addEventListener('click', function () {
      var isHidden = durationRowEl.style.display === 'none';
      durationRowEl.style.display = isHidden ? 'block' : 'none';
      durationToggleBtnEl.classList.toggle('is-active', isHidden);
    });
  }

  if (logInteractionToggleBtnEl && logInteractionRowEl) {
    logInteractionToggleBtnEl.addEventListener('click', function () {
      var isHidden = logInteractionRowEl.style.display === 'none';
      logInteractionRowEl.style.display = isHidden ? 'block' : 'none';
      logInteractionToggleBtnEl.classList.toggle('is-active', isHidden);
      if (isHidden && logSimilarityInputEl) logSimilarityInputEl.focus();
    });
  }

  if (logInteractionSubmitBtnEl) {
    logInteractionSubmitBtnEl.addEventListener('click', function () {
      submitLogInteraction();
    });
  }

  if (textualFeedbackSubmitBtnEl && textualFeedbackInputEl) {
    textualFeedbackSubmitBtnEl.addEventListener('click', function () {
      var feedbackText = (textualFeedbackInputEl.value || '').trim();
      if (!feedbackText) {
        setStatus('Please enter feedback text before submitting.', true);
        return;
      }
      showProgress(isInFeedbackMode ? 'Refining scent' : 'Composing scent', 25);
      setStatus('');
      processInputText(feedbackText).then(function () {
        textualFeedbackInputEl.value = '';
      }).catch(function (err) {
        setStatus('Textual feedback failed: ' + (err.message || err), true);
        hideProgress();
      });
    });

    textualFeedbackInputEl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        textualFeedbackSubmitBtnEl.click();
      }
    });
  }

  var imageTranscriptToggleBtnEl = document.getElementById('imageTranscriptToggleBtn');
  if (imageTranscriptToggleBtnEl) {
    imageTranscriptToggleBtnEl.addEventListener('click', function () {
      if (!transcriptHiddenForImageUpload) return;
      imageTranscriptVisible = !imageTranscriptVisible;
      updateImageTranscriptToggleBtn();
      updateTranscriptionVisibility();
    });
    updateImageTranscriptToggleBtn();
  }

  window.aromaFrequencyProgress = {
    update: updateProgress,
    show: showProgress,
    hide: hideProgress,
    finishComplete: function () {
      updateProgress('Complete', 100);
      setTimeout(hideProgress, 800);
    },
  };
})();

/*
Below is the original code for scent composition from death_sentence/script.js, now modified to take in the transcription and composed a scent sequence based on the transcription. 
*/

// Base notes are loaded from the cartridge API; fallback to scent_classification.json
const baseNotes = [];
let scentsData = {};
let currentSequence = null; // Store the last generated sequence for playback

// Feedback loop session state
let sessionOriginalSentence = null;
let sessionOriginalSequence = null;
let sessionHistory = []; // Array of {feedback_text, changes_made, resulting_sequence}
let sessionId = null;
let isInFeedbackMode = false;

// Load the fixed 12-odorant catalog (slot locations for device playback)
function loadActiveCartridgeScents() {
  return fetch(API_BASE + '/cartridge/active')
    .then(function (res) {
      if (!res.ok) throw new Error('Cartridge API unavailable');
      return res.json();
    })
    .then(function (data) {
      scentsData = data.scents || {};
      const names = Object.keys(scentsData);
      baseNotes.splice(0, baseNotes.length, ...names);
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

// Interaction logging (the "Log" button + "Open Log Sheet") depends on a
// private Google Sheet + Apps Script deployment specific to this
// installation (see aromagen/production_logging/apps_script/) -- someone
// cloning the repo fresh won't have that configured, and clicking "Log"
// would otherwise surface a raw "Interaction logging is not configured"
// backend error. Check on load and hide those controls entirely rather
// than let an unrelated feature look broken to a new user.
function applyInteractionLoggingAvailability(configured) {
  ['logInteractionToggleBtn', 'openLogSheetBtn'].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.style.display = configured ? '' : 'none';
  });
}

fetch(API_BASE + '/health')
  .then(function (r) { return r.ok ? r.json() : { interaction_logging_configured: false }; })
  .then(function (data) { applyInteractionLoggingAvailability(!!data.interaction_logging_configured); })
  .catch(function () { applyInteractionLoggingAvailability(false); });

let currentPulseSequence = null; // Interleaved hardware pulse train from the last compose/feedback call

function handleComposeResponse(data) {
  if (data.session_id) sessionId = data.session_id;
  console.log('[Compose] Justification:', data.justification);
  if (data.rag_metadata) {
    console.log('[Compose] RAG:', data.rag_metadata);
  }
  console.log('[Compose] Validation:', data.validation_reasoning, 'removed:', data.removed_scents);
  if (data.compatibility_warnings && data.compatibility_warnings.length) {
    console.warn('[Compose] Compatibility warnings:', data.compatibility_warnings);
  }
  console.log('[Compose] Pulse sequence:', data.pulse_sequence);
  currentPulseSequence = data.pulse_sequence || null;
  window.composeAwaitingSceneImage = false;
  if (data.generated_image_url) {
    showGeneratedSceneImage(data.generated_image_url);
  } else if (data.generated_image_status === 'pending' && data.session_id && isSceneImageEnabled()) {
    window.composeAwaitingSceneImage = true;
    beginSceneImagePoll(data.session_id);
  } else if (data.generated_image_status === 'skipped' || !isSceneImageEnabled()) {
    showGeneratedSceneImage(null);
  }
  return (data.validated_sequence && data.validated_sequence.length > 0)
    ? data.validated_sequence
    : (data.scent_sequence || null);
}

var sceneImagePollTimer = null;

function cancelSceneImagePoll() {
  if (sceneImagePollTimer) {
    clearTimeout(sceneImagePollTimer);
    sceneImagePollTimer = null;
  }
}

function showGeneratedSceneImage(relativeUrl) {
  var wrap = document.getElementById('generatedSceneWrap');
  var img = document.getElementById('generatedSceneImg');
  if (!wrap || !img) return;
  if (!relativeUrl) {
    wrap.style.display = 'none';
    img.removeAttribute('src');
    img.alt = '';
    return;
  }
  img.src = API_BASE + relativeUrl;
  img.alt = 'Generated scene for this smell request';
  wrap.style.display = 'flex';
}

function beginSceneImagePoll(sessionId) {
  cancelSceneImagePoll();
  showGeneratedSceneImage(null);
  var progress = window.aromaFrequencyProgress;
  if (progress) {
    progress.update('Generating image', 85);
  }

  var attempts = 0;
  var maxAttempts = 60;

  function poll() {
    attempts += 1;
    if (progress) {
      var pct = Math.min(95, 85 + Math.floor(attempts * 1.5));
      progress.update('Generating image', pct);
    }
    fetch(API_BASE + '/generated_image/' + encodeURIComponent(sessionId))
      .then(function (res) { return res.json(); })
      .then(function (body) {
        if (body.status === 'ready' && body.url) {
          cancelSceneImagePoll();
          window.composeAwaitingSceneImage = false;
          showGeneratedSceneImage(body.url);
          if (typeof window.persistVideoClipSceneImageForSession === 'function') {
            window.persistVideoClipSceneImageForSession(sessionId, body.url);
          }
          if (progress) progress.finishComplete();
          return;
        }
        if (body.status === 'failed' || body.status === 'not_found' || attempts >= maxAttempts) {
          cancelSceneImagePoll();
          window.composeAwaitingSceneImage = false;
          if (progress) progress.finishComplete();
          return;
        }
        sceneImagePollTimer = setTimeout(poll, 2000);
      })
      .catch(function () {
        if (attempts >= maxAttempts) {
          window.composeAwaitingSceneImage = false;
          if (progress) progress.finishComplete();
          return;
        }
        sceneImagePollTimer = setTimeout(poll, 3000);
      });
  }
  poll();
}

async function composeScent(sentence) {
  try {
    const res = await fetch(API_BASE + '/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sentence: sentence,
        include_generated_image: isSceneImageEnabled()
      })
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
    const effectiveSequence = (data.validated_sequence && data.validated_sequence.length > 0)
      ? data.validated_sequence
      : (data.scent_sequence || null);
    if (effectiveSequence) {
      if (data.session_id) sessionId = data.session_id;
      sessionHistory.push({
        feedback_text: feedbackText,
        changes_made: data.changes_made || '',
        resulting_sequence: effectiveSequence
      });
    }
    console.log('[Feedback] Justification:', data.justification);
    console.log('[Feedback] Changes made:', data.changes_made);
    console.log('[Feedback] Validation:', data.validation_reasoning, 'removed:', data.removed_scents);
    if (data.compatibility_warnings && data.compatibility_warnings.length) {
      console.warn('[Feedback] Compatibility warnings:', data.compatibility_warnings);
    }
    console.log('[Feedback] Pulse sequence:', data.pulse_sequence);
    currentPulseSequence = data.pulse_sequence || null;
    return effectiveSequence;
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

// ---- Generation history (client-side, localStorage) ----
// Every successful compose/feedback call (see processInputText's success
// branch) gets recorded here: the prompt/feedback text that produced it,
// the full resulting recipe (base odorants + ratios), and the hardware
// pulse train if one was returned, so a restored entry can be played back
// with the exact same timing as the original generation. Capped to the
// most recent HISTORY_LIMIT entries, newest first.
const HISTORY_STORAGE_KEY = 'aromagen_generation_history';
const HISTORY_LIMIT = 50;

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    console.warn('Could not read generation history from localStorage', e);
    return [];
  }
}

function saveHistory(entries) {
  try {
    localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(entries));
  } catch (e) {
    console.warn('Could not save generation history to localStorage', e);
  }
}

function recordHistoryEntry(prompt, sequence, pulseSequence) {
  if (!prompt || !sequence || !sequence.length) return;
  const entries = loadHistory();
  entries.unshift({
    id: Date.now() + '-' + Math.random().toString(36).slice(2, 8),
    prompt: prompt,
    sequence: sequence,
    pulseSequence: pulseSequence || null,
    timestamp: new Date().toISOString()
  });
  saveHistory(entries.slice(0, HISTORY_LIMIT));
}

function formatHistoryTimestamp(iso) {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
    });
  } catch (e) {
    return '';
  }
}

function summarizeRecipe(sequence) {
  const total = sequence.reduce((sum, item) => {
    return sum + (typeof item.ratio === 'number' && !Number.isNaN(item.ratio) ? item.ratio : 0);
  }, 0);
  return sequence.map(function (item) {
    const hasRatio = typeof item.ratio === 'number' && !Number.isNaN(item.ratio) && total > 0;
    const pct = hasRatio ? Math.round((item.ratio / total) * 100) + '%' : '';
    return pct ? (item.scent_name || '') + ' ' + pct : (item.scent_name || '');
  }).join(', ');
}

function renderHistoryList() {
  const listEl = document.getElementById('historyList');
  if (!listEl) return;
  const entries = loadHistory();

  if (!entries.length) {
    listEl.innerHTML = '<p class="history-empty">No generations yet. Compose or refine a scent to start building history.</p>';
    return;
  }

  listEl.innerHTML = entries.map(function (entry) {
    const promptHtml = escapeHtmlText(entry.prompt || '');
    const recipeHtml = escapeHtmlText(summarizeRecipe(entry.sequence || []));
    const timeHtml = escapeHtmlText(formatHistoryTimestamp(entry.timestamp));
    return '<button type="button" class="history-entry" onclick="restoreHistoryEntry(\'' + entry.id + '\')">' +
      '<p class="history-entry-prompt">' + promptHtml + '</p>' +
      '<p class="history-entry-recipe">' + recipeHtml + '</p>' +
      '<p class="history-entry-meta">' + timeHtml + '</p>' +
      '</button>';
  }).join('') +
    '<button type="button" class="history-clear-btn" onclick="clearHistory()">Clear history</button>';
}

function escapeHtmlText(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function toggleHistoryPanel() {
  const panel = document.getElementById('historyPanel');
  if (!panel) return;
  if (panel.classList.contains('open')) {
    closeHistoryPanel();
  } else {
    openHistoryPanel();
  }
}

function openHistoryPanel() {
  const panel = document.getElementById('historyPanel');
  const backdrop = document.getElementById('historyBackdrop');
  renderHistoryList();
  if (panel) { panel.classList.add('open'); panel.setAttribute('aria-hidden', 'false'); }
  if (backdrop) backdrop.classList.add('open');
}

function closeHistoryPanel() {
  const panel = document.getElementById('historyPanel');
  const backdrop = document.getElementById('historyBackdrop');
  if (panel) { panel.classList.remove('open'); panel.setAttribute('aria-hidden', 'true'); }
  if (backdrop) backdrop.classList.remove('open');
}

function clearHistory() {
  saveHistory([]);
  renderHistoryList();
}

/**
 * Loads a past generation back into the editor as the CURRENT generation --
 * updates the prompt display and recipe (nodes on the wheel), and restores
 * the exact hardware pulse train if one was saved with the entry, so
 * pressing Play later reproduces the original timing. Does NOT call
 * compose/feedback again and does NOT play anything: playback stays a
 * separate, explicit action (the Play button), same as every other
 * generation path in this app.
 */
function restoreHistoryEntry(id) {
  const entries = loadHistory();
  const entry = entries.find(function (e) { return e.id === id; });
  if (!entry) return;

  sessionHistory = [];
  sessionOriginalSentence = entry.prompt;
  sessionOriginalSequence = entry.sequence;
  isInFeedbackMode = true;
  currentSequence = entry.sequence;
  currentPulseSequence = entry.pulseSequence || null;

  const transcriptionEl = document.getElementById('frequencyTranscriptionText');
  if (transcriptionEl) transcriptionEl.textContent = entry.prompt;
  const statusEl = document.getElementById('frequencyTranscriptionStatus');
  if (statusEl) {
    statusEl.textContent = 'Loaded from history — press Play to release this scent.';
    statusEl.style.color = 'rgba(255, 255, 255, 0.5)';
  }

  renderProfile(entry.sequence);
  closeHistoryPanel();
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

  const visible = sequence.slice(0, 8);
  // Normalize displayed percentages to the visible set so they sum to 100% even
  // after the validation layer has dropped some odorants from the original ratios.
  const ratioTotal = visible.reduce((sum, item) => {
    return sum + (typeof item.ratio === 'number' && !Number.isNaN(item.ratio) ? item.ratio : 0);
  }, 0);

  visible.forEach((item, i) => {
    const node = nodes[i];
    if (!node) return;
    const label = node.querySelector('.node-label');
    console.log(item.scent_name);
    if (label) {
      const hasRatio = typeof item.ratio === 'number' && !Number.isNaN(item.ratio) && ratioTotal > 0;
      const pct = hasRatio ? Math.round((item.ratio / ratioTotal) * 100) + '%' : '';
      label.textContent = pct ? `${item.scent_name || ''} · ${pct}` : (item.scent_name || '');
    }

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

  // Refresh the catalog so slot locations are current
  try {
    await loadActiveCartridgeScents();
  } catch (e) {
    console.warn('Could not refresh cartridge scents', e);
  }

  // A manual duration override (from the hidden "Duration" field) cycles
  // through each scent in the current ratio at a fixed X-second duration
  // instead of the backend's interleaved short-pulse train.
  const durationOverrideInputEl = document.getElementById('durationOverrideInput');
  const durationOverrideRaw = durationOverrideInputEl ? durationOverrideInputEl.value : '';
  const durationOverride = durationOverrideRaw !== '' ? parseFloat(durationOverrideRaw) : NaN;
  const hasDurationOverride = !isNaN(durationOverride) && durationOverride > 0;

  // Prefer the interleaved hardware pulse train (short repeated rounds meant to
  // encourage perceptual blending) over the raw conceptual sequence; fall back
  // if the backend didn't return one. A duration override always uses the raw
  // ratio sequence (one entry per scent) rather than the pulse train.
  const sourceSequence = hasDurationOverride
    ? currentSequence
    : (currentPulseSequence && currentPulseSequence.length > 0)
      ? currentPulseSequence
      : currentSequence;

  // Convert scent names to scent_ids using the location field, skipping unknown scents
  const bleSequence = [];
  for (const item of sourceSequence) {
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
    bleSequence.push({ scent_id: locId, duration: hasDurationOverride ? durationOverride : item.scent_duration });
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

(function initSceneImageToggle() {
  var btn = document.getElementById('sceneImageToggleBtn');
  if (!btn) return;
  setSceneImageEnabled(isSceneImageEnabled());
  btn.addEventListener('click', function () {
    setSceneImageEnabled(!isSceneImageEnabled());
  });
})();
