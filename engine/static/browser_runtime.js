const TRANSFORMERS_VERSION = '3.8.1';
const TRANSFORMERS_CDN = `https://cdn.jsdelivr.net/npm/@huggingface/transformers@${TRANSFORMERS_VERSION}`;
const DEFAULT_MODEL = 'Xenova/swin2SR-lightweight-x2-64';
const DB_NAME = 'corvo-browser-runtime';
const DB_VERSION = 1;
const RUN_STORE = 'runs';

function nowIso() {
  return new Date().toISOString();
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

async function blobToDataUrl(blob) {
  return await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

async function sourceToBlob(source) {
  if (source instanceof Blob) return source;
  if (source instanceof HTMLCanvasElement) {
    return await new Promise((resolve, reject) => source.toBlob((b) => b ? resolve(b) : reject(new Error('Falha ao converter canvas.')), 'image/png'));
  }
  if (typeof source === 'string') {
    const res = await fetch(source);
    if (!res.ok) throw new Error(`Falha ao ler imagem: HTTP ${res.status}`);
    return await res.blob();
  }
  throw new Error('Fonte de imagem não suportada pelo refinador web.');
}

async function blobDimensions(blob) {
  const bitmap = await createImageBitmap(blob);
  const dims = { width: bitmap.width, height: bitmap.height };
  bitmap.close();
  return dims;
}

async function resizeBlob(blob, maxDimension) {
  const bitmap = await createImageBitmap(blob);
  const maxSide = Math.max(bitmap.width, bitmap.height);
  if (maxSide <= maxDimension) {
    const dims = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return { blob, ...dims, resized: false };
  }
  const scale = maxDimension / maxSide;
  const width = Math.max(32, Math.round(bitmap.width * scale));
  const height = Math.max(32, Math.round(bitmap.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { alpha: false });
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  const out = await new Promise((resolve, reject) => canvas.toBlob((b) => b ? resolve(b) : reject(new Error('Falha ao redimensionar imagem.')), 'image/png'));
  return { blob: out, width, height, resized: true };
}

function rawImageToCanvas(raw) {
  const canvas = document.createElement('canvas');
  canvas.width = raw.width;
  canvas.height = raw.height;
  const ctx = canvas.getContext('2d', { alpha: true });
  const rgba = new Uint8ClampedArray(raw.width * raw.height * 4);
  const src = raw.data;
  const channels = raw.channels || 3;
  for (let i = 0, p = 0; i < raw.width * raw.height; i += 1, p += channels) {
    const q = i * 4;
    if (channels === 1) {
      rgba[q] = src[p]; rgba[q + 1] = src[p]; rgba[q + 2] = src[p]; rgba[q + 3] = 255;
    } else {
      rgba[q] = src[p]; rgba[q + 1] = src[p + 1]; rgba[q + 2] = src[p + 2]; rgba[q + 3] = channels >= 4 ? src[p + 3] : 255;
    }
  }
  ctx.putImageData(new ImageData(rgba, raw.width, raw.height), 0, 0);
  return canvas;
}

async function canvasToDataUrl(canvas) {
  const blob = await new Promise((resolve, reject) => canvas.toBlob((b) => b ? resolve(b) : reject(new Error('Falha ao exportar refinamento.')), 'image/png'));
  return { blob, dataUrl: await blobToDataUrl(blob) };
}

function openDb() {
  return new Promise((resolve, reject) => {
    if (!('indexedDB' in window)) return resolve(null);
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(RUN_STORE)) {
        const store = db.createObjectStore(RUN_STORE, { keyPath: 'id' });
        store.createIndex('created_at', 'created_at');
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function saveRun(run) {
  const db = await openDb();
  if (!db) return;
  await new Promise((resolve, reject) => {
    const tx = db.transaction(RUN_STORE, 'readwrite');
    tx.objectStore(RUN_STORE).put(run);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

async function listRuns(limit = 20) {
  const db = await openDb();
  if (!db) return [];
  return await new Promise((resolve, reject) => {
    const tx = db.transaction(RUN_STORE, 'readonly');
    const req = tx.objectStore(RUN_STORE).getAll();
    req.onsuccess = () => {
      const rows = (req.result || []).sort((a, b) => String(b.created_at).localeCompare(String(a.created_at))).slice(0, limit);
      db.close();
      resolve(rows);
    };
    req.onerror = () => { db.close(); reject(req.error); };
  });
}

class CorvoBrowserRuntime extends EventTarget {
  constructor() {
    super();
    this.adapter = null;
    this.device = null;
    this.transformers = null;
    this.pipelineCache = new Map();
    this.lastDetection = null;
    this.lastResult = null;
    this.model = DEFAULT_MODEL;
  }

  emit(type, detail = {}) {
    this.dispatchEvent(new CustomEvent(type, { detail }));
  }

  async detect() {
    const result = {
      browser: navigator.userAgent,
      secure_context: window.isSecureContext,
      webgpu_api: !!navigator.gpu,
      webgpu_ready: false,
      adapter_info: null,
      limits: null,
      device_memory_gb: navigator.deviceMemory || null,
      hardware_concurrency: navigator.hardwareConcurrency || null,
      cache_api: 'caches' in window,
      indexeddb: 'indexedDB' in window,
      service_worker: 'serviceWorker' in navigator,
      recommended_mode: 'wasm',
      profile: 'compatibility',
      reason: '',
    };

    if (!window.isSecureContext) {
      result.reason = 'WebGPU exige contexto seguro (HTTPS ou localhost).';
      this.lastDetection = result;
      return result;
    }
    if (!navigator.gpu) {
      result.reason = 'WebGPU não está exposto por este navegador/driver; WASM continua disponível.';
      this.lastDetection = result;
      return result;
    }

    try {
      this.adapter = await navigator.gpu.requestAdapter({ powerPreference: 'high-performance' });
      if (!this.adapter) {
        result.reason = 'Nenhum adaptador WebGPU disponível.';
      } else {
        result.webgpu_ready = true;
        result.recommended_mode = 'webgpu';
        const limits = this.adapter.limits || {};
        result.limits = {
          maxBufferSize: Number(limits.maxBufferSize || 0),
          maxStorageBufferBindingSize: Number(limits.maxStorageBufferBindingSize || 0),
          maxComputeWorkgroupStorageSize: Number(limits.maxComputeWorkgroupStorageSize || 0),
        };
        if (this.adapter.info) {
          const info = this.adapter.info;
          result.adapter_info = {
            vendor: info.vendor || '', architecture: info.architecture || '', device: info.device || '', description: info.description || '',
          };
        }
        const mem = Number(result.device_memory_gb || 0);
        const maxBuffer = result.limits.maxBufferSize;
        if (mem >= 8 || maxBuffer >= 1024 * 1024 * 1024) result.profile = 'high';
        else if (mem >= 4 || maxBuffer >= 512 * 1024 * 1024) result.profile = 'medium';
        else result.profile = 'low';
      }
    } catch (err) {
      result.reason = err?.message || String(err);
    }
    this.lastDetection = result;
    return result;
  }

  async ensureDevice() {
    if (this.device) return this.device;
    if (!this.adapter) await this.detect();
    if (!this.adapter) throw new Error('WebGPU indisponível.');
    this.device = await this.adapter.requestDevice();
    this.device.lost.then((info) => {
      this.emit('gpu-lost', { reason: info.reason, message: info.message });
      this.device = null;
    });
    return this.device;
  }

  async benchmarkWebGPU({ elements = 1024 * 1024, passes = 12 } = {}) {
    const device = await this.ensureDevice();
    const count = clamp(Number(elements), 65536, 4 * 1024 * 1024);
    const bytes = count * 4;
    const input = new Float32Array(count);
    input.fill(0.5);

    const src = device.createBuffer({ size: bytes, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST });
    const dst = device.createBuffer({ size: bytes, usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC });
    device.queue.writeBuffer(src, 0, input);
    const module = device.createShaderModule({ code: `
      @group(0) @binding(0) var<storage, read> inputData: array<f32>;
      @group(0) @binding(1) var<storage, read_write> outputData: array<f32>;
      @compute @workgroup_size(256)
      fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
        let i = gid.x;
        if (i < arrayLength(&outputData)) {
          let x = inputData[i];
          outputData[i] = x * 1.0001 + 0.0001;
        }
      }
    ` });
    const pipeline = device.createComputePipeline({ layout: 'auto', compute: { module, entryPoint: 'main' } });
    const group = device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: { buffer: src } },
        { binding: 1, resource: { buffer: dst } },
      ],
    });

    const started = performance.now();
    for (let p = 0; p < passes; p += 1) {
      const encoder = device.createCommandEncoder();
      const pass = encoder.beginComputePass();
      pass.setPipeline(pipeline);
      pass.setBindGroup(0, group);
      pass.dispatchWorkgroups(Math.ceil(count / 256));
      pass.end();
      device.queue.submit([encoder.finish()]);
    }
    await device.queue.onSubmittedWorkDone();
    const durationMs = performance.now() - started;
    src.destroy(); dst.destroy();
    return {
      duration_ms: Math.round(durationMs),
      passes,
      elements: count,
      bytes_per_pass: bytes,
      effective_million_elements_per_second: Math.round((count * passes / Math.max(1, durationMs)) / 1000),
    };
  }

  async loadTransformers() {
    if (this.transformers) return this.transformers;
    this.emit('runtime-progress', { status: 'loading-runtime', message: `Carregando Transformers.js ${TRANSFORMERS_VERSION}...` });
    const mod = await import(TRANSFORMERS_CDN);
    if (mod.env) {
      mod.env.useBrowserCache = true;
      if ('useWasmCache' in mod.env) mod.env.useWasmCache = true;
      try {
        if (mod.env.backends?.onnx?.wasm) {
          mod.env.backends.onnx.wasm.numThreads = window.crossOriginIsolated
            ? Math.max(1, Math.min(4, Number(navigator.hardwareConcurrency || 2)))
            : 1;
        }
      } catch (_) {}
    }
    this.transformers = mod;
    this.emit('runtime-progress', { status: 'runtime-ready', message: 'Runtime de IA carregado.' });
    return mod;
  }

  async prepareRefiner({ device = 'auto', model = DEFAULT_MODEL } = {}) {
    const detected = this.lastDetection || await this.detect();
    let chosen = device;
    if (chosen === 'auto') chosen = detected.webgpu_ready ? 'webgpu' : 'wasm';
    if (chosen === 'webgpu' && !detected.webgpu_ready) chosen = 'wasm';
    const key = `${model}|${chosen}`;
    if (this.pipelineCache.has(key)) return { pipeline: this.pipelineCache.get(key), device: chosen, model, cached_in_memory: true };

    const { pipeline } = await this.loadTransformers();
    this.emit('model-progress', { status: 'loading', model, device: chosen, progress: 0, message: 'Baixando/carregando refinador no navegador...' });
    const progress_callback = (p) => {
      const percent = typeof p?.progress === 'number' ? Math.round(p.progress) : null;
      this.emit('model-progress', {
        status: p?.status || 'loading', model, device: chosen, progress: percent,
        file: p?.file || null, loaded: p?.loaded || null, total: p?.total || null,
        message: p?.file ? `${p.status || 'carregando'} · ${p.file}${percent != null ? ` · ${percent}%` : ''}` : (p?.status || 'carregando'),
      });
    };

    try {
      const pipe = await pipeline('image-to-image', model, { device: chosen, progress_callback });
      this.pipelineCache.set(key, pipe);
      this.emit('model-progress', { status: 'ready', model, device: chosen, progress: 100, message: `Refinador pronto em ${chosen.toUpperCase()}.` });
      return { pipeline: pipe, device: chosen, model, cached_in_memory: false };
    } catch (err) {
      if (chosen === 'webgpu') {
        this.emit('model-progress', { status: 'fallback', model, device: 'wasm', message: `WebGPU falhou (${err?.message || err}). Tentando WASM...` });
        return await this.prepareRefiner({ device: 'wasm', model });
      }
      throw err;
    }
  }

  async refine(source, { device = 'auto', model = DEFAULT_MODEL, maxInputDimension = null, preserveOutputSize = true } = {}) {
    const originalBlob = await sourceToBlob(source);
    const original = await blobDimensions(originalBlob);
    const detected = this.lastDetection || await this.detect();
    let mode = device === 'auto' ? detected.recommended_mode : device;
    if (mode === 'webgpu' && !detected.webgpu_ready) mode = 'wasm';

    const recommendedMax = detected.profile === 'high' ? 512 : detected.profile === 'medium' ? 384 : 256;
    const inputMax = Number(maxInputDimension || recommendedMax);
    const prepared = await resizeBlob(originalBlob, inputMax);
    const { pipeline: pipe, device: effectiveDevice } = await this.prepareRefiner({ device: mode, model });
    const started = performance.now();
    this.emit('inference-progress', { status: 'running', message: `Refinando no navegador via ${effectiveDevice.toUpperCase()}...` });
    const raw = await pipe(prepared.blob);
    const output = Array.isArray(raw) ? raw[0] : raw;
    if (!output || !output.data || !output.width || !output.height) throw new Error('O modelo web não retornou uma imagem válida.');
    let canvas = rawImageToCanvas(output);

    if (preserveOutputSize && (canvas.width !== original.width || canvas.height !== original.height)) {
      const finalCanvas = document.createElement('canvas');
      finalCanvas.width = original.width;
      finalCanvas.height = original.height;
      const ctx = finalCanvas.getContext('2d', { alpha: false });
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(canvas, 0, 0, original.width, original.height);
      canvas = finalCanvas;
    }

    const encoded = await canvasToDataUrl(canvas);
    const durationMs = Math.round(performance.now() - started);
    const run = {
      id: `web_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      created_at: nowIso(),
      engine: 'browser',
      runtime: `transformers.js-${TRANSFORMERS_VERSION}`,
      model,
      device: effectiveDevice,
      webgpu: !!detected.webgpu_ready,
      profile: detected.profile,
      original_width: original.width,
      original_height: original.height,
      model_input_width: prepared.width,
      model_input_height: prepared.height,
      output_width: canvas.width,
      output_height: canvas.height,
      duration_ms: durationMs,
      note: 'MVP browser image-to-image (super-resolution/refino). Não é ainda o refinador generativo guiado definitivo.',
    };
    await saveRun(run).catch(() => {});
    this.lastResult = { ...run, dataUrl: encoded.dataUrl, blob: encoded.blob };
    this.emit('inference-progress', { status: 'done', message: `Refino concluído em ${durationMs} ms.`, run });
    return this.lastResult;
  }

  async cacheStatus() {
    const data = { available: 'caches' in window, cache_names: [], matching_entries: 0, estimated_bytes: 0 };
    if (!data.available) return data;
    const names = await caches.keys();
    data.cache_names = names;
    for (const name of names) {
      if (!/transform|hugging|onnx/i.test(name)) continue;
      const cache = await caches.open(name);
      const keys = await cache.keys();
      for (const req of keys) {
        if (!/swin2sr|transformers|onnx|huggingface/i.test(req.url)) continue;
        data.matching_entries += 1;
        const response = await cache.match(req);
        const len = Number(response?.headers?.get('content-length') || 0);
        if (len > 0) data.estimated_bytes += len;
      }
    }
    return data;
  }

  async clearModelCache() {
    if (!('caches' in window)) return { deleted: [] };
    const names = await caches.keys();
    const targets = names.filter((n) => /transform|hugging|onnx/i.test(n));
    const deleted = [];
    for (const n of targets) {
      if (await caches.delete(n)) deleted.push(n);
    }
    this.pipelineCache.clear();
    return { deleted };
  }

  async history(limit = 20) {
    return await listRuns(limit);
  }
}

export const browserRuntime = new CorvoBrowserRuntime();
export { DEFAULT_MODEL, TRANSFORMERS_VERSION };
