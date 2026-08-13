import { browserRuntime, DEFAULT_MODEL, TRANSFORMERS_VERSION } from './browser_runtime.js?v=0.12.13';

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
const collectMissingBtn = $('collectMissingBtn');
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

const collectQuery = $('collectQuery');
const collectType = $('collectType');
const collectSaveLimit = $('collectSaveLimit');
const collectPerProvider = $('collectPerProvider');
const collectAutoApprove = $('collectAutoApprove');
const collectBtn = $('collectBtn');
const refreshMemoryBtn = $('refreshMemoryBtn');
const collectMeta = $('collectMeta');
const collectSummary = $('collectSummary');
const memoryTypeFilter = $('memoryTypeFilter');
const memoryStateFilter = $('memoryStateFilter');
const memoryQueryFilter = $('memoryQueryFilter');
const memorySearchBtn = $('memorySearchBtn');
const memoryStatusMini = $('memoryStatusMini');
const memoryGallery = $('memoryGallery');

const guidedPrompt = $('guidedPrompt');
const guidedGuide = $('guidedGuide');
const guidedWidth = $('guidedWidth');
const guidedHeight = $('guidedHeight');
const guidedRefiner = $('guidedRefiner');
const guidedSteps = $('guidedSteps');
const guidedStrength = $('guidedStrength');
const guidedCollectMissing = $('guidedCollectMissing');
const guidedCollectBtn = $('guidedCollectBtn');
const guidedRunBtn = $('guidedRunBtn');
const guidedExportLink = $('guidedExportLink');
const guidedMeta = $('guidedMeta');
const guidedPreview = $('guidedPreview');
const guidedPlan = $('guidedPlan');
const guidedOperationBadge = $('guidedOperationBadge');
const guidedErrorType = $('guidedErrorType');
const guidedSeverity = $('guidedSeverity');
const guidedProblem = $('guidedProblem');
const guidedApproveBtn = $('guidedApproveBtn');
const guidedRejectBtn = $('guidedRejectBtn');
const guidedSaveEvalBtn = $('guidedSaveEvalBtn');
const guidedFixGuide = $('guidedFixGuide');
const guidedReprocessBtn = $('guidedReprocessBtn');

const refinerStatusBadge = $('refinerStatusBadge');
const refinerSize = $('refinerSize');
const refinerSteps = $('refinerSteps');
const refinerStrength = $('refinerStrength');
const benchmarkLightBtn = $('benchmarkLightBtn');
const benchmarkAiBtn = $('benchmarkAiBtn');
const cancelBenchmarkBtn = $('cancelBenchmarkBtn');
const refreshRefinerBtn = $('refreshRefinerBtn');
const benchmarkPrompts = $('benchmarkPrompts');
const benchmarkMeta = $('benchmarkMeta');
const benchmarkVerdict = $('benchmarkVerdict');
const benchmarkBody = $('benchmarkBody');

const browserRuntimeBadge = $('browserRuntimeBadge');
const browserWebgpu = $('browserWebgpu');
const browserProfile = $('browserProfile');
const browserCache = $('browserCache');
const browserModelStatus = $('browserModelStatus');
const browserDeviceInfo = $('browserDeviceInfo');
const browserDeviceMode = $('browserDeviceMode');
const browserModel = $('browserModel');
const browserInputLimit = $('browserInputLimit');
const browserDetectBtn = $('browserDetectBtn');
const browserBenchmarkBtn = $('browserBenchmarkBtn');
const browserPrepareBtn = $('browserPrepareBtn');
const browserClearCacheBtn = $('browserClearCacheBtn');
const browserProgressBar = $('browserProgressBar');
const browserProgressText = $('browserProgressText');
const browserImageFile = $('browserImageFile');
const browserUseComposerBtn = $('browserUseComposerBtn');
const browserUseGuidedBtn = $('browserUseGuidedBtn');
const browserRefineBtn = $('browserRefineBtn');
const browserDownloadLink = $('browserDownloadLink');
const browserRefineMeta = $('browserRefineMeta');
const browserBeforePreview = $('browserBeforePreview');
const browserAfterPreview = $('browserAfterPreview');
const simpleAiStatus = $('simpleAiStatus');
const singleDownloadLink = $('singleDownloadLink');
const singleOperationExportLink = $('singleOperationExportLink');
const productionGuideFile = $('productionGuideFile');
const productionGuideInfo = $('productionGuideInfo');
const productionGuideText = $('productionGuideText');


let currentJobId = null;
let pollTimer = null;
let currentBenchmarkId = null;
let benchmarkPollTimer = null;
let currentOperationId = null;
let browserSelectedSource = null;
let browserSelectedLabel = null;
let browserBatchCancelled = false;
let browserBatchObjectUrls = [];
let currentSingleOperationBundle = null;
let currentSingleOperationZipUrl = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.status === 504
      ? 'Tempo limite do servidor durante a operação. A coleta será abortada e deve retornar diagnóstico em vez de esperar indefinidamente.'
      : `${response.status} ${response.statusText}`.trim();
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

function syncFriendlyFormatFromGuide(text) {
  if (!simpleFormat || !singleWidth || !singleHeight || !text) return null;
  const outputMatch = String(text).match(/\[OUTPUT\]([\s\S]*?)(?=\n\s*\[[^\]]+\]|$)/i);
  if (!outputMatch) return null;
  const block = outputMatch[1] || '';
  const read = (key) => {
    const m = block.match(new RegExp(`^\\s*${key}\\s*=\\s*(.+?)\\s*$`, 'im'));
    return m ? m[1].trim() : '';
  };
  let w = Number(read('width') || 0);
  let h = Number(read('height') || 0);
  const ratio = String(read('aspect_ratio') || '').replace(/\s/g, '');
  if ((!w || !h) && /^\d+(?:\.\d+)?:\d+(?:\.\d+)?$/.test(ratio)) {
    const [rw, rh] = ratio.split(':').map(Number);
    if (rw && rh) {
      if (rh > rw) { h = 1280; w = Math.round(h * rw / rh); }
      else if (rw > rh) { w = 1280; h = Math.round(w * rh / rw); }
      else { w = h = 768; }
    }
  }
  if (w && h) { singleWidth.value = String(w); singleHeight.value = String(h); }
  if (w && h) {
    const r = w / h;
    simpleFormat.value = Math.abs(r - 1) < 0.08 ? 'square' : (r > 1 ? 'landscape' : 'portrait');
    simpleFormat.dataset.guideControlled = 'true';
    simpleFormat.title = `Formato definido pelo guia: ${w}×${h}`;
    return { width: w, height: h, ratio };
  }
  return null;
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
    ['FUNDO', `${p.background?.id || '-'}${p.background?.source ? ` · ${p.background.source}` : ''}`],
    ['POSE', `${p.pose?.id || '-'}${p.pose?.source ? ` · ${p.pose.source}` : ''}`],
    ['ROSTO/EXPRESSÃO', `${p.face?.id || '-'}${p.face?.source ? ` · ${p.face.source}` : ''}`],
    ['ROUPA', `${p.outfit?.id || '-'}${p.outfit?.source ? ` · ${p.outfit.source}` : ''}`],
    ['OBJETO', `${p.object?.id || '-'}${p.object?.source ? ` · ${p.object.source}` : ''}`],
    ['CONFIANÇA', `${Math.round((p.confidence || 0) * 100)}%`],
  ];
  singlePlan.innerHTML = rows.map(([k,v]) => `<div><span>${escapeHtml(k)}</span><strong>${escapeHtml(v)}</strong></div>`).join('');
  singlePlan.classList.remove('empty');
}

async function refreshHealth() {
  try {
    const [health, system] = await Promise.all([api('/api/health'), api('/api/system')]);
    const runtimeLabel = health.runtime_mode === 'vercel' ? 'VERCEL · TEMPORÁRIO' : 'LOCAL';
    healthBadge.textContent = `Online · V${health.version} · ${runtimeLabel} · ${health.jobs} lote(s)`;
    const gpu = system.gpu_names?.length ? `GPU: ${system.gpu_names.join(', ')}` : 'GPU: não identificada';
    const memory = system.memory?.total_items ?? 0;
    const anatomy = system.anatomy?.ready ? 'POSE PRONTA' : 'POSE FALLBACK';
    if (health.runtime_mode === 'vercel') {
      systemBadge.textContent = `MODO VERCEL · REFINADOR BROWSER-FIRST NO CLIENTE · Composer API leve · dados do servidor temporários · SD.CPP apenas legado · ${memory} item(ns) na memória desta instância`;
      document.querySelectorAll('option[value="sdcpp_local"], option[value="diffusers_cpu"]').forEach(opt => {
        opt.disabled = true;
        opt.textContent = `${opt.textContent} · SOMENTE LOCAL`;
      });
    } else {
      systemBadge.textContent = `BROWSER-FIRST · ${gpu} · memória visual: ${memory} item(ns) · anatomia servidor: ${anatomy} · providers: ${(system.providers || []).join(', ')}`;
    }
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
    if (showMessage) composerMessage.textContent = `Banco carregado. Demo + memória visual local.`;
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
  generateOneBtn.textContent = singleBackend.value === 'composer_browser' ? 'Compor + refinar no navegador' : (singleBackend.value === 'composer' ? 'Compor imagem' : 'Gerar imagem');
}

function renderQueue(items, jobId) {
  queueBody.innerHTML = '';
  for (const item of items) {
    const tr = document.createElement('tr');
    const fileCell = item.output_file
      ? `<a href="/api/batch/${encodeURIComponent(jobId)}/image/${encodeURIComponent(item.output_file)}" target="_blank">${escapeHtml(item.output_file)}</a>${item.export_url ? ` · <a href="${escapeHtml(item.export_url)}">OPERAÇÃO</a>` : ''}`
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

function renderCollectSummary(data) {
  collectSummary.innerHTML = `
    <strong>Coleta concluída</strong><br>
    Consulta: <code>${escapeHtml(data.query || '-')}</code><br>
    Tipo: <code>${escapeHtml(data.type || '-')}</code><br>
    Candidatos encontrados: <strong>${escapeHtml(data.candidates_found)}</strong><br>
    Mantidos após filtro: <strong>${escapeHtml(data.kept_after_filter)}</strong><br>
    Salvos na memória: <strong>${escapeHtml(data.saved_count)}</strong><br>
    Erros/provedores: ${escapeHtml((data.errors || []).join(' | ') || 'nenhum')}
  `;
}

function renderMemoryGallery(items, status) {
  memoryStatusMini.textContent = `${status.total_items || 0} item(ns) · candidates ${status.candidate_items || 0} · approved ${status.approved_items || 0} · rejected ${status.rejected_items || 0}`;
  if (!items?.length) {
    memoryGallery.innerHTML = '<div class="memory-empty">Nenhuma referência encontrada na biblioteca.</div>';
    return;
  }
  memoryGallery.innerHTML = items.map(item => {
    const state = item.status || (item.approved ? 'approved' : 'candidates');
    const success = Math.round((Number(item.success_rate || 0)) * 100);
    return `
      <div class="memory-card">
        <img src="/api/memory/items/${encodeURIComponent(item.id)}/asset" alt="${escapeHtml(item.id)}" />
        <div class="memory-card-body">
          <strong>${escapeHtml(item.id)}</strong>
          <span>${escapeHtml(item.type || '-')} · ${escapeHtml(item.concept || '-')}</span>
          <span>ESTADO: ${escapeHtml(state.toUpperCase())}${item.preferred ? ' · ⭐ PREFERIDA' : ''}${item.blocked ? ' · BLOQUEADA' : ''}</span>
          <span>Fonte: ${escapeHtml(item.source || '-')} · Licença: ${escapeHtml(item.license || '-')}</span>
          <span>Query: ${escapeHtml(item.query || '-')}</span>
          <span>Q ${escapeHtml(item.quality_score)} · R ${escapeHtml(item.relevance_score)} · usos ${escapeHtml(item.used_count || 0)} · sucesso ${success}%</span>
          <span>Operações: ${escapeHtml((item.operations_used || []).slice(-3).join(', ') || '-')}</span>
          <div class="memory-tags">${(item.tags || []).slice(0,8).map(t => `<code>${escapeHtml(t)}</code>`).join(' ')}</div>
          <div class="memory-actions">
            <button class="ghost tiny-btn" data-state-id="${escapeHtml(item.id)}" data-state="approved">Aprovar</button>
            <button class="ghost tiny-btn" data-state-id="${escapeHtml(item.id)}" data-state="rejected">Reprovar</button>
            <button class="ghost tiny-btn" data-pref-id="${escapeHtml(item.id)}" data-pref="${item.preferred ? '1' : '0'}">${item.preferred ? 'Remover preferência' : 'Preferida'}</button>
            <button class="ghost tiny-btn" data-block-id="${escapeHtml(item.id)}" data-block="${item.blocked ? '1' : '0'}">${item.blocked ? 'Desbloquear' : 'Bloquear'}</button>
            <button class="ghost tiny-btn" data-tags-id="${escapeHtml(item.id)}" data-tags="${escapeHtml((item.tags || []).join(','))}">Editar tags</button>
            <button class="ghost tiny-btn" data-move-id="${escapeHtml(item.id)}" data-type="${escapeHtml(item.type || 'other')}">Mover categoria</button>
            <button class="ghost tiny-btn" data-delete-id="${escapeHtml(item.id)}">Apagar</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
  memoryGallery.querySelectorAll('[data-state-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        await api(`/api/memory/items/${encodeURIComponent(btn.dataset.stateId)}`, {
          method: 'PATCH', body: JSON.stringify({ status: btn.dataset.state }),
        });
        await refreshMemoryGallery(); await refreshComposerStatus(false);
      } catch (err) { collectMeta.textContent = `Erro ao alterar estado: ${err.message}`; }
      finally { btn.disabled = false; }
    });
  });
  memoryGallery.querySelectorAll('[data-pref-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await api(`/api/memory/items/${encodeURIComponent(btn.dataset.prefId)}`, {
          method: 'PATCH', body: JSON.stringify({ preferred: btn.dataset.pref !== '1' }),
        });
        await refreshMemoryGallery();
      } catch (err) { collectMeta.textContent = `Erro ao marcar preferência: ${err.message}`; }
    });
  });
  memoryGallery.querySelectorAll('[data-block-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      try {
        await api(`/api/memory/items/${encodeURIComponent(btn.dataset.blockId)}`, {
          method: 'PATCH', body: JSON.stringify({ blocked: btn.dataset.block !== '1' }),
        });
        await refreshMemoryGallery(); await refreshComposerStatus(false);
      } catch (err) { collectMeta.textContent = `Erro ao bloquear referência: ${err.message}`; }
    });
  });
  memoryGallery.querySelectorAll('[data-tags-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const value = window.prompt('TAGS SEPARADAS POR VÍRGULA', btn.dataset.tags || '');
      if (value === null) return;
      const tags = value.split(',').map(x => x.trim()).filter(Boolean);
      try {
        await api(`/api/memory/items/${encodeURIComponent(btn.dataset.tagsId)}`, { method: 'PATCH', body: JSON.stringify({ tags }) });
        await refreshMemoryGallery(); await refreshComposerStatus(false);
      } catch (err) { collectMeta.textContent = `Erro ao editar tags: ${err.message}`; }
    });
  });
  memoryGallery.querySelectorAll('[data-move-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const type = window.prompt('NOVA CATEGORIA (object, background, pose, face, character, lighting, camera...)', btn.dataset.type || 'other');
      if (!type) return;
      try {
        await api(`/api/memory/items/${encodeURIComponent(btn.dataset.moveId)}`, { method: 'PATCH', body: JSON.stringify({ type: type.trim() }) });
        await refreshMemoryGallery(); await refreshComposerStatus(false);
      } catch (err) { collectMeta.textContent = `Erro ao mover categoria: ${err.message}`; }
    });
  });
  memoryGallery.querySelectorAll('[data-delete-id]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!window.confirm(`Apagar ${btn.dataset.deleteId} da biblioteca física?`)) return;
      try {
        await api(`/api/memory/items/${encodeURIComponent(btn.dataset.deleteId)}`, { method: 'DELETE' });
        await refreshMemoryGallery(); await refreshComposerStatus(false);
      } catch (err) { collectMeta.textContent = `Erro ao apagar referência: ${err.message}`; }
    });
  });
}


async function refreshRefinerStatus() {
  try {
    const data = await api('/api/refiner/status');
    const ai = data.sdcpp_img2img || {};
    const engine = ai.engine || {};
    if (ai.available) {
      const cf = ai.conditioning_features || {};
      const refs = [cf.ip_adapter_image ? 'IDENTIDADE' : null, cf.control_image ? 'POSE' : null, cf.ref_images ? 'REFS' : null].filter(Boolean);
      const conditioning = refs.length ? ` · refs: ${refs.join('+')}` : ' · refs: FALLBACK';
      refinerStatusBadge.textContent = `IA disponível · ${engine.mode || 'auto'} · ${engine.ready ? 'PRONTO' : 'instalado'}${conditioning}`;
      refinerStatusBadge.classList.remove('bad-badge');
    } else {
      refinerStatusBadge.textContent = 'IA não instalada · rode INSTALAR_VULKAN.bat';
      refinerStatusBadge.classList.add('bad-badge');
    }
  } catch (err) {
    refinerStatusBadge.textContent = `Erro: ${err.message}`;
    refinerStatusBadge.classList.add('bad-badge');
  }
}

function benchmarkPromptsArray() {
  return benchmarkPrompts.value
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map(x => x.trim())
    .filter(Boolean)
    .slice(0, 10);
}

function renderBenchmark(job) {
  benchmarkBody.innerHTML = '';
  for (const item of (job.items || [])) {
    const links = item.before_file
      ? `<a href="/api/refiner/benchmark/${encodeURIComponent(job.job_id)}/image/${encodeURIComponent(item.before_file)}" target="_blank">ANTES</a>${item.after_file ? ` · <a href="/api/refiner/benchmark/${encodeURIComponent(job.job_id)}/image/${encodeURIComponent(item.after_file)}" target="_blank">DEPOIS</a>` : ''}`
      : escapeHtml(item.error || '-');
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${escapeHtml(item.index)}</td>
      <td class="status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</td>
      <td>${formatMs(item.composer_ms)}</td>
      <td>${formatMs(item.refiner_ms)}</td>
      <td>${formatMs(item.total_ms)}</td>
      <td>${item.engine_ram_mb != null ? `${escapeHtml(item.engine_ram_mb)} MB` : '-'}</td>
      <td>${links}</td>
    `;
    benchmarkBody.appendChild(tr);
  }
  const s = job.summary;
  if (s && !s.error) {
    benchmarkVerdict.classList.remove('empty');
    benchmarkVerdict.innerHTML = `
      <div><span>VEREDITO</span><strong>${escapeHtml(s.verdict)}</strong></div>
      <div><span>START MOTOR</span><strong>${formatMs(s.engine_start_ms)}</strong></div>
      <div><span>1ª IMAGEM</span><strong>${formatMs(s.first_refiner_ms)}</strong></div>
      <div><span>MÉDIA AQUECIDA</span><strong>${formatMs(s.warm_avg_refiner_ms)}</strong></div>
      <div><span>MÍN / MÁX</span><strong>${formatMs(s.min_refiner_ms)} / ${formatMs(s.max_refiner_ms)}</strong></div>
      <div><span>FLOW REFERÊNCIA</span><strong>~32s / imagem</strong></div>
    `;
  } else if (s?.error) {
    benchmarkVerdict.classList.remove('empty');
    benchmarkVerdict.innerHTML = `<div><span>ERRO</span><strong>${escapeHtml(s.error)}</strong></div>`;
  }
}

async function pollBenchmark() {
  if (!currentBenchmarkId) return;
  try {
    const job = await api(`/api/refiner/benchmark/${currentBenchmarkId}`);
    benchmarkMeta.textContent = `Benchmark ${job.job_id} · ${job.status.toUpperCase()} · ${job.completed}/${job.total} concluídas · ${job.failed} falhas${job.engine_start_ms != null ? ` · carga do motor ${formatMs(job.engine_start_ms)}` : ''}`;
    renderBenchmark(job);
    if (['done', 'error', 'cancelled'].includes(job.status)) {
      clearInterval(benchmarkPollTimer);
      benchmarkPollTimer = null;
      benchmarkLightBtn.disabled = false;
      benchmarkAiBtn.disabled = false;
      await refreshRefinerStatus();
    }
  } catch (err) {
    benchmarkMeta.textContent = `Erro ao consultar benchmark: ${err.message}`;
    if (benchmarkPollTimer) clearInterval(benchmarkPollTimer);
    benchmarkPollTimer = null;
    benchmarkLightBtn.disabled = false;
    benchmarkAiBtn.disabled = false;
  }
}

async function startBenchmark(backend) {
  const prompts = benchmarkPromptsArray();
  if (!prompts.length) {
    benchmarkMeta.textContent = 'Informe pelo menos um prompt.';
    return;
  }
  benchmarkLightBtn.disabled = true;
  benchmarkAiBtn.disabled = true;
  benchmarkVerdict.className = 'benchmark-verdict empty';
  benchmarkVerdict.textContent = 'Benchmark em andamento...';
  benchmarkBody.innerHTML = '';
  benchmarkMeta.textContent = backend === 'sdcpp_img2img'
    ? 'Iniciando motor local e preparando benchmark IA... A primeira carga pode demorar bastante.'
    : 'Executando baseline de refinamento leve...';
  try {
    const size = Number(refinerSize.value);
    const job = await api('/api/refiner/benchmark', {
      method: 'POST',
      body: JSON.stringify({
        backend,
        prompts,
        width: size,
        height: size,
        steps: Number(refinerSteps.value),
        strength: Number(refinerStrength.value),
      }),
    });
    currentBenchmarkId = job.job_id;
    if (benchmarkPollTimer) clearInterval(benchmarkPollTimer);
    benchmarkPollTimer = setInterval(pollBenchmark, 1000);
    pollBenchmark();
  } catch (err) {
    benchmarkMeta.textContent = `Erro ao iniciar benchmark: ${err.message}`;
    benchmarkLightBtn.disabled = false;
    benchmarkAiBtn.disabled = false;
  }
}


function guidedPlanHtml(data) {
  const refs = (data.references || []).map(x => `${x.label || x.id}: ${x.id}`).join('<br>') || 'Nenhuma referência da biblioteca selecionada.';
  const t = data.timings || {};
  const applied = data.refiner?.conditioning_applied || [];
  const fallback = data.refiner?.conditioning_fallback || '';
  const conditioning = applied.length ? applied.join(' · ') : (fallback ? `FALLBACK: ${fallback}` : 'não aplicado');
  return `<div><span>OPERAÇÃO</span><strong>${escapeHtml(data.operation_id || '-')}</strong></div>
    <div><span>TEMPOS</span><strong>coleta ${formatMs(t.collect_ms)} · composer ${formatMs(t.composer_ms)} · refinador ${formatMs(t.refiner_ms)} · total ${formatMs(t.total_ms)}</strong></div>
    <div><span>REFERÊNCIAS</span><strong>${refs}</strong></div>
    <div><span>CONDICIONAMENTO</span><strong>${escapeHtml(conditioning)}</strong></div>`;
}

async function guidedEvaluate(approved = null) {
  if (!currentOperationId) { guidedMeta.textContent = 'Execute uma operação primeiro.'; return; }
  const body = {
    error_type: guidedErrorType.value.trim() || null,
    problem: guidedProblem.value.trim() || null,
    severity: guidedSeverity.value || null,
    notes: guidedProblem.value.trim() || null,
  };
  if (approved !== null) body.approved = approved;
  try {
    await api(`/api/operations/${encodeURIComponent(currentOperationId)}/evaluate`, { method: 'POST', body: JSON.stringify(body) });
    guidedMeta.textContent = approved === true ? 'Operação aprovada e histórico das referências atualizado.' : approved === false ? 'Operação reprovada e histórico das referências atualizado.' : 'Anotação salva no log da operação.';
    await refreshMemoryGallery();
  } catch (err) { guidedMeta.textContent = `Erro na avaliação: ${err.message}`; }
}

async function reprocessGuidedRegion() {
  if (!currentOperationId) { guidedMeta.textContent = 'Execute uma operação primeiro.'; return; }
  const correction_guide_text = guidedFixGuide.value.trim();
  if (!correction_guide_text) { guidedMeta.textContent = 'Informe o guia [REPROCESS]/[FIX].'; return; }
  guidedReprocessBtn.disabled = true;
  const parentOperationId = currentOperationId;
  const effectiveRefiner = guidedRefiner.value === 'none' ? 'light_cpu' : guidedRefiner.value;
  guidedMeta.textContent = `Reprocessando somente a região indicada · base ${parentOperationId}...`;
  try {
    const data = await api(`/api/operations/${encodeURIComponent(parentOperationId)}/reprocess`, {
      method: 'POST', body: JSON.stringify({
        correction_guide_text, refiner: effectiveRefiner,
        steps: Number(guidedSteps.value), strength: Number(guidedStrength.value),
      }),
    });
    currentOperationId = data.operation_id;
    guidedPreview.src = `data:image/png;base64,${data.image_base64}`;
    guidedOperationBadge.textContent = `${data.operation_id} ← ${parentOperationId}`;
    guidedExportLink.href = data.export_url; guidedExportLink.classList.remove('disabled');
    const fixText = (data.fixes || []).map(x => `${x.region?.name || 'região'} [${(x.region?.box || []).join(', ')}] · ${x.backend || effectiveRefiner}`).join('<br>');
    guidedPlan.innerHTML = `<div><span>OPERAÇÃO FILHA</span><strong>${escapeHtml(data.operation_id)}</strong></div>
      <div><span>OPERAÇÃO PAI</span><strong>${escapeHtml(parentOperationId)}</strong></div>
      <div><span>CORREÇÕES</span><strong>${fixText || '-'}</strong></div>
      <div><span>TEMPO</span><strong>${formatMs(data.timings?.total_ms)}</strong></div>`;
    guidedPlan.classList.remove('empty');
    guidedMeta.textContent = `Reprocessamento concluído · ${formatMs(data.timings?.total_ms)} · o restante da imagem foi preservado por máscara regional.`;
  } catch (err) {
    guidedMeta.textContent = `Erro no reprocessamento: ${err.message}`;
  } finally {
    guidedReprocessBtn.disabled = false;
  }
}

async function collectGuidedReferences() {
  const guide_text = guidedGuide.value.trim();
  if (!guide_text) return;
  guidedCollectBtn.disabled = true;
  guidedMeta.textContent = 'Executando SEARCH_* e FILTER do guia...';
  try {
    const data = await api('/api/guide/collect', { method: 'POST', body: JSON.stringify({ guide_text, auto_approve: false }) });
    const saved = (data.results || []).reduce((n, x) => n + Number(x.result?.saved_count || 0), 0);
    const rejected = (data.results || []).reduce((n, x) => n + Number(x.result?.saved_rejected_count || 0), 0);
    guidedMeta.textContent = `Busca guiada concluída · ${saved} candidates salvos · ${rejected} rejeitados auditáveis.`;
    await refreshMemoryGallery(); await refreshComposerStatus(false); await refreshHealth();
  } catch (err) { guidedMeta.textContent = `Erro na busca guiada: ${err.message}`; }
  finally { guidedCollectBtn.disabled = false; }
}

async function runGuided() {
  const guide_text = guidedGuide.value.trim();
  if (!guide_text) { guidedMeta.textContent = 'Cole um guia técnico.'; return; }
  guidedRunBtn.disabled = true;
  guidedExportLink.classList.add('disabled'); guidedExportLink.href = '#';
  guidedMeta.textContent = 'Executando guia → composição → refinador opcional → logs...';
  try {
    const browserRefineRequested = guidedRefiner.value === 'browser_swin2sr';
    const data = await api('/api/generate/guided', {
      method: 'POST', body: JSON.stringify({
        prompt: guidedPrompt.value.trim(), guide_text,
        width: Number(guidedWidth.value), height: Number(guidedHeight.value),
        refiner: browserRefineRequested ? 'none' : guidedRefiner.value,
        steps: Number(guidedSteps.value), strength: Number(guidedStrength.value),
        collect_missing: guidedCollectMissing.value === 'true', auto_approve_collected: false,
      }),
    });
    currentOperationId = data.operation_id;
    guidedPreview.src = `data:image/png;base64,${data.image_base64}`;
    guidedOperationBadge.textContent = data.operation_id;
    guidedExportLink.href = data.export_url; guidedExportLink.classList.remove('disabled');
    guidedPlan.innerHTML = guidedPlanHtml(data); guidedPlan.classList.remove('empty');
    if (browserRefineRequested) {
      guidedMeta.textContent = `Composição concluída em ${formatMs(data.timings?.total_ms)} · iniciando refinador no navegador...`;
      const baseDataUrl = `data:image/png;base64,${data.image_base64}`;
      const webResult = await refineSelectedInBrowser({ source: baseDataUrl, label: `operação ${data.operation_id}`, updateGuided: true });
      guidedMeta.textContent = webResult
        ? `Execução concluída · COMPOSER + BROWSER ${webResult.device.toUpperCase()} · servidor não executou a IA. ZIP do servidor mantém a composição-base; PNG web pode ser baixado no painel Browser.`
        : `Composição concluída · refinador web não executado.`;
    } else {
      guidedMeta.textContent = `Execução concluída · ${formatMs(data.timings?.total_ms)} · avaliação manual pendente.`;
    }
    await refreshMemoryGallery();
  } catch (err) { guidedMeta.textContent = `Erro na execução guiada: ${err.message}`; }
  finally { guidedRunBtn.disabled = false; }
}

async function refreshMemoryGallery() {
  try {
    const type = memoryTypeFilter.value;
    const q = memoryQueryFilter.value.trim();
    const state = memoryStateFilter?.value || '';
    const qs = new URLSearchParams();
    if (type) qs.set('type', type);
    if (state) qs.set('status', state);
    if (q) qs.set('q', q);
    qs.set('limit', '60');
    const data = await api(`/api/memory/items?${qs.toString()}`);
    renderMemoryGallery(data.items, data.status);
  } catch (err) {
    memoryGallery.innerHTML = `<div class="memory-empty error-text">Erro ao ler memória: ${escapeHtml(err.message)}</div>`;
  }
}


function formatBytes(value) {
  const n = Number(value || 0);
  if (!n) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / (1024 ** i)).toFixed(i ? 1 : 0)} ${units[i]}`;
}

function setBrowserProgress(percent = 0, text = '') {
  if (browserProgressBar) browserProgressBar.style.width = `${Math.max(0, Math.min(100, Number(percent || 0)))}%`;
  if (text && browserProgressText) browserProgressText.textContent = text;
}

async function refreshBrowserCacheStatus() {
  try {
    const data = await browserRuntime.cacheStatus();
    if (!data.available) {
      browserCache.textContent = 'INDISPONÍVEL';
      return data;
    }
    browserCache.textContent = data.matching_entries
      ? `${data.matching_entries} ARQ.${data.estimated_bytes ? ` · ${formatBytes(data.estimated_bytes)}` : ''}`
      : 'VAZIO / NÃO MEDIDO';
    return data;
  } catch (err) {
    browserCache.textContent = 'ERRO';
    return null;
  }
}

async function refreshBrowserRuntime() {
  browserRuntimeBadge.textContent = 'Detectando WebGPU...';
  browserDetectBtn.disabled = true;
  try {
    const data = await browserRuntime.detect();
    if (data.webgpu_ready) {
      browserWebgpu.textContent = 'DISPONÍVEL';
      browserWebgpu.className = 'ok';
      browserRuntimeBadge.textContent = 'BROWSER ENGINE · WEBGPU';
      if (simpleAiStatus) simpleAiStatus.textContent = 'Refinador local pronto · GPU';
      browserRuntimeBadge.className = 'badge';
    } else {
      browserWebgpu.textContent = 'FALLBACK WASM';
      browserWebgpu.className = 'warn';
      browserRuntimeBadge.textContent = 'BROWSER ENGINE · WASM';
      if (simpleAiStatus) simpleAiStatus.textContent = 'Refinador local pronto · modo compatibilidade';
    }
    browserProfile.textContent = String(data.profile || 'compatibility').toUpperCase();
    const info = data.adapter_info || {};
    const gpuName = info.description || info.device || info.architecture || info.vendor || 'GPU não identificada pelo navegador';
    browserDeviceInfo.innerHTML = [
      `<strong>${escapeHtml(gpuName)}</strong>`,
      `Perfil: ${escapeHtml(data.profile)} · RAM reportada: ${data.device_memory_gb ? `${data.device_memory_gb} GB` : 'n/d'} · CPU threads: ${data.hardware_concurrency || 'n/d'}`,
      data.webgpu_ready ? 'Execução recomendada: WEBGPU. Nenhuma instalação local necessária.' : `Execução recomendada: WASM/CPU. ${escapeHtml(data.reason || '')}`,
    ].join('<br>');
    await refreshBrowserCacheStatus();
    return data;
  } catch (err) {
    browserWebgpu.textContent = 'ERRO';
    browserWebgpu.className = 'bad';
    browserRuntimeBadge.textContent = 'Falha no diagnóstico';
    browserDeviceInfo.textContent = `Erro: ${err.message}`;
    return null;
  } finally {
    browserDetectBtn.disabled = false;
  }
}

async function prepareBrowserRefiner() {
  browserPrepareBtn.disabled = true;
  browserModelStatus.textContent = 'CARREGANDO...';
  browserModelStatus.className = 'warn';
  setBrowserProgress(3, 'Preparando runtime e modelo no navegador...');
  try {
    const data = await browserRuntime.prepareRefiner({
      device: browserDeviceMode.value,
      model: browserModel.value || DEFAULT_MODEL,
    });
    browserModelStatus.textContent = `PRONTO · ${data.device.toUpperCase()}`;
    browserModelStatus.className = 'ok';
    setBrowserProgress(100, `Refinador pronto · ${data.model} · ${data.device.toUpperCase()} · cache do navegador habilitado.`);
    await refreshBrowserCacheStatus();
    return data;
  } catch (err) {
    browserModelStatus.textContent = 'FALHOU';
    browserModelStatus.className = 'bad';
    setBrowserProgress(0, `Erro ao preparar refinador: ${err.message}`);
    throw err;
  } finally {
    browserPrepareBtn.disabled = false;
  }
}

async function runBrowserBenchmark() {
  browserBenchmarkBtn.disabled = true;
  browserProgressText.textContent = 'Executando compute shader WebGPU no próprio navegador...';
  try {
    const data = await browserRuntime.benchmarkWebGPU();
    browserProgressText.textContent = `WebGPU OK · ${data.duration_ms} ms · ${data.passes} passes · ~${data.effective_million_elements_per_second} M elementos/s (indicador interno, não comparação entre modelos).`;
  } catch (err) {
    browserProgressText.textContent = `Benchmark WebGPU indisponível: ${err.message}. O modo WASM continua possível.`;
  } finally {
    browserBenchmarkBtn.disabled = false;
  }
}

function setBrowserSource(source, label, previewUrl = null) {
  browserSelectedSource = source;
  browserSelectedLabel = label;
  browserBeforePreview.src = previewUrl || (typeof source === 'string' ? source : '');
  browserAfterPreview.removeAttribute('src');
  browserDownloadLink.classList.add('disabled');
  browserDownloadLink.href = '#';
  browserRefineMeta.textContent = `Fonte selecionada: ${label}`;
}

function setSingleDownload(dataUrl, fileName = 'corvo_imagem.png') {
  if (!singleDownloadLink) return;
  singleDownloadLink.href = dataUrl || '#';
  singleDownloadLink.download = fileName;
  if (dataUrl) singleDownloadLink.classList.remove('disabled');
  else singleDownloadLink.classList.add('disabled');
}

function stripDataUrlPrefix(dataUrl) {
  const value = String(dataUrl || '');
  const comma = value.indexOf(',');
  return comma >= 0 ? value.slice(comma + 1) : value;
}

function operationRefLogRows(rows = []) {
  return (rows || []).map((ref) => {
    const copy = { ...ref };
    delete copy.image_base64;
    return copy;
  });
}

async function exportCurrentSingleOperation() {
  const bundle = currentSingleOperationBundle;
  if (!bundle) throw new Error('Nenhuma operação guiada pronta para exportar.');
  const operationId = bundle.operation_id || `operacao_${Date.now()}`;
  const originalLabel = singleOperationExportLink?.textContent || 'Exportar operação';
  if (singleOperationExportLink) {
    singleOperationExportLink.classList.add('disabled');
    singleOperationExportLink.textContent = 'Montando ZIP...';
  }
  try {
    const mod = await import('https://cdn.jsdelivr.net/npm/jszip@3.10.1/+esm');
    const JSZip = mod.default || mod;
    const zip = new JSZip();
    const data = bundle.server || {};
    const refined = bundle.refined || {};
    const refinerLog = {
      backend: 'browser',
      id: refined.id || null,
      device: refined.device || null,
      model: refined.model || null,
      strategy: refined.strategy || null,
      change_score: refined.change_score ?? null,
      model_difference: refined.model_difference ?? null,
      duration_ms: refined.duration_ms ?? null,
      note: refined.note || '',
      guided: refined.guided || false,
      guide_sections: refined.guide_sections || [],
      guide_refine_strength: refined.guide_refine_strength ?? null,
      reference_count: refined.reference_count ?? (data.references || []).length,
      unsupported_guided_directives: refined.unsupported_guided_directives || [],
    };
    const totalMs = Number(data.timings?.total_ms || 0) + Number(refined.duration_ms || 0);
    const now = new Date().toISOString();

    zip.file('pedido_original.txt', bundle.prompt || '');
    zip.file('guia_auxiliar.txt', bundle.guide_text || '');
    zip.file('resultado_final.png', stripDataUrlPrefix(bundle.final_data_url), { base64: true });
    zip.file('etapas/composicao_base.png', stripDataUrlPrefix(bundle.base_data_url), { base64: true });
    zip.file('etapas/antes_refinamento.png', stripDataUrlPrefix(bundle.base_data_url), { base64: true });
    zip.file('etapas/depois_refinamento.png', stripDataUrlPrefix(bundle.final_data_url), { base64: true });

    for (const file of (data.client_export?.reference_files || [])) {
      if (!file?.image_base64) continue;
      const safeName = String(file.name || `${file.id || 'referencia'}.png`).replace(/[\/:*?"<>|]+/g, '_');
      zip.file(`referencias_usadas/${safeName}`, file.image_base64, { base64: true });
    }

    zip.file('logs/buscas.json', JSON.stringify(data.searches || [], null, 2));
    zip.file('logs/referencias.json', JSON.stringify({ used: operationRefLogRows(data.references || []) }, null, 2));
    zip.file('logs/composicao.json', JSON.stringify(data.composition || {}, null, 2));
    zip.file('logs/refinador.json', JSON.stringify(refinerLog, null, 2));
    zip.file('logs/condicionamento.json', JSON.stringify({ requested: false, browser_first: true }, null, 2));
    zip.file('logs/tempos.json', JSON.stringify({
      collect_ms: data.timings?.collect_ms || 0,
      composer_ms: data.timings?.composer_ms || 0,
      server_refiner_ms: data.timings?.refiner_ms || 0,
      browser_refiner_ms: refined.duration_ms || 0,
      total_ms: totalMs,
    }, null, 2));
    zip.file('logs/execucao.json', JSON.stringify({
      ...(data.execution || {}),
      export_mode: 'browser',
      export_version: '0.12.13',
      final_result_owner: 'browser',
    }, null, 2));
    zip.file('logs/erros.json', JSON.stringify([], null, 2));
    zip.file('logs/avaliacao.json', JSON.stringify({ approved: null, scores: {}, notes: '' }, null, 2));
    zip.file('logs/operacao.json', JSON.stringify({
      operation_id: operationId,
      status: 'done',
      kind: 'guided_generation_browser_export',
      exported_at: now,
      server_tmp_dependency: false,
    }, null, 2));
    zip.file('diagnostico.txt', 'Execução guiada concluída. ZIP montado no navegador para evitar dependência do /tmp efêmero da Vercel.');

    const zipBlob = await zip.generateAsync({
      type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 },
    }, (meta) => {
      if (singleOperationExportLink) singleOperationExportLink.textContent = `Montando ZIP · ${Math.round(meta.percent)}%`;
    });

    if (currentSingleOperationZipUrl) URL.revokeObjectURL(currentSingleOperationZipUrl);
    currentSingleOperationZipUrl = URL.createObjectURL(zipBlob);
    const a = document.createElement('a');
    a.href = currentSingleOperationZipUrl;
    a.download = `${operationId}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    return { operation_id: operationId, bytes: zipBlob.size };
  } finally {
    if (singleOperationExportLink) {
      singleOperationExportLink.textContent = originalLabel;
      singleOperationExportLink.classList.remove('disabled');
      singleOperationExportLink.href = '#';
    }
  }
}

async function refineSelectedInBrowser({ source = null, label = null, updateGuided = false, guideText = '', referenceCount = 0 } = {}) {
  const actualSource = source || browserSelectedSource;
  if (!actualSource) {
    browserRefineMeta.textContent = 'Selecione uma imagem, ou use um preview existente.';
    return null;
  }
  browserRefineBtn.disabled = true;
  browserRefineMeta.textContent = 'Refinando localmente no navegador...';
  if (source) setBrowserSource(source, label || 'resultado guiado', typeof source === 'string' ? source : null);
  try {
    const limit = Number(browserInputLimit.value || 0) || null;
    const result = await browserRuntime.refine(actualSource, {
      device: browserDeviceMode.value,
      model: browserModel.value || DEFAULT_MODEL,
      maxInputDimension: limit,
      preserveOutputSize: true,
      ensureVisibleChange: true,
      guideText,
      referenceCount,
    });
    browserAfterPreview.src = result.dataUrl;
    browserDownloadLink.href = result.dataUrl;
    browserDownloadLink.download = `corvo_refinado_${result.id}.png`;
    browserDownloadLink.classList.remove('disabled');
    const changePct = Math.max(0.1, Number(result.change_score || 0) * 100).toFixed(1);
    browserRefineMeta.textContent = `REFINO ENTREGUE · ${result.device.toUpperCase()} · ${formatMs(result.duration_ms)} · ${result.strategy || 'browser'} · mudança detectada ${changePct}% · entrada IA ${result.model_input_width}×${result.model_input_height} · saída ${result.output_width}×${result.output_height}.`;
    browserModelStatus.textContent = `PRONTO · ${result.device.toUpperCase()}`;
    browserModelStatus.className = 'ok';
    if (updateGuided && guidedPreview) guidedPreview.src = result.dataUrl;
    return result;
  } catch (err) {
    browserRefineMeta.textContent = `Erro no refinador web: ${err.message}`;
    throw err;
  } finally {
    browserRefineBtn.disabled = false;
  }
}

browserRuntime.addEventListener('model-progress', (event) => {
  const d = event.detail || {};
  if (d.progress != null) setBrowserProgress(d.progress, d.message || d.status || 'Carregando modelo...');
  else if (d.message) browserProgressText.textContent = d.message;
});
browserRuntime.addEventListener('runtime-progress', (event) => {
  const d = event.detail || {};
  if (d.message) browserProgressText.textContent = d.message;
});
browserRuntime.addEventListener('inference-progress', (event) => {
  const d = event.detail || {};
  if (d.message) browserRefineMeta.textContent = d.message;
});

browserDetectBtn.addEventListener('click', refreshBrowserRuntime);
browserBenchmarkBtn.addEventListener('click', runBrowserBenchmark);
browserPrepareBtn.addEventListener('click', () => prepareBrowserRefiner().catch(() => {}));
browserClearCacheBtn.addEventListener('click', async () => {
  browserClearCacheBtn.disabled = true;
  try {
    const data = await browserRuntime.clearModelCache();
    browserModelStatus.textContent = 'NÃO CARREGADO';
    browserModelStatus.className = '';
    setBrowserProgress(0, `Cache limpo: ${data.deleted.length} cache(s) removido(s).`);
    await refreshBrowserCacheStatus();
  } catch (err) {
    browserProgressText.textContent = `Erro ao limpar cache: ${err.message}`;
  } finally { browserClearCacheBtn.disabled = false; }
});
browserImageFile.addEventListener('change', () => {
  const file = browserImageFile.files?.[0];
  if (!file) return;
  setBrowserSource(file, `${file.name} · ${formatBytes(file.size)}`, URL.createObjectURL(file));
});
browserUseComposerBtn.addEventListener('click', () => {
  if (!singlePreview.src || !singlePreview.src.startsWith('data:image')) {
    browserRefineMeta.textContent = 'Primeiro gere uma imagem no Composer.';
    return;
  }
  setBrowserSource(singlePreview.src, 'último preview da geração');
});
browserUseGuidedBtn.addEventListener('click', () => {
  if (!guidedPreview.src || !guidedPreview.src.startsWith('data:image')) {
    browserRefineMeta.textContent = 'Primeiro execute uma geração guiada.';
    return;
  }
  setBrowserSource(guidedPreview.src, 'último preview guiado');
});
browserRefineBtn.addEventListener('click', () => refineSelectedInBrowser().catch(() => {}));


function parseBrowserBatch(text) {
  return String(text || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean).map((line, index) => {
    const pipe = line.indexOf('|');
    if (pipe > 0) return { id: line.slice(0, pipe).trim(), prompt: line.slice(pipe + 1).trim() };
    return { id: String(index + 1).padStart(3, '0'), prompt: line };
  }).filter(x => x.prompt);
}

function renderBrowserBatchRows(items) {
  queueBody.innerHTML = '';
  for (const item of items) {
    const tr = document.createElement('tr');
    const link = item.object_url ? `<a href="${item.object_url}" target="_blank" download="${escapeHtml(item.id)}.png">${escapeHtml(item.id)}.png</a>` : escapeHtml(item.error || '-');
    tr.innerHTML = `
      <td>${escapeHtml(item.id)}</td>
      <td class="status-${escapeHtml(item.status)}">${escapeHtml(item.status)}</td>
      <td>${formatMs(item.duration_ms)}</td>
      <td class="plan-cell">${escapeHtml(item.stage || 'browser')}</td>
      <td class="error-cell">${link}</td>
    `;
    queueBody.appendChild(tr);
  }
}

async function runBrowserBatch(text) {
  const entries = parseBrowserBatch(text);
  if (!entries.length) throw new Error('Nenhum prompt encontrado.');
  browserBatchCancelled = false;
  browserBatchObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  browserBatchObjectUrls = [];
  const items = entries.map((x) => ({ ...x, status: 'pending', duration_ms: null, stage: 'aguardando', data_url: null, object_url: null, error: null }));
  renderBrowserBatchRows(items);
  updateDownloadLink('', false);
  batchSummary.textContent = `LOTE BROWSER · preparando refinador uma única vez para ${items.length} imagem(ns)...`;
  const prepared = await prepareBrowserRefiner();
  const manifest = {
    version: '0.12.13',
    execution: 'browser_client',
    generated_at: new Date().toISOString(),
    model: browserModel.value || DEFAULT_MODEL,
    device: prepared.device,
    items: [],
  };

  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    if (browserBatchCancelled) {
      item.status = 'cancelled'; item.stage = 'cancelado';
      continue;
    }
    item.status = 'running'; item.stage = 'compondo no servidor leve'; renderBrowserBatchRows(items);
    const started = performance.now();
    try {
      const composed = await api('/api/generate', {
        method: 'POST',
        body: JSON.stringify({
          prompt: item.prompt, backend: 'composer', engine_url: null,
          width: Number(batchWidth.value), height: Number(batchHeight.value), steps: 1,
        }),
      });
      item.stage = 'refinando no navegador'; renderBrowserBatchRows(items);
      const base = `data:image/png;base64,${composed.image_base64}`;
      const limit = Number(browserInputLimit.value || 0) || null;
      const refined = await browserRuntime.refine(base, {
        device: browserDeviceMode.value,
        model: browserModel.value || DEFAULT_MODEL,
        maxInputDimension: limit,
        preserveOutputSize: true,
      });
      item.duration_ms = Math.round(performance.now() - started);
      item.data_url = refined.dataUrl;
      item.status = 'done';
      item.stage = `COMPOSER → BROWSER ${refined.device.toUpperCase()}`;
      const blob = refined.blob;
      item.object_url = URL.createObjectURL(blob);
      browserBatchObjectUrls.push(item.object_url);
      manifest.items.push({
        id: item.id, prompt: item.prompt, status: 'done', duration_ms: item.duration_ms,
        browser_run_id: refined.id, browser_device: refined.device,
        model_input: [refined.model_input_width, refined.model_input_height],
        output: [refined.output_width, refined.output_height],
        composition: composed.composition || null,
      });
    } catch (err) {
      item.status = 'error'; item.error = err.message; item.stage = 'erro'; item.duration_ms = Math.round(performance.now() - started);
      manifest.items.push({ id: item.id, prompt: item.prompt, status: 'error', error: err.message, duration_ms: item.duration_ms });
    }
    renderBrowserBatchRows(items);
    const done = items.filter(x => x.status === 'done').length;
    const failed = items.filter(x => x.status === 'error').length;
    batchSummary.textContent = `LOTE BROWSER · ${done}/${items.length} concluídas · ${failed} falhas · IA executada no cliente.`;
  }

  renderBrowserBatchRows(items);
  if (browserBatchCancelled) {
    batchSummary.textContent = 'Lote browser cancelado. Resultados já concluídos continuam disponíveis.';
    return;
  }

  const success = items.filter(x => x.status === 'done');
  if (!success.length) throw new Error('Nenhuma imagem foi concluída para exportação.');
  batchSummary.textContent = `Gerando ZIP no próprio navegador · ${success.length} PNG(s)...`;
  const mod = await import('https://cdn.jsdelivr.net/npm/jszip@3.10.1/+esm');
  const JSZip = mod.default || mod;
  const zip = new JSZip();
  for (const item of success) {
    const base64 = String(item.data_url).split(',', 2)[1];
    zip.file(`${item.id}.png`, base64, { base64: true });
  }
  zip.file('manifest_browser.json', JSON.stringify(manifest, null, 2));
  const zipBlob = await zip.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } }, (meta) => {
    batchSummary.textContent = `Compactando no navegador · ${Math.round(meta.percent)}%`;
  });
  const zipUrl = URL.createObjectURL(zipBlob);
  browserBatchObjectUrls.push(zipUrl);
  downloadZipLink.href = zipUrl;
  downloadZipLink.download = `corvo_browser_lote_${Date.now()}.zip`;
  downloadZipLink.classList.remove('disabled');
  batchSummary.textContent = `LOTE CONCLUÍDO NO NAVEGADOR · ${success.length}/${items.length} PNG(s) · ZIP local pronto.`;
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

if (productionGuideFile) {
  productionGuideFile.addEventListener('change', async () => {
    const file = productionGuideFile.files?.[0];
    if (!file) {
      productionGuideInfo.textContent = 'Nenhum guia carregado · sem guia o sistema usa apenas o modo compatibilidade.';
      return;
    }
    try {
      const text = await file.text();
      productionGuideText.value = normalizeBatchText(text);
      const guideOutput = syncFriendlyFormatFromGuide(productionGuideText.value);
      const sections = (productionGuideText.value.match(/^\s*\[[^\]]+\]/gm) || []).length;
      const searchBlocks = (productionGuideText.value.match(/^\s*\[SEARCH_[^\]]+\]/gmi) || []).length;
      const fallbackLines = (productionGuideText.value.match(/^\s*(fallback_queries|query_fallbacks|query_fallback_\d+)\s*=/gmi) || []).length;
      const fallbackNote = searchBlocks && !fallbackLines
        ? ' · atenção: busca sem query de fallback'
        : (fallbackLines ? ` · ${fallbackLines} fallback(s) de busca` : '');
      const outputNote = guideOutput ? ` · saída ${guideOutput.width}×${guideOutput.height} pelo guia` : '';
      let contractNote = '';
      try {
        const parsed = await api('/api/guide/parse', { method: 'POST', body: JSON.stringify({ guide_text: productionGuideText.value }) });
        const contract = parsed.contract || {};
        if (contract.valid === false) {
          contractNote = ` · GUIA INCOMPLETO: ${(contract.issues || []).join(' | ')}`;
        } else if ((contract.warnings || []).length) {
          contractNote = ` · válido com aviso: ${(contract.warnings || []).join(' | ')}`;
        } else {
          contractNote = ' · contrato OK';
        }
      } catch (validationError) {
        contractNote = ` · validação indisponível: ${validationError.message}`;
      }
      productionGuideInfo.textContent = `${file.name} · ${sections} bloco(s) de instrução${fallbackNote}${outputNote}${contractNote}.`;
    } catch (err) {
      productionGuideInfo.textContent = `Erro ao ler guia: ${err.message}`;
    }
  });
}

generateOneBtn.addEventListener('click', async () => {
  const prompt = singlePrompt.value.trim();
  const guideText = (productionGuideText?.value || '').trim();
  if (!prompt) {
    singleMeta.textContent = 'Digite o pedido da imagem.';
    return;
  }
  generateOneBtn.disabled = true;
  currentSingleOperationBundle = null;
  setSingleDownload(null);
  if (singleOperationExportLink) { singleOperationExportLink.classList.add('disabled'); singleOperationExportLink.href = '#'; }
  singleMeta.className = 'meta';
  try {
    let data;
    let baseDataUrl;
    if (guideText) {
      singleMeta.textContent = 'Executando guia · buscando e selecionando referências...';
      data = await api('/api/generate/guided', {
        method: 'POST',
        body: JSON.stringify({
          prompt, guide_text: guideText,
          width: Number(singleWidth.value), height: Number(singleHeight.value),
          refiner: 'none', steps: 1, strength: 0.24,
          collect_missing: true, auto_approve_collected: false, use_candidates: true,
          providers: ['openverse', 'wikimedia_commons'], fast_mvp: true,
        }),
      });
      currentOperationId = data.operation_id;
      baseDataUrl = `data:image/png;base64,${data.image_base64}`;
      singlePreview.src = baseDataUrl;
      renderPlan(data.composition);
      setBrowserSource(baseDataUrl, 'montagem guiada');
      const refs = (data.references || []).length;
      const searches = (data.searches || []).length;
      singleMeta.textContent = `GUIA EXECUTADO · ${searches} busca(s) · ${refs} referência(s) usadas · refinando no navegador...`;
      const refined = await refineSelectedInBrowser({ source: baseDataUrl, label: 'produção guiada', updateGuided: false, guideText, referenceCount: refs });
      if (!refined) throw new Error('O refinador do navegador não entregou resultado.');
      singlePreview.src = refined.dataUrl;
      setSingleDownload(refined.dataUrl, `corvo_${data.operation_id}.png`);
      currentSingleOperationBundle = {
        operation_id: data.operation_id,
        prompt,
        guide_text: guideText,
        base_data_url: baseDataUrl,
        final_data_url: refined.dataUrl,
        server: data,
        refined,
      };
      if (singleOperationExportLink) {
        singleOperationExportLink.href = '#';
        singleOperationExportLink.classList.remove('disabled');
      }
      const change = (Math.max(0.1, Number(refined.change_score || 0) * 100)).toFixed(1);
      singleMeta.textContent = `IMAGEM PRONTA · GUIA → REFERÊNCIAS → COMPOSIÇÃO → REFINO · ${formatMs(Number(data.timings?.total_ms || 0) + Number(refined.duration_ms || 0))} · mudança ${change}%`;
    } else {
      singleMeta.textContent = 'Sem guia TXT · executando modo compatibilidade...';
      const browserRefineRequested = singleBackend.value === 'composer_browser';
      data = await api('/api/generate', {
        method: 'POST',
        body: JSON.stringify({
          prompt, backend: browserRefineRequested ? 'composer' : singleBackend.value,
          engine_url: singleEngineUrl.value.trim() || null, width: Number(singleWidth.value),
          height: Number(singleHeight.value), steps: Number(singleSteps.value),
        }),
      });
      baseDataUrl = `data:image/png;base64,${data.image_base64}`;
      singlePreview.src = baseDataUrl;
      setSingleDownload(baseDataUrl, 'corvo_composicao_base.png');
      renderPlan(data.composition);
      if (data.image_base64) setBrowserSource(baseDataUrl, 'última geração do Composer');
      if (browserRefineRequested) {
        const refined = await refineSelectedInBrowser({ source: baseDataUrl, label: 'geração compatibilidade', updateGuided: false });
        if (refined) {
          singlePreview.src = refined.dataUrl;
          setSingleDownload(refined.dataUrl, `corvo_refinado_${refined.id}.png`);
        }
      }
      singleMeta.textContent = 'IMAGEM PRONTA · MODO COMPATIBILIDADE · adicione um guia TXT para o pipeline de produção.';
    }
    singleMeta.className = 'meta success-text';
    await refreshComposerStatus(false);
  } catch (err) {
    singleMeta.textContent = `Erro: ${err.message}`;
    singleMeta.className = 'meta error-text';
  } finally {
    generateOneBtn.disabled = false;
  }
});

collectMissingBtn.addEventListener('click', async () => {
  const prompt = singlePrompt.value.trim();
  if (!prompt) return;
  collectMissingBtn.disabled = true;
  collectMeta.className = 'meta';
  collectMeta.textContent = 'Buscando componentes faltantes para o prompt...';
  try {
    const data = await api('/api/collect/missing', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        providers: ['openverse', 'wikimedia_commons'],
        per_provider: Number(collectPerProvider.value),
        save_limit_per_concept: 2,
        auto_approve: collectAutoApprove.value === 'true',
      }),
    });
    const saved = (data.results || []).reduce((acc, x) => acc + (x.saved_count || 0), 0);
    collectMeta.textContent = `Busca por faltantes concluída · ${saved} item(ns) salvo(s).`;
    collectSummary.innerHTML = `<strong>Lacunas detectadas:</strong> ${(data.missing || []).map(x => `${escapeHtml(x.type)}:${escapeHtml(x.concept)}`).join(' · ') || 'nenhuma'}`;
    await refreshMemoryGallery();
    await refreshComposerStatus(false);
    await refreshHealth();
  } catch (err) {
    collectMeta.textContent = `Erro na busca de faltantes: ${err.message}`;
  } finally {
    collectMissingBtn.disabled = false;
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
  if (batchBackend.value === 'composer_browser') {
    try {
      await runBrowserBatch(text);
    } catch (err) {
      batchSummary.textContent = `Erro no lote browser: ${err.message}`;
    }
    return;
  }
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
  if (batchBackend.value === 'composer_browser') {
    browserBatchCancelled = true;
    batchSummary.textContent = 'Cancelamento do lote browser solicitado...';
    return;
  }
  if (!currentJobId) return;
  try {
    await api(`/api/batch/${currentJobId}/cancel`, { method: 'POST' });
    batchSummary.textContent = `Cancelamento solicitado para ${currentJobId}`;
  } catch (err) {
    batchSummary.textContent = `Erro ao cancelar: ${err.message}`;
  }
});

collectBtn.addEventListener('click', async () => {
  const query = collectQuery.value.trim();
  if (!query) {
    collectMeta.textContent = 'Digite a consulta de coleta.';
    return;
  }
  collectBtn.disabled = true;
  collectMeta.className = 'meta';
  collectMeta.textContent = 'Consultando Openverse + Wikimedia Commons...';
  try {
    const data = await api('/api/collect', {
      method: 'POST',
      body: JSON.stringify({
        query,
        type: collectType.value,
        concept: query,
        providers: ['openverse', 'wikimedia_commons'],
        per_provider: Number(collectPerProvider.value),
        save_limit: Number(collectSaveLimit.value),
        auto_approve: collectAutoApprove.value === 'true',
      }),
    });
    collectMeta.textContent = `Coleta concluída · ${data.saved_count} item(ns) salvo(s).`;
    renderCollectSummary(data);
    await refreshMemoryGallery();
    await refreshComposerStatus(false);
    await refreshHealth();
  } catch (err) {
    collectMeta.textContent = `Erro na coleta: ${err.message}`;
  } finally {
    collectBtn.disabled = false;
  }
});


benchmarkLightBtn.addEventListener('click', () => startBenchmark('light_cpu'));
benchmarkAiBtn.addEventListener('click', () => startBenchmark('sdcpp_img2img'));
refreshRefinerBtn.addEventListener('click', refreshRefinerStatus);
cancelBenchmarkBtn.addEventListener('click', async () => {
  if (!currentBenchmarkId) return;
  try {
    await api(`/api/refiner/benchmark/${currentBenchmarkId}/cancel`, { method: 'POST' });
    benchmarkMeta.textContent = `Cancelamento solicitado para ${currentBenchmarkId}`;
  } catch (err) {
    benchmarkMeta.textContent = `Erro ao cancelar: ${err.message}`;
  }
});

refreshMemoryBtn.addEventListener('click', refreshMemoryGallery);
memorySearchBtn.addEventListener('click', refreshMemoryGallery);
if (memoryStateFilter) memoryStateFilter.addEventListener('change', refreshMemoryGallery);

guidedCollectBtn.addEventListener('click', collectGuidedReferences);
guidedRunBtn.addEventListener('click', runGuided);
guidedApproveBtn.addEventListener('click', () => guidedEvaluate(true));
guidedRejectBtn.addEventListener('click', () => guidedEvaluate(false));
guidedSaveEvalBtn.addEventListener('click', () => guidedEvaluate(null));
guidedReprocessBtn.addEventListener('click', reprocessGuidedRegion);
if (singleOperationExportLink) {
  singleOperationExportLink.addEventListener('click', async (event) => {
    event.preventDefault();
    if (singleOperationExportLink.classList.contains('disabled')) return;
    const previousMeta = singleMeta.textContent;
    try {
      singleMeta.textContent = 'Montando ZIP da operação no navegador...';
      const result = await exportCurrentSingleOperation();
      singleMeta.textContent = `${previousMeta} · ZIP ${formatBytes(result.bytes)} pronto`;
    } catch (err) {
      singleMeta.textContent = `Erro ao montar ZIP no navegador: ${err.message}`;
    }
  });
}

Promise.all([refreshHealth(), refreshComposerStatus(false), refreshMemoryGallery(), refreshRefinerStatus(), refreshBrowserRuntime()]).then(toggleBackendFields);
setInterval(refreshHealth, 10000);

// V0.12.13 · recuperação automática de busca · produção guiada
for (const button of document.querySelectorAll('.nav-btn')) {
  button.addEventListener('click', () => {
    const view = button.dataset.view || 'create';
    document.body.dataset.view = view;
    document.querySelectorAll('.nav-btn').forEach((item) => item.classList.toggle('active', item === button));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
}

function syncSimpleDownload() {
  if (!singleDownloadLink || !singlePreview) return;
  const src = singlePreview.getAttribute('src') || '';
  if (src.startsWith('data:image')) {
    singleDownloadLink.href = src;
    singleDownloadLink.classList.remove('disabled');
  } else {
    singleDownloadLink.href = '#';
    singleDownloadLink.classList.add('disabled');
  }
}
if (singlePreview && singleDownloadLink) {
  new MutationObserver(syncSimpleDownload).observe(singlePreview, { attributes: true, attributeFilter: ['src'] });
  syncSimpleDownload();
}

browserRuntime.addEventListener('model-progress', (event) => {
  if (!simpleAiStatus) return;
  const d = event.detail || {};
  if (d.status === 'ready') simpleAiStatus.textContent = `IA local pronta · ${String(d.device || '').toUpperCase()}`;
  else if (d.status === 'loading' || d.status === 'progress') simpleAiStatus.textContent = 'Preparando IA local...';
  else if (d.status === 'fallback') simpleAiStatus.textContent = 'IA local em modo compatibilidade';
});

// Controles amigáveis de formato; sincronizam os campos técnicos ocultos.
const simpleFormat = document.getElementById('simpleFormat');
const batchSimpleFormat = document.getElementById('batchSimpleFormat');
function applyFriendlyFormat(select, widthInput, heightInput) {
  if (!select || !widthInput || !heightInput) return;
  const formats = {
    square: [768, 768],
    landscape: [1024, 576],
    portrait: [576, 1024],
  };
  const [w, h] = formats[select.value] || formats.square;
  widthInput.value = String(w);
  heightInput.value = String(h);
}
if (simpleFormat) {
  simpleFormat.addEventListener('change', () => applyFriendlyFormat(simpleFormat, singleWidth, singleHeight));
  applyFriendlyFormat(simpleFormat, singleWidth, singleHeight);
}
if (batchSimpleFormat) {
  batchSimpleFormat.addEventListener('change', () => applyFriendlyFormat(batchSimpleFormat, batchWidth, batchHeight));
  applyFriendlyFormat(batchSimpleFormat, batchWidth, batchHeight);
}
