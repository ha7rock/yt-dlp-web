from pathlib import Path

APP_JS = Path(__file__).resolve().parents[1] / "static" / "app.js"


def test_history_preview_state_is_preserved_across_refreshes():
    js = APP_JS.read_text(encoding="utf-8")

    assert "openPreviewIds" in js
    assert "data-preview-id" in js
    assert "collectOpenPreviewIds" in js
    assert "restoreOpenPreviewIds" in js


def test_history_polling_skips_refresh_while_preview_is_open():
    js = APP_JS.read_text(encoding="utf-8")

    assert "hasOpenPreview()" in js
    assert "skip history refresh because preview is open" in js


def test_frontend_debug_log_helper_exists():
    js = APP_JS.read_text(encoding="utf-8")

    assert "debugLog(" in js
    assert "[yt-dlp-web]" in js


def test_download_polling_stops_when_no_active_jobs():
    js = APP_JS.read_text(encoding="utf-8")

    assert "activeJobs" in js
    assert "activeJobs.length === 0" in js
    assert "stop polling because no active jobs" in js
    assert "pollTimer = null" in js


def test_tasks_section_only_shows_active_downloads_and_refreshes_history_on_completion():
    js = APP_JS.read_text(encoding="utf-8")
    html = (APP_JS.parent / "index.html").read_text(encoding="utf-8")

    assert "正在下载" in html
    assert html.index('id="refreshJobs"') > html.index('id="jobs"') - 200
    assert "activeJobs = allJobs.filter" in js
    assert "暂无正在下载任务" in js
    assert "completedSinceLastPoll" in js
    assert "refresh history because a task finished" in js
    assert "loadHistory(1, {force: true})" in js


def test_ios_compatible_checkbox_exists_and_is_not_format_option():
    js = APP_JS.read_text(encoding="utf-8")
    html = (APP_JS.parent / "index.html").read_text(encoding="utf-8")

    assert 'id="iosCompatible"' in html
    assert 'value="ios"' not in html
    assert "iOS 兼容" in html
    assert "isYouTubeUrl" in js
    assert "updateIosCompatibleAvailability" in js
    assert "ios_compatible" in js
    assert "$('iosCompatible').disabled = !enabled" in js


def test_clipboard_button_has_ios_safari_manual_paste_fallback():
    js = APP_JS.read_text(encoding="utf-8")

    assert "当前浏览器不允许自动读取剪切板" in js
    assert "$('url').focus()" in js
    assert "$('url').select()" in js


def test_clipboard_button_and_frontend_url_extraction_exist():
    js = APP_JS.read_text(encoding="utf-8")
    html = (APP_JS.parent / "index.html").read_text(encoding="utf-8")

    assert "pasteClipboard" in html
    assert "navigator.clipboard.readText" in js
    assert "extractUrlFromInput" in js
