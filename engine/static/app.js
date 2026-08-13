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

let currentJobId = null;
let pollTimer = null;
let currentBenchmarkId = null;
let benchmarkPollTimer = null;
let currentOperationId = null;

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
    healthBadge.textContent = `Online · V${health.version} · ${health.jobs} lote(s)`;
    const gpu = system.gpu_names?.length ? `GPU: ${system.gpu_names.join(', ')}` : 'GPU: não identificada';
    const memory = system.memory?.total_items ?? 0;
    const anatomy = system.anatomy?.ready ? 'POSE PRONTA' : 'POSE FALLBACK';
    systemBadge.textContent = `${gpu} · CUDA: ${system.cuda_available ? 'SIM' : 'NÃO'} · memória visual: ${memory} item(ns) · anatomia: ${anatomy} · providers: ${(system.providers || []).join(', ')}`;
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
  generateOneBtn.textContent = singleBackend.value === 'composer' ? 'Compor imagem' : 'Gerar imagem';
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
    const data = await api('/api/generate/guided', {
      method: 'POST', body: JSON.stringify({
        prompt: guidedPrompt.value.trim(), guide_text,
        width: Number(guidedWidth.value), height: Number(guidedHeight.value),
        refiner: guidedRefiner.value, steps: Number(guidedSteps.value), strength: Number(guidedStrength.value),
        collect_missing: guidedCollectMissing.value === 'true', auto_approve_collected: false,
      }),
    });
    currentOperationId = data.operation_id;
    guidedPreview.src = `data:image/png;base64,${data.image_base64}`;
    guidedOperationBadge.textContent = data.operation_id;
    guidedExportLink.href = data.export_url; guidedExportLink.classList.remove('disabled');
    guidedPlan.innerHTML = guidedPlanHtml(data); guidedPlan.classList.remove('empty');
    guidedMeta.textContent = `Execução concluída · ${formatMs(data.timings?.total_ms)} · avaliação manual pendente.`;
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

Promise.all([refreshHealth(), refreshComposerStatus(false), refreshMemoryGallery(), refreshRefinerStatus()]).then(toggleBackendFields);
setInterval(refreshHealth, 10000);
