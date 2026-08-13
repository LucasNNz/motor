const $ = (id) => document.getElementById(id);

const healthBadge = $('healthBadge');
const systemBadge = $('systemBadge');
const bankAssets = $('bankAssets');
const bankBreakdown = $('bankBreakdown');
const composerMessage = $('composerMessage');
const refreshComposerBtn = $('refreshComposerBtn');
const rebuildComposerBtn = $('rebuildComposerBtn');

const singlePrompt = $('singlePrompt');
const singleBackend = $('singleBackend');
const singleEngineUrl = $('singleEngineUrl');
const singleWidth = $('singleWidth');
const singleHeight = $('singleHeight');
const singleSteps = $('singleSteps');
const generateOneBtn = $('generateOneBtn');
const singlePreview = $('singlePreview');
const singleMeta = $('singleMeta');
const singlePlan = $('singlePlan');

const batchFile = $('batchFile');
const batchFileInfo = $('batchFileInfo');
const batchText = $('batchText');
const batchBackend = $('batchBackend');
const batchEngineUrl = $('batchEngineUrl');
const batchWidth = $('batchWidth');
const batchHeight = $('batchHeight');
const batchSteps = $('batchSteps');
const startBatchBtn = $('startBatchBtn');
const cancelBatchBtn = $('cancelBatchBtn');
const downloadZipLink = $('downloadZipLink');
const batchSummary = $('batchSummary');
const queueBody = $('queueBody');

let currentJobId = null;
let pollTimer = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`.trim();
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch (_) {
      try {
        const text = await response.text();
        if (text) detail = text;
      } catch (_) {}
    }
    throw new Error(detail || 'Erro desconhecido');
  }
  const type = response.headers.get('content-type') || '';
  if (type.includes('application/json')) return response.json();
  return response;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function formatMs(value) {
  if (!value && value !== 0) return '-';
  const seconds = value / 1000;
  if (seconds < 1) return `${Math.round(value)}ms`;
  if (seconds < 60) return `${seconds.toFixed(2)}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${(seconds % 60).toFixed(1)}s`;
}

function normalizeBatchText(text) {
  let value = (text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  if (!value.includes('\n') && value.includes('\\n')) value = value.replaceAll('\\n', '\n');
  return value.trim();
}

function planSummary(composition) {
  const p = composition?.plan;
  if (!p) return '-';
  const parts = [];
  if (p.background?.id) parts.push(p.background.id.replace('bg_', 'FUNDO: '));
  if (p.pose?.id) parts.push(p.pose.id.replace('pose_', 'POSE: '));
  if (p.face?.id) parts.push(p.face.id.replace('face_', 'ROSTO: '));
  if (p.outfit?.id) parts.push(p.outfit.id.replace('outfit_', 'ROUPA: '));
  if (p.object?.id) parts.push(p.object.id.replace('obj_', 'OBJETO: '));
  return parts.join(' · ') || p.mode || '-';
}

function renderPlan(composition) {
  const p = composition?.plan;
  if (!p) {
    singlePlan.textContent = 'Backend sem plano de composição.';
    singlePlan.classList.add('empty');
    return;
  }
  const rows = [
    ['MODO', p.mode],
    ['FUNDO', p.background?.id || '-'],
    ['POSE', p.pose?.id || '-'],
    ['ROSTO/EXPRESSÃO', p.face?.id || '-'],
    ['ROUPA', p.outfit?.id || '-'],
    ['OBJETO', p.object?.id || '-'],
    ['CONFIANÇA', `${Math.round((p.confidence || 0) * 100)}%`],
  ];
  singlePlan.innerHTML = rows.map(([k,v]) => `<div><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join('');
  singlePlan.classList.remove('empty');
}

async function refreshHealth() {
  try {
    const [health, system] = await Promise.all([api('/api/health'), api('/api/system')]);
    healthBadge.textContent = `Online · V${health.version} · ${health.jobs} lote(s)`;
    const gpu = system.gpu_names?.length ? `GPU: ${system.gpu_names.join(', ')}` : 'GPU: não identificada';
    systemBadge.textContent = `${gpu} · CUDA: ${system.cuda_available ? 'SIM' : 'NÃO'} · recomendado: COMPOSER`;
  } catch (err) {
    healthBadge.textContent = 'Motor offline';
    systemBadge.textContent = err.message;
  }
}

async function refreshComposerStatus(showMessage = false) {
  try {
    const data = await api('/api/composer/status');
    bankAssets.textContent = `${data.total_assets} ITENS`;
    const c = data.categories || {};
    bankBreakdown.textContent = `${c.background || 0} FUNDOS · ${c.object || 0} OBJETOS · ${c.pose || 0} POSES · ${c.face || 0} ROSTOS · ${c.outfit || 0} ROUPAS`;
    if (showMessage) composerMessage.textContent = `Banco carregado em ${data.root}`;
  } catch (err) {
    bankAssets.textContent = 'ERRO';
    bankBreakdown.textContent = '-';
    composerMessage.textContent = `Erro ao ler banco: ${err.message}`;
  }
}

function toggleBackendFields() {
  const singleIsA1111 = singleBackend.value === 'automatic1111';
  const batchIsA1111 = batchBackend.value === 'automatic1111';
  const singleUrlWrap = singleEngineUrl.closest('.a1111-only');
  const batchUrlWrap = batchEngineUrl.closest('.a1111-only');
  if (singleUrlWrap) singleUrlWrap.style.display = singleIsA1111 ? '' : 'none';
  if (batchUrlWrap) batchUrlWrap.style.display = batchIsA1111 ? '' : 'none';
  generateOneBtn.textContent = singleBackend.value === 'composer' ? 'Compor imagem' : 'Gerar imagem';
}

function renderQueue(items, jobId) {
  queueBody.innerHTML = '';
  for (const item of items) {
    const tr = document.createElement('tr');
    const fileCell = item.output_file
      ? `<a href="/api/batch/${encodeURIComponent(jobId)}/image/${encodeURIComponent(item.output_file)}" target="_blank">${escapeHtml(item.output_file)}</a>`
      : escapeHtml(item.error || '-');
    tr.innerHTML = `
      <td>${escapeHtml(item.id)}</td>
      <td class="status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</td>
      <td>${formatMs(item.duration_ms)}</td>
      <td class="plan-cell">${escapeHtml(planSummary(item.composition))}</td>
      <td class="error-cell">${fileCell}</td>
    `;
    queueBody.appendChild(tr);
  }
}

function updateDownloadLink(jobId, ready) {
  if (ready) {
    downloadZipLink.classList.remove('disabled');
    downloadZipLink.href = `/api/batch/${encodeURIComponent(jobId)}/zip`;
  } else {
    downloadZipLink.classList.add('disabled');
    downloadZipLink.href = '#';
  }
}

async function pollBatchStatus() {
  if (!currentJobId) return;
  try {
    const data = await api(`/api/batch/${currentJobId}`);
    const doneItems = data.items.filter(x => x.status === 'done' && x.duration_ms !== null);
    const avg = doneItems.length ? doneItems.reduce((acc, x) => acc + x.duration_ms, 0) / doneItems.length : null;
    batchSummary.textContent = `Job ${data.job_id} · ${data.status.toUpperCase()} · ${data.completed}/${data.total} concluídas · ${data.failed} falhas${avg !== null ? ` · média ${formatMs(avg)}` : ''}`;
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

refreshComposerBtn.addEventListener('click', () => refreshComposerStatus(true));
rebuildComposerBtn.addEventListener('click', async () => {
  rebuildComposerBtn.disabled = true;
  composerMessage.textContent = 'Recriando banco visual demo...';
  try {
    const data = await api('/api/composer/rebuild-demo', { method: 'POST' });
    composerMessage.textContent = `Banco demo recriado · ${data.total_assets} assets.`;
    await refreshComposerStatus(false);
  } catch (err) {
    composerMessage.textContent = `Erro: ${err.message}`;
  } finally {
    rebuildComposerBtn.disabled = false;
  }
});

singleBackend.addEventListener('change', toggleBackendFields);
batchBackend.addEventListener('change', toggleBackendFields);

batchFile.addEventListener('change', async () => {
  const file = batchFile.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    batchText.value = normalizeBatchText(text);
    const count = batchText.value.split('\n').filter(Boolean).length;
    batchFileInfo.textContent = `${file.name} · ${count} linha(s) carregada(s)`;
  } catch (err) {
    batchFileInfo.textContent = `Erro ao ler TXT: ${err.message}`;
  }
});

generateOneBtn.addEventListener('click', async () => {
  const prompt = singlePrompt.value.trim();
  if (!prompt) {
    singleMeta.textContent = 'Digite um prompt.';
    return;
  }
  generateOneBtn.disabled = true;
  singleMeta.className = 'meta';
  singleMeta.textContent = singleBackend.value === 'composer'
    ? 'Interpretando prompt → buscando memória visual → compondo...'
    : 'Gerando...';
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
    singleMeta.textContent = `SUCESSO · ${data.backend.toUpperCase()} · ${formatMs(data.duration_ms)}`;
    singleMeta.className = 'meta success-text';
    renderPlan(data.composition);
  } catch (err) {
    singleMeta.textContent = `Erro: ${err.message}`;
    singleMeta.className = 'meta error-text';
  } finally {
    generateOneBtn.disabled = false;
  }
});

startBatchBtn.addEventListener('click', async () => {
  const text = normalizeBatchText(batchText.value);
  batchText.value = text;
  if (!text) {
    batchSummary.textContent = 'Importe ou cole os prompts do lote.';
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
    batchSummary.textContent = `Job ${data.job_id} iniciado · ${data.total} item(ns) · backend ${data.backend}`;
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(pollBatchStatus, 500);
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

Promise.all([refreshHealth(), refreshComposerStatus(false)]).then(toggleBackendFields);
setInterval(refreshHealth, 10000);
