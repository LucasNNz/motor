const healthBadge = document.getElementById('healthBadge');
const systemBadge = document.getElementById('systemBadge');
const singlePrompt = document.getElementById('singlePrompt');
const singleBackend = document.getElementById('singleBackend');
const singleEngineUrl = document.getElementById('singleEngineUrl');
const singleWidth = document.getElementById('singleWidth');
const singleHeight = document.getElementById('singleHeight');
const singleSteps = document.getElementById('singleSteps');
const generateOneBtn = document.getElementById('generateOneBtn');
const singlePreview = document.getElementById('singlePreview');
const singleMeta = document.getElementById('singleMeta');

const batchText = document.getElementById('batchText');
const batchBackend = document.getElementById('batchBackend');
const batchEngineUrl = document.getElementById('batchEngineUrl');
const batchWidth = document.getElementById('batchWidth');
const batchHeight = document.getElementById('batchHeight');
const batchSteps = document.getElementById('batchSteps');
const startBatchBtn = document.getElementById('startBatchBtn');
const cancelBatchBtn = document.getElementById('cancelBatchBtn');
const downloadZipLink = document.getElementById('downloadZipLink');
const batchSummary = document.getElementById('batchSummary');
const queueBody = document.getElementById('queueBody');

let currentJobId = null;
let pollTimer = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) return response.json();
  return response;
}

async function refreshHealth() {
  try {
    const [health, system] = await Promise.all([api('/api/health'), api('/api/system')]);
    healthBadge.textContent = `Motor online · ${health.jobs} job(s)`;
    const txt = [];
    if (system.cuda_available) txt.push(`CUDA: ${system.cuda_device_name}`);
    else if (system.mps_available) txt.push('MPS disponível');
    else txt.push('Sem CUDA neste ambiente');
    txt.push(`backend sugerido: ${system.recommended_backend}`);
    if (!system.diffusers_installed) txt.push('diffusers ausente');
    systemBadge.textContent = txt.join(' · ');
  } catch (err) {
    healthBadge.textContent = 'Motor offline';
    systemBadge.textContent = '';
  }
}

function formatMs(value) {
  if (!value && value !== 0) return '-';
  return `${(value / 1000).toFixed(2)}s`;
}

function renderQueue(items, jobId) {
  queueBody.innerHTML = '';
  for (const item of items) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.id}</td>
      <td class="status-${item.status}">${item.status}</td>
      <td>${formatMs(item.duration_ms)}</td>
      <td>${item.output_file ? `<a href="/api/batch/${jobId}/image/${item.output_file}" target="_blank">${item.output_file}</a>` : (item.error || '-')}</td>
    `;
    queueBody.appendChild(tr);
  }
}

function updateDownloadLink(jobId, ready) {
  if (ready) {
    downloadZipLink.classList.remove('disabled');
    downloadZipLink.href = `/api/batch/${jobId}/zip`;
  } else {
    downloadZipLink.classList.add('disabled');
    downloadZipLink.href = '#';
  }
}

async function pollBatchStatus() {
  if (!currentJobId) return;
  try {
    const data = await api(`/api/batch/${currentJobId}`);
    batchSummary.textContent = `Job ${data.job_id} · ${data.status} · ${data.completed}/${data.total} concluídas · ${data.failed} falhas · backend ${data.backend}`;
    renderQueue(data.items, data.job_id);
    updateDownloadLink(data.job_id, data.zip_ready);
    if (['done', 'error', 'cancelled'].includes(data.status)) {
      clearInterval(pollTimer);
      pollTimer = null;
      await refreshHealth();
    }
  } catch (err) {
    batchSummary.textContent = `Erro ao consultar lote: ${err.message}`;
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

generateOneBtn.addEventListener('click', async () => {
  const prompt = singlePrompt.value.trim();
  if (!prompt) {
    singleMeta.textContent = 'Digite um prompt.';
    return;
  }
  singleMeta.textContent = 'Gerando...';
  try {
    const data = await api('/api/generate', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        backend: singleBackend.value,
        engine_url: singleEngineUrl.value.trim() || null,
        width: Number(singleWidth.value),
        height: Number(singleHeight.value),
        steps: Number(singleSteps.value),
      }),
    });
    singlePreview.src = `data:image/png;base64,${data.image_base64}`;
    singleMeta.textContent = `Backend ${data.backend} · ${formatMs(data.duration_ms)}`;
  } catch (err) {
    singleMeta.textContent = `Erro: ${err.message}`;
  }
});

startBatchBtn.addEventListener('click', async () => {
  const text = batchText.value.trim();
  if (!text) {
    batchSummary.textContent = 'Cole os prompts do lote.';
    return;
  }
  batchSummary.textContent = 'Iniciando lote...';
  queueBody.innerHTML = '';
  updateDownloadLink('', false);
  try {
    const data = await api('/api/batch', {
      method: 'POST',
      body: JSON.stringify({
        text,
        backend: batchBackend.value,
        engine_url: batchEngineUrl.value.trim() || null,
        width: Number(batchWidth.value),
        height: Number(batchHeight.value),
        steps: Number(batchSteps.value),
      }),
    });
    currentJobId = data.job_id;
    renderQueue(data.items, data.job_id);
    batchSummary.textContent = `Job ${data.job_id} iniciado · ${data.total} itens · backend ${data.backend}`;
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollBatchStatus, 1200);
    pollBatchStatus();
    await refreshHealth();
  } catch (err) {
    batchSummary.textContent = `Erro: ${err.message}`;
  }
});

cancelBatchBtn.addEventListener('click', async () => {
  if (!currentJobId) return;
  try {
    await api(`/api/batch/${currentJobId}/cancel`, { method: 'POST' });
    batchSummary.textContent = `Cancelamento solicitado para ${currentJobId}`;
  } catch (err) {
    batchSummary.textContent = `Erro ao cancelar: ${err.message}`;
  }
});

refreshHealth();
setInterval(refreshHealth, 5000);
