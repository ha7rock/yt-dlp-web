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

    assert "hasActiveJob" in js
    assert "['queued', 'running'].includes(j.status)" in js
    assert "stop polling because no active jobs" in js
    assert "pollTimer = null" in js


def test_clipboard_button_and_frontend_url_extraction_exist():
    js = APP_JS.read_text(encoding="utf-8")
    html = (APP_JS.parent / "index.html").read_text(encoding="utf-8")

    assert "pasteClipboard" in html
    assert "navigator.clipboard.readText" in js
    assert "extractUrlFromInput" in js
