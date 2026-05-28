/* ComicFX — upload, preview, poll, download */

// ── DOM refs ────────────────────────────────────────────────
const zone        = document.getElementById('upload-zone');
const fileInput   = document.getElementById('file-input');
const uploadPanel = document.getElementById('upload-panel');

const progressSection = document.getElementById('progress-section');
const progressFill    = document.getElementById('progress-fill');
const progressPct     = document.getElementById('progress-pct');
const progressMsg     = document.getElementById('progress-msg');

const resultsSection = document.getElementById('results-section');
const originalBox    = document.getElementById('original-box');
const resultBox      = document.getElementById('result-box');
const spinner        = document.getElementById('spinner');
const downloadBtn    = document.getElementById('download-btn');
const resetBtn       = document.getElementById('reset-btn');

// Technique options
const optCrosshatch = document.getElementById('opt-crosshatch');
const optContour    = document.getElementById('opt-contour');
const optColors     = document.getElementById('opt-colors');
const paletteLabel  = document.getElementById('palette-label');
const cardHatch     = document.getElementById('card-hatch');
const cardContour   = document.getElementById('card-contour');

let pollTimer   = null;
let originalUrl = null;

// ── Options interactivity ───────────────────────────────────

optColors.addEventListener('input', () => {
  paletteLabel.textContent = optColors.value + ' colours';
});

// ── Drag-and-drop wiring ────────────────────────────────────

zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('over'); });
zone.addEventListener('dragleave', ()  => zone.classList.remove('over'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('over');
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
zone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

// ── Core upload flow ────────────────────────────────────────

async function handleFile(file) {
  // Cancel any running job from a rapid double-drop
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }

  // Detect video by MIME type AND extension (MKV often has empty MIME)
  const isVideo = file.type.startsWith('video/') ||
                  /\.(mp4|mov|avi|mkv)$/i.test(file.name);

  showOriginal(file, isVideo);
  resultsSection.classList.remove('hidden');
  spinner.classList.remove('hidden');
  downloadBtn.classList.add('hidden');

  uploadPanel.style.opacity = '.45';
  uploadPanel.style.pointerEvents = 'none';

  // Build form data including technique options
  const form = new FormData();
  form.append('file', file);
  form.append('cross_hatch',      optCrosshatch.checked);
  form.append('variable_contour', optContour.checked);
  form.append('n_colors',         optColors.value);

  let data;
  try {
    const res = await fetch('/upload', { method: 'POST', body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    data = await res.json();
  } catch (err) {
    alert('Upload failed: ' + err.message);
    resetUI();
    return;
  }

  const { job_id: jobId } = data;

  if (isVideo) {
    progressSection.classList.remove('hidden');
    pollProgress(jobId, isVideo);
  } else {
    renderResult(jobId, isVideo);
  }
}

// ── Polling (video) ─────────────────────────────────────────

function pollProgress(jobId, isVideo) {
  const msgs = [
    'Clarifying value masses…',        // de Reyna
    'Quantising colour palette…',
    'Applying vintage grade…',
    'Stamping cross-hatch shadows…',   // Probyn
    'Drawing pure contour lines…',     // Edwards
    'Adding Ben-Day halftone dots…',
    'Almost there — hang tight…',
  ];

  pollTimer = setInterval(async () => {
    let data;
    try {
      const res = await fetch(`/status/${jobId}`);
      if (!res.ok) return;
      data = await res.json();
    } catch (_) { return; }

    const pct = Math.min(100, Math.max(0, data.progress ?? 0));
    progressFill.style.width = pct + '%';
    progressPct.textContent  = pct + '%';
    progressMsg.textContent  = msgs[Math.floor(pct / (100 / msgs.length))] ?? msgs[msgs.length - 1];

    if (data.status === 'done') {
      clearInterval(pollTimer); pollTimer = null;
      progressSection.classList.add('hidden');
      renderResult(jobId, isVideo);
    } else if (data.status === 'error') {
      clearInterval(pollTimer); pollTimer = null;
      progressSection.classList.add('hidden');
      resultBox.innerHTML = `<p style="color:red;padding:20px;font-weight:bold">
        Processing failed:<br>${data.error ?? 'Unknown error'}</p>`;
    }
  }, 1000);
}

// ── Rendering helpers ───────────────────────────────────────

function showOriginal(file, isVideo) {
  if (originalUrl) { URL.revokeObjectURL(originalUrl); }
  originalUrl = URL.createObjectURL(file);
  originalBox.innerHTML = '';

  if (isVideo) {
    const v = document.createElement('video');
    v.src = originalUrl; v.controls = true; v.muted = true;
    v.loop = true; v.autoplay = true;
    originalBox.appendChild(v);
  } else {
    const img = document.createElement('img');
    img.src = originalUrl; img.alt = 'Original';
    originalBox.appendChild(img);
  }
}

function renderResult(jobId, isVideo) {
  spinner.classList.add('hidden');
  resultBox.innerHTML = '';
  const src = `/download/${jobId}?t=${Date.now()}`;

  if (isVideo) {
    const v = document.createElement('video');
    v.src = src; v.controls = true; v.muted = true;
    v.loop = true; v.autoplay = true;
    resultBox.appendChild(v);
  } else {
    const img = document.createElement('img');
    img.src = src; img.alt = 'Comic Style';
    resultBox.appendChild(img);
  }

  downloadBtn.classList.remove('hidden');
  downloadBtn.onclick = () => {
    const a = document.createElement('a');
    a.href = `/download/${jobId}`;
    a.download = isVideo ? 'comicfx.mp4' : 'comicfx.png';
    a.click();
  };
}

// ── Reset ───────────────────────────────────────────────────

resetBtn.addEventListener('click', resetUI);

function resetUI() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  if (originalUrl) { URL.revokeObjectURL(originalUrl); originalUrl = null; }

  uploadPanel.style.opacity = '1';
  uploadPanel.style.pointerEvents = 'auto';

  progressSection.classList.add('hidden');
  progressFill.style.width = '0%';
  progressPct.textContent  = '0%';

  resultsSection.classList.add('hidden');
  originalBox.innerHTML = '';
  resultBox.innerHTML   = '';
  spinner.classList.remove('hidden');
  downloadBtn.classList.add('hidden');

  fileInput.value = '';
}
