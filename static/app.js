/* ── Helpers ─────────────────────────────────────────────── */
function $(id) { return document.getElementById(id); }
function val(id) { return ($(id) && $(id).value) ? $(id).value.trim() : ''; }
function checked(id) { return $(id) ? $(id).checked : false; }

function toast(msg, type) {
  const wrap = $('toastWrap');
  const el = document.createElement('div');
  el.className = 'toast' + (type ? ` ${type}` : '');
  el.textContent = msg;
  wrap.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }, 2800);
}

function humanSize(n) {
  if (!n) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
}

function formatDate(ts) {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit', year: 'numeric' });
}

function extractUrl(raw) {
  const text = String(raw || '').trim();
  const match = text.match(/https?:\/\/[^\s\]）】>"'，。！？；、]+/);
  return match ? match[0].replace(/[.,，。!！?？;；)）\]】>]+$/, '') : text;
}

function isYouTubeUrl(url) {
  try {
    const host = new URL(extractUrl(url)).hostname.toLowerCase();
    return ['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'music.youtube.com'].includes(host);
  } catch (_) { return false; }
}

async function postJSON(url, data) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || res.statusText);
  return body;
}

/* ── Theme ─────────────────────────────────────────────── */
let themeMode = localStorage.getItem('theme') || 'system';
const sysDarkMQ = window.matchMedia('(prefers-color-scheme: dark)');

function applyTheme() {
  const isDark = themeMode === 'dark' || (themeMode === 'system' && sysDarkMQ.matches);
  document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
  $('iconMoon').style.display = themeMode === 'dark' ? 'block' : 'none';
  $('iconSun').style.display = themeMode === 'light' ? 'block' : 'none';
  $('iconAuto').style.display = themeMode === 'system' ? 'block' : 'none';
  const titles = { light: '当前：浅色 — 点击切换到深色', dark: '当前：深色 — 点击跟随系统', system: '当前：跟随系统 — 点击切换到浅色' };
  $('themeToggle').title = titles[themeMode] || '切换主题';
  localStorage.setItem('theme', themeMode);
}
applyTheme();
sysDarkMQ.addEventListener('change', () => { if (themeMode === 'system') applyTheme(); });
$('themeToggle').addEventListener('click', () => {
  themeMode = { light: 'dark', dark: 'system', system: 'light' }[themeMode] || 'system';
  applyTheme();
});

/* ── URL Input ─────────────────────────────────────────── */
const urlInput = $('url');
const urlClear = $('urlClear');

urlInput.addEventListener('input', () => {
  urlClear.classList.toggle('visible', urlInput.value.length > 0);
  updateIosChip();
});
urlClear.addEventListener('click', () => {
  urlInput.value = '';
  urlClear.classList.remove('visible');
  $('previewStrip').classList.remove('visible');
  $('previewThumb').innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
  resetFormatSelect();
  updateIosChip();
});

const clipboardReadable = !!(window.isSecureContext && navigator.clipboard && navigator.clipboard.readText);
if (!clipboardReadable) {
  $('urlPaste').classList.add('disabled');
  $('urlPaste').title = window.isSecureContext
    ? '当前浏览器不支持读取剪贴板，请用 Ctrl/⌘+V 粘贴'
    : '需要 https 或 localhost 才能读剪贴板，请用 Ctrl/⌘+V 粘贴';
}
$('urlPaste').addEventListener('click', async () => {
  if (!clipboardReadable) {
    toast(window.isSecureContext ? '浏览器禁用了剪贴板读取' : '请改用 https 或 localhost 访问', 'error');
    urlInput.focus();
    return;
  }
  try {
    const raw = await navigator.clipboard.readText();
    const text = (raw || '').trim();
    if (!text) { toast('剪贴板为空', 'error'); return; }
    const url = extractUrl(text);
    if (!/^https?:\/\//i.test(url)) {
      toast('剪贴板里没有有效链接', 'error');
      return;
    }
    urlInput.value = url;
    urlInput.dispatchEvent(new Event('input'));
    urlInput.focus();
    toast('已粘贴链接', 'success');
  } catch (e) {
    toast('无法读取剪贴板：' + (e.message || e), 'error');
  }
});

function updateIosChip() {
  const isYT = isYouTubeUrl(urlInput.value);
  const chip = $('chipIOS');
  const cb = $('iosCompatible');
  chip.classList.toggle('disabled', !isYT);
  cb.disabled = !isYT;
  if (!isYT) { cb.checked = false; chip.classList.remove('on'); }
}

/* ── Toggle Chips ── */
['chipAudioOnly', 'chipIOS', 'chipPlaylist', 'chipSubs', 'chipAutoSubs', 'chipEmbedSubs', 'chipMeta', 'chipThumb', 'chipCookies'].forEach(id => {
  const chip = $(id);
  if (!chip) return;
  const cb = chip.querySelector('input');
  if (!cb) return;
  cb.addEventListener('change', () => chip.classList.toggle('on', cb.checked));
});

/* ── Advanced Panel ── */
$('advToggle').addEventListener('click', () => {
  const open = $('advPanel').classList.toggle('open');
  $('advToggle').classList.toggle('open', open);
});

/* ── More Menu ── */
function toggleMore(btn) {
  const menu = btn.nextElementSibling;
  const isOpen = menu.classList.contains('open');
  closeMore();
  if (!isOpen) menu.classList.add('open');
}
function closeMore() {
  document.querySelectorAll('.hist-more-menu.open').forEach(m => m.classList.remove('open'));
}
document.addEventListener('click', e => { if (!e.target.closest('.hist-more-wrap')) closeMore(); });

/* ── Probe / Fetch Info ─────────────────────────────────── */
$('probe').addEventListener('click', async () => {
  const url = extractUrl(urlInput.value);
  if (!url) { toast('请先粘贴视频链接', 'error'); return; }
  urlInput.value = url;

  const btn = $('probe');
  btn.textContent = '解析中…';
  btn.classList.add('loading');

  const strip = $('previewStrip');
  strip.classList.add('visible');
  $('previewTitle').textContent = '解析中…';
  $('previewMeta').textContent = '';

  try {
    const data = await postJSON('/api/info', { url });

    // Thumbnail
    if (data.thumbnail) {
      $('previewThumb').innerHTML = `<img src="${escHtml(data.thumbnail)}" alt="" referrerpolicy="no-referrer" onerror="this.parentElement.innerHTML='<svg width=24 height=24 viewBox=\\'0 0 24 24\\' fill=none stroke=currentColor stroke-width=1.5><polygon points=\\'5 3 19 12 5 21 5 3\\'/></svg>'">`;
    }
    $('previewTitle').textContent = data.title || url;
    const parts = [];
    if (data.extractor) parts.push(data.extractor);
    if (data.duration) parts.push(fmtDuration(data.duration));
    if (data.formats) parts.push(`${data.formats.length} 个格式`);
    $('previewMeta').textContent = parts.join(' · ');

    // Populate format select
    if (data.formats && data.formats.length > 0) {
      buildFormatSelect(data.formats);
    }
    toast('解析成功', 'success');
  } catch (e) {
    $('previewTitle').textContent = '解析失败';
    $('previewMeta').textContent = e.message;
    toast('解析失败：' + e.message, 'error');
  } finally {
    btn.textContent = '解析';
    btn.classList.remove('loading');
  }
});

function fmtDuration(secs) {
  if (!secs) return '';
  const m = Math.floor(secs / 60), s = secs % 60;
  return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
}

function buildFormatSelect(formats) {
  const sel = $('format');
  // Remove previously added optgroups
  sel.querySelectorAll('optgroup').forEach(g => g.remove());
  const rows = formats.slice(0, 80).map(f => {
    const label = [f.format_id, f.resolution || '', f.ext || '', f.note || '', humanSize(f.filesize)].filter(Boolean).join(' · ');
    return `<option value="${escHtml(f.format_id)}">${escHtml(label)}</option>`;
  }).join('');
  sel.insertAdjacentHTML('beforeend', `<optgroup label="源站格式">${rows}</optgroup>`);
  $('formatsRow').style.display = 'flex';
  const hint = $('formatsHint');
  if (hint) hint.style.display = 'none';
  // Open advanced panel if not already open
  if (!$('advPanel').classList.contains('open')) {
    $('advPanel').classList.add('open');
    $('advToggle').classList.add('open');
  }
}

function resetFormatSelect() {
  const sel = $('format');
  if (sel) sel.querySelectorAll('optgroup').forEach(g => g.remove());
  $('formatsRow').style.display = 'none';
  const hint = $('formatsHint');
  if (hint) hint.style.display = '';
}

/* ── Download ─────────────────────────────────────────────── */
$('download').addEventListener('click', async () => {
  const url = extractUrl(urlInput.value);
  if (!url) { toast('请先粘贴视频链接', 'error'); return; }
  urlInput.value = url;

  const btn = $('download');
  btn.classList.add('loading');

  try {
    const payload = {
      url,
      audio_only: checked('audioOnly'),
      quality: val('quality'),
      format: val('format') || 'bv*+ba/b',
      ios_compatible: checked('iosCompatible') && isYouTubeUrl(url),
      merge_output_format: val('mergeOutputFormat'),
      audio_format: val('audioFormat'),
      write_subs: checked('writeSubs'),
      write_auto_subs: checked('writeAutoSubs'),
      embed_subs: checked('embedSubs'),
      sub_langs: val('subLangs'),
      embed_metadata: checked('embedMetadata'),
      write_thumbnail: false,
      embed_thumbnail: checked('embedThumbnail'),
      playlist: checked('playlist'),
      cookies_from_browser: checked('cookiesFromBrowser'),
      browser: 'chrome',
      rate_limit: val('rateLimit'),
      retries: val('retries'),
      extra_args: val('extraArgs'),
    };
    await postJSON('/api/download', payload);
    toast('下载任务已开始', 'success');
    startPolling();
  } catch (e) {
    toast('提交失败：' + e.message, 'error');
  } finally {
    btn.classList.remove('loading');
  }
});

/* ── Jobs Polling ─────────────────────────────────────────── */
let pollTimer = null;
let prevJobs = new Map();
const jobCards = new Map();

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(pollJobs, 1500);
  pollJobs();
}

async function pollJobs() {
  const { allJobs, activeJobs } = await loadJobs();
  const currentIds = new Set(activeJobs.map(j => j.id));
  const finishedIds = [...prevJobs.keys()].filter(id => !currentIds.has(id));
  if (finishedIds.length) {
    const finishedJobs = allJobs.filter(j => finishedIds.includes(j.id));
    const someDone = finishedJobs.some(j => j.status === 'done');
    const currentUrl = extractUrl(urlInput.value);
    if (someDone && currentUrl && finishedJobs.some(j => j.status === 'done' && j.url === currentUrl)) {
      clearUrlInput();
    }
    if (someDone) toast('下载完成', 'success');
    const failed = finishedJobs.filter(j => j.status === 'failed');
    if (failed.length) toast('下载失败：' + (failed[0].title || failed[0].url || ''), 'error');
    loadHistory(historyPage);
  }
  prevJobs = new Map(activeJobs.map(j => [j.id, j]));
  if (activeJobs.length === 0) {
    clearInterval(pollTimer);
    pollTimer = null;
    loadHistory(1);
  }
}

async function loadJobs() {
  try {
    const res = await fetch('/api/jobs', { cache: 'no-store' });
    const data = await res.json();
    const all = data.jobs || [];
    const active = all.filter(j => ['queued', 'running'].includes(j.status));
    renderJobs(active);
    return { allJobs: all, activeJobs: active };
  } catch (_) { return { allJobs: [], activeJobs: [] }; }
}

function clearUrlInput() {
  urlInput.value = '';
  urlClear.classList.remove('visible');
  $('previewStrip').classList.remove('visible');
  $('previewThumb').innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
  resetFormatSelect();
  updateIosChip();
}

function renderJobs(jobs) {
  const el = $('activeList');
  if (jobs.length === 0) {
    if (jobCards.size > 0) {
      jobCards.forEach(c => c.remove());
      jobCards.clear();
    }
    if (!el.querySelector('.empty-state')) {
      el.innerHTML = `<div class="empty-state">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M8 12l3 3 5-5"/></svg>
        <p>暂无进行中的下载</p></div>`;
    }
    return;
  }
  const empty = el.querySelector('.empty-state');
  if (empty) empty.remove();

  const seen = new Set();
  jobs.forEach(j => {
    seen.add(j.id);
    let card = jobCards.get(j.id);
    if (!card) {
      card = createJobCard(j);
      jobCards.set(j.id, card);
      el.appendChild(card);
    }
    updateJobCard(card, j);
  });
  for (const [id, card] of jobCards) {
    if (!seen.has(id)) { card.remove(); jobCards.delete(id); }
  }
}

function createJobCard(j) {
  const card = document.createElement('div');
  card.className = 'dl-card';
  card.dataset.task = j.id;
  card.innerHTML = `
    <div class="dl-card-top">
      <img class="dl-card-thumb" alt="" referrerpolicy="no-referrer" data-thumb style="display:none">
      <div class="dl-card-info">
        <div class="dl-card-title" data-title></div>
        <div class="dl-card-meta">
          <span class="dl-badge" data-badge></span>
          <span class="dl-meta-tag" data-id></span>
        </div>
      </div>
      <button class="dl-cancel" data-cancel title="取消下载">取消</button>
    </div>
    <div class="dl-progress-area">
      <div class="dl-progress-bar-wrap"><div class="dl-progress-bar" data-bar style="width:0%"></div></div>
      <div class="dl-progress-info">
        <span class="dl-progress-pct" data-pct></span>
        <span class="dl-progress-speed" data-speed></span>
      </div>
    </div>
    <button class="dl-log-toggle" data-log-toggle style="display:none">查看日志</button>
    <pre class="dl-log" data-log></pre>`;
  card.querySelector('[data-cancel]').addEventListener('click', () => cancelJob(j.id, card));
  card.querySelector('[data-log-toggle]').addEventListener('click', () => {
    card.querySelector('[data-log]').classList.toggle('open');
  });
  return card;
}

function updateJobCard(card, j) {
  const prog = j.progress || {};
  const pct = Math.max(0, Math.min(100, Number(prog.percent || 0)));
  const label = prog.label || (j.status === 'queued' ? '等待中' : `${pct.toFixed(1)}%`);
  const speed = [prog.speed, prog.eta ? `剩余 ${prog.eta}` : ''].filter(Boolean).join(' · ');
  const shortUrl = j.url.length > 60 ? j.url.slice(0, 60) + '…' : j.url;
  const titleText = j.title || shortUrl;

  const thumb = card.querySelector('[data-thumb]');
  if (j.thumbnail_url && thumb.getAttribute('src') !== j.thumbnail_url) {
    thumb.src = j.thumbnail_url;
    thumb.style.display = 'block';
    thumb.onerror = () => { thumb.style.display = 'none'; };
  } else if (!j.thumbnail_url && thumb.style.display !== 'none') {
    thumb.style.display = 'none';
  }

  const titleEl = card.querySelector('[data-title]');
  if (titleEl.textContent !== titleText) titleEl.textContent = titleText;

  const badge = card.querySelector('[data-badge]');
  const badgeText = j.status === 'queued' ? '等待' : j.status === 'running' ? '下载中' : j.status;
  if (badge.textContent !== badgeText) {
    badge.textContent = badgeText;
    badge.className = `dl-badge ${j.status}`;
  }
  const idEl = card.querySelector('[data-id]');
  if (idEl.textContent !== j.id) idEl.textContent = j.id;

  const bar = card.querySelector('[data-bar]');
  bar.style.width = `${pct}%`;

  const pctEl = card.querySelector('[data-pct]');
  if (pctEl.textContent !== label) pctEl.textContent = label;
  const speedEl = card.querySelector('[data-speed]');
  if (speedEl.textContent !== speed) speedEl.textContent = speed;

  const logText = (j.log || []).slice(-30).join('\n');
  const logEl = card.querySelector('[data-log]');
  const toggle = card.querySelector('[data-log-toggle]');
  if (logText) {
    if (logEl.textContent !== logText) {
      const wasOpen = logEl.classList.contains('open');
      const atBottom = logEl.scrollTop + logEl.clientHeight >= logEl.scrollHeight - 4;
      logEl.textContent = logText;
      if (wasOpen && atBottom) logEl.scrollTop = logEl.scrollHeight;
    }
    toggle.style.display = '';
  } else {
    toggle.style.display = 'none';
  }
}

async function cancelJob(taskId, card) {
  const btn = card.querySelector('[data-cancel]');
  btn.disabled = true;
  btn.textContent = '取消中…';
  try {
    const res = await fetch(`/api/download/${encodeURIComponent(taskId)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
    toast('已取消', 'success');
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '取消';
    toast('取消失败：' + e.message, 'error');
  }
}

/* ── History ─────────────────────────────────────────────── */
let historyPage = 1;
let historyTotalPages = 1;
let searchQuery = '';
let historyItems = [];

async function loadHistory(page) {
  page = page || historyPage;
  try {
    const params = new URLSearchParams({ page: String(page), per_page: '7' });
    if (searchQuery) params.set('q', searchQuery);
    const res = await fetch(`/api/history?${params.toString()}`, { cache: 'no-store' });
    const data = await res.json();
    historyPage = data.page || 1;
    historyTotalPages = Math.max(1, data.total_pages || 1);
    historyItems = data.items || [];
    renderHistory();
  } catch (_) {}
}

function renderHistory() {
  const list = $('historyList');
  const items = historyItems;

  if (items.length === 0) {
    list.innerHTML = `<div class="empty-state">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
      <p>暂无历史下载</p></div>`;
    renderPagination();
    return;
  }

  list.innerHTML = items.map((item, i) => {
    const mime = item.mime || '';
    const isVideo = mime.startsWith('video/');
    const ext = (mime.split('/')[1] || item.title.split('.').pop() || '').toUpperCase();
    const dateStr = formatDate(item.mtime);
    const sizeStr = humanSize(item.size);
    const thumbInner = item.thumbnail_url
      ? `<img src="${escHtml(item.thumbnail_url)}" alt="" referrerpolicy="no-referrer" style="width:100%;height:100%;object-fit:cover;display:block" onerror="this.outerHTML='<svg width=16 height=16 viewBox=\\'0 0 24 24\\' fill=none stroke=currentColor stroke-width=1.5 opacity=0.25><polygon points=\\'5 3 19 12 5 21 5 3\\'/></svg>'">`
      : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.25"><polygon points="5 3 19 12 5 21 5 3"/></svg>`;
    return `<div class="hist-item" data-idx="${i}">
      <div class="hist-thumb" onclick="openPlayer(${i})" title="播放预览">
        <div class="hist-thumb-inner">${thumbInner}</div>
        <div class="hist-play-btn"><svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg></div>
      </div>
      <div class="hist-body">
        <div class="hist-title" title="${escHtml(item.title)}">${escHtml(item.title)}</div>
        <div class="hist-filename">${escHtml(item.title)}</div>
        <div class="hist-tags">
          <span class="hist-tag size">${sizeStr}</span>
          ${ext ? `<span class="hist-tag">${escHtml(ext)}</span>` : ''}
          <span class="hist-tag date">${dateStr}</span>
        </div>
        <div class="hist-url-row">
          <div class="hist-url">${escHtml(item.url || '')}</div>
        </div>
      </div>
      <div class="hist-actions">
        <div class="hist-more-wrap">
          <button class="hist-action" title="更多操作" onclick="toggleMore(this)" aria-label="更多">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg>
          </button>
          <div class="hist-more-menu">
            ${item.previewable ? `<button class="more-item" onclick="openPlayer(${i});closeMore()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              播放
            </button>` : ''}
            <button class="more-item" onclick="downloadFile(${i});closeMore()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              下载到本机
            </button>
            <button class="more-item" onclick="copyUrl(${i});closeMore()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
              复制链接
            </button>
            <button class="more-item" onclick="toggleExpand(this.closest('.hist-item'));closeMore()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              查看来源链接
            </button>
            <div class="more-divider"></div>
            <button class="more-item danger" onclick="deleteItem(${i});closeMore()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
              删除文件
            </button>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');

  renderPagination();
}

function renderPagination() {
  const pg = $('pagination');
  if (historyTotalPages <= 1) { pg.innerHTML = ''; return; }
  let html = `<button class="page-btn" onclick="gotoPage(${historyPage - 1})" ${historyPage === 1 ? 'disabled' : ''}>← 上页</button>`;
  for (let i = 1; i <= historyTotalPages; i++) {
    html += `<button class="page-btn ${i === historyPage ? 'active' : ''}" onclick="gotoPage(${i})">${i}</button>`;
  }
  html += `<button class="page-btn" onclick="gotoPage(${historyPage + 1})" ${historyPage === historyTotalPages ? 'disabled' : ''}>下页 →</button>`;
  pg.innerHTML = html;
}

function gotoPage(n) {
  if (n < 1 || n > historyTotalPages) return;
  loadHistory(n);
}

/* ── History Actions ── */
function toggleExpand(item) { item && item.classList.toggle('expanded'); }

async function deleteItem(idx) {
  const item = historyItems[idx];
  if (!item) return;
  if (!confirm(`确认删除文件？\n${item.title}`)) return;
  try {
    await postJSON('/api/history/delete', { id: item.id });
    toast('已删除', 'success');
    await loadHistory(historyPage);
  } catch (e) {
    toast('删除失败：' + e.message, 'error');
  }
}

function downloadFile(idx) {
  const item = historyItems[idx];
  if (!item || !item.download_url) return;
  const a = document.createElement('a');
  a.href = item.download_url;
  a.download = item.title;
  a.click();
  toast('开始下载：' + item.title, 'success');
}

function legacyCopy(text) {
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch (_) { return false; }
}

function copyUrl(idx) {
  const item = historyItems[idx];
  if (!item || !item.url) return;
  const text = item.url;
  const onOk = () => toast('链接已复制', 'success');
  const onFail = () => {
    if (legacyCopy(text)) onOk();
    else toast('复制失败，请手动复制', 'error');
  };
  if (window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(onOk, onFail);
  } else {
    if (legacyCopy(text)) onOk();
    else toast('当前环境不支持自动复制', 'error');
  }
}

/* ── Player Modal ── */
function openPlayer(idx) {
  const item = historyItems[idx];
  if (!item) return;

  $('playerTitle').textContent = item.title;
  $('playerMeta').innerHTML = [
    item.mime ? `<span>${escHtml(item.mime)}</span>` : '',
    humanSize(item.size) ? `<span>${humanSize(item.size)}</span>` : '',
    formatDate(item.mtime) ? `<span>${formatDate(item.mtime)}</span>` : '',
  ].join('');
  $('playerPath').textContent = item.path || item.title;

  const video = $('playerVideo');
  const thumbBg = $('playerThumbBg');

  // Reset video state to avoid iOS Safari carrying over a stale "paused-while-playing" UI.
  try { video.pause(); } catch (_) {}
  video.removeAttribute('src');
  video.removeAttribute('poster');
  video.load();

  if (item.previewable && item.preview_url) {
    if (item.thumbnail_url) video.poster = item.thumbnail_url;
    video.src = item.preview_url;
    video.style.display = 'block';
    thumbBg.style.display = 'none';
  } else {
    video.style.display = 'none';
    thumbBg.style.display = 'flex';
    thumbBg.innerHTML = item.thumbnail_url
      ? `<img src="${escHtml(item.thumbnail_url)}" alt="" referrerpolicy="no-referrer" style="width:100%;height:100%;object-fit:cover" onerror="this.remove()">`
      : `<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.15"><polygon points="5 3 19 12 5 21 5 3"/></svg>`;
  }

  $('playerOpenBtn').onclick = () => {
    if (item.preview_url) {
      window.open(item.preview_url, '_blank');
    }
    toast('正在打开…', '');
  };
  $('playerDownloadBtn').onclick = () => downloadFile(idx);

  $('playerModal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closePlayerBtn() {
  $('playerModal').classList.remove('open');
  document.body.style.overflow = '';
  const video = $('playerVideo');
  if (video) { video.pause(); video.src = ''; }
}
function closePlayerOverlay(e) {
  if (e.target === $('playerModal')) closePlayerBtn();
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closePlayerBtn(); });

/* ── Search ── */
let searchDebounce = null;
$('searchInput').addEventListener('input', e => {
  searchQuery = e.target.value.trim();
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => loadHistory(1), 220);
});

/* ── Escape HTML ── */
function escHtml(s) {
  return String(s || '').replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[ch]));
}

/* ── Init ── */
loadJobs().then(({ activeJobs }) => {
  if (activeJobs.length > 0) {
    prevActiveIds = new Set(activeJobs.map(j => j.id));
    startPolling();
  }
});
loadHistory(1);
updateIosChip();
