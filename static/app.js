const $ = (id) => document.getElementById(id);
const statusEl = $('status');
let pollTimer = null;
let historyPage = 1;
let historyTotalPages = 1;
let openPreviewIds = new Set();

function debugLog(message, data = {}) {
  console.debug('[yt-dlp-web]', message, data);
}

function val(id) { return $(id).value.trim(); }
function checked(id) { return $(id).checked; }
function setStatus(msg) { statusEl.textContent = msg || ''; }

function extractUrlFromInput(raw) {
  const text = String(raw || '').trim();
  const match = text.match(/https?:\/\/[^\s\]）】>"'，。！？；、]+/);
  return match ? match[0].replace(/[.,，。!！?？;；)）\]】>]+$/, '') : text;
}

function normalizedUrl() {
  const url = extractUrlFromInput(val('url'));
  $('url').value = url;
  return url;
}

function payload() {
  return {
    url: normalizedUrl(),
    audio_only: checked('audioOnly'),
    quality: val('quality'),
    format: val('format'),
    merge_output_format: val('mergeOutputFormat'),
    audio_format: val('audioFormat'),
    write_subs: checked('writeSubs'),
    write_auto_subs: checked('writeAutoSubs'),
    embed_subs: checked('embedSubs'),
    sub_langs: val('subLangs'),
    embed_metadata: checked('embedMetadata'),
    write_thumbnail: checked('writeThumbnail'),
    embed_thumbnail: checked('embedThumbnail'),
    playlist: checked('playlist'),
    cookies_from_browser: checked('cookiesFromBrowser'),
    browser: val('browser'),
    rate_limit: val('rateLimit'),
    retries: val('retries'),
    extra_args: val('extraArgs'),
  };
}

async function postJSON(url, data) {
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || res.statusText);
  return body;
}

function humanSize(n) {
  if (!n) return '';
  const units = ['B','KB','MB','GB'];
  let i=0; while (n>=1024 && i<units.length-1) { n/=1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
}

$('pasteClipboard').onclick = async () => {
  try {
    const text = await navigator.clipboard.readText();
    $('url').value = extractUrlFromInput(text);
    debugLog('clipboard pasted', {rawLength: text.length, url: $('url').value});
  } catch (e) {
    $('url').focus();
    $('url').select();
    setStatus('当前浏览器不允许自动读取剪切板，请长按/⌘V 手动粘贴到输入框');
    debugLog('clipboard read failed', {error: e.message});
  }
};

$('probe').onclick = async () => {
  const info = $('info');
  info.classList.remove('hidden');
  info.textContent = '读取中...';
  try {
    const data = await postJSON('/api/info', {url: normalizedUrl()});
    const rows = (data.formats || []).slice(0, 80).map(f => {
      const label = `${f.format_id} · ${f.resolution || ''} · ${f.ext || ''} · ${f.note || ''} ${humanSize(f.filesize)}`;
      return `<option value="${f.format_id}">${label}</option>`;
    }).join('');
    $('format').insertAdjacentHTML('beforeend', `<optgroup label="源站格式">${rows}</optgroup>`);
    info.innerHTML = `<b>${data.title || '已读取'}</b><br>来源：${data.extractor || '-'} ｜ 时长：${data.duration || '-'} 秒<br>可选格式：${(data.formats || []).length} 个`;
  } catch (e) {
    info.textContent = '读取失败：' + e.message;
  }
};

$('download').onclick = async () => {
  setStatus('提交中...');
  try {
    const data = await postJSON('/api/download', payload());
    setStatus(`任务已开始：${data.job.id}`);
    await loadJobs();
    await loadHistory();
    startPolling();
  } catch (e) {
    setStatus('失败：' + e.message);
  }
};

$('refreshJobs').onclick = loadJobs;
$('refreshHistory').onclick = () => loadHistory(historyPage, {force: true});
$('prevHistory').onclick = () => { if (historyPage > 1) loadHistory(historyPage - 1, {force: true}); };
$('nextHistory').onclick = () => { if (historyPage < historyTotalPages) loadHistory(historyPage + 1, {force: true}); };

async function loadJobs() {
  const res = await fetch('/api/jobs', {cache:'no-store'});
  const data = await res.json();
  const allJobs = data.jobs || [];
  const activeJobs = allJobs.filter(j => ['queued', 'running'].includes(j.status));
  const html = activeJobs.map(j => {
    const cls = ['badge', j.status].join(' ');
    const files = (j.files || []).map(f => `<div>${escapeHtml(f)}</div>`).join('');
    const log = (j.log || []).slice(-80).join('\n');
    const progress = j.progress || {percent: 0, label: j.status || '等待中'};
    const percent = Math.max(0, Math.min(100, Number(progress.percent || 0)));
    const progressLabel = progress.label || `${percent.toFixed(1)}%`;
    return `<div class="job">
      <div class="job-head"><b>${j.id}</b><span class="${cls}">${j.status}</span></div>
      <p>${escapeHtml(j.url)}</p>
      <div class="progress-wrap" aria-label="下载进度">
        <div class="progress-meta"><span>${escapeHtml(progress.stage || '')}</span><span>${escapeHtml(progressLabel)}</span></div>
        <div class="progress"><div class="progress-bar ${j.status}" style="width:${percent}%"></div></div>
      </div>
      <p>保存目录：<code>${escapeHtml(j.output_dir)}</code></p>
      ${files ? `<div class="files">新文件：${files}</div>` : ''}
      <details class="log-details"><summary>查看日志</summary><div class="log">${escapeHtml(log)}</div></details>
    </div>`;
  }).join('') || '<p>暂无正在下载任务</p>';
  $('jobs').innerHTML = html;
  return {allJobs, activeJobs};
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[ch]));
}

function formatDate(ts) {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

function previewHtml(item) {
  if (!item.previewable) return '<span class="muted">不可预览</span>';
  const url = escapeHtml(item.preview_url);
  if ((item.mime || '').startsWith('video/')) {
    return `<video class="preview" controls preload="metadata" src="${url}"></video>`;
  }
  if ((item.mime || '').startsWith('audio/')) {
    return `<audio class="preview-audio" controls preload="metadata" src="${url}"></audio>`;
  }
  return '<span class="muted">不可预览</span>';
}

function collectOpenPreviewIds() {
  openPreviewIds = new Set([...document.querySelectorAll('.preview-box[open][data-preview-id]')].map(el => el.dataset.previewId));
  return openPreviewIds;
}

function restoreOpenPreviewIds() {
  openPreviewIds.forEach(id => {
    const el = document.querySelector(`.preview-box[data-preview-id="${CSS.escape(id)}"]`);
    if (el) el.open = true;
  });
}

function hasOpenPreview() {
  collectOpenPreviewIds();
  return openPreviewIds.size > 0;
}

async function loadHistory(page = 1, options = {}) {
  const force = Boolean(options.force);
  if (!force && hasOpenPreview()) {
    debugLog('skip history refresh because preview is open', {page, openPreviewIds: [...openPreviewIds]});
    return;
  }
  collectOpenPreviewIds();
  debugLog('load history', {page, force, openPreviewIds: [...openPreviewIds]});
  const res = await fetch(`/api/history?page=${page}&per_page=10`, {cache:'no-store'});
  const data = await res.json();
  historyPage = data.page || 1;
  historyTotalPages = Math.max(1, data.total_pages || 1);
  const items = data.items || [];
  $('history').innerHTML = items.map(item => `
    <div class="history-item">
      <div class="history-main">
        <div class="history-title">${escapeHtml(item.title)}</div>
        <div class="history-meta">${humanSize(item.size)} · ${escapeHtml(item.mime)} · ${formatDate(item.mtime)}</div>
        <div class="history-url">${escapeHtml(item.url)}</div>
        <div class="history-actions">
          <a class="btn-link" href="${escapeHtml(item.download_url)}">下载</a>
          <button class="danger" data-delete="${escapeHtml(item.id)}">删除</button>
        </div>
      </div>
      <details class="preview-box" data-preview-id="${escapeHtml(item.id)}"><summary>预览</summary>${previewHtml(item)}</details>
    </div>`).join('') || '<p>暂无历史下载</p>';
  restoreOpenPreviewIds();
  document.querySelectorAll('.preview-box[data-preview-id]').forEach(box => {
    box.addEventListener('toggle', () => {
      collectOpenPreviewIds();
      debugLog('preview toggled', {id: box.dataset.previewId, open: box.open, openPreviewIds: [...openPreviewIds]});
    });
  });
  $('historyPage').textContent = `第 ${historyPage} / ${historyTotalPages} 页，共 ${data.total || 0} 条`;
  $('prevHistory').disabled = historyPage <= 1;
  $('nextHistory').disabled = historyPage >= historyTotalPages;
  document.querySelectorAll('[data-delete]').forEach(btn => {
    btn.onclick = async () => {
      if (!confirm('确认删除这个文件吗？')) return;
      try {
        await postJSON('/api/history/delete', {id: btn.dataset.delete});
        await loadHistory(historyPage, {force: true});
      } catch (e) {
        alert('删除失败：' + e.message);
      }
    };
  });
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  let previousActiveIds = new Set();
  pollTimer = setInterval(async () => {
    const {activeJobs} = await loadJobs();
    const activeIds = new Set(activeJobs.map(j => j.id));
    const completedSinceLastPoll = [...previousActiveIds].some(id => !activeIds.has(id));
    if (completedSinceLastPoll) {
      await loadHistory(1, {force: true});
      debugLog('refresh history because a task finished');
    }
    previousActiveIds = activeIds;
    if (activeJobs.length === 0) {
      clearInterval(pollTimer);
      pollTimer = null;
      await loadHistory(1, {force: true});
      debugLog('stop polling because no active jobs');
    }
  }, 2000);
}

loadJobs();
loadHistory();
