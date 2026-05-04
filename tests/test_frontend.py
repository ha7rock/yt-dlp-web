from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "static" / "app.js"
INDEX = ROOT / "static" / "index.html"


def test_redesigned_frontend_uses_handoff_structure_and_tokens():
    html = INDEX.read_text(encoding="utf-8")

    assert 'class="topbar"' in html
    assert 'class="url-panel"' in html
    assert 'id="previewStrip"' in html
    assert 'id="activeList"' in html
    assert 'id="historyList"' in html
    assert 'id="toastWrap"' in html
    assert "--accent: oklch(68% 0.22 28)" in html
    assert "--radius-xl: 28px" in html
    assert "@keyframes shimmer" in html
    assert "@keyframes fadeSlideIn" in html


def test_theme_toggle_persists_to_local_storage():
    js = APP_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="themeToggle"' in html
    assert "localStorage.getItem('theme')" in js
    assert "localStorage.setItem('theme'" in js
    assert "data-theme" in js


def test_url_parse_and_download_buttons_call_apis():
    js = APP_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="url"' in html
    assert 'id="probe"' in html
    assert 'id="download"' in html
    assert "/api/info" in js
    assert "/api/download" in js
    assert "POST" in js


def test_settings_match_readme_fields_and_advanced_panel():
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="quality"' in html
    assert 'id="mergeOutputFormat"' in html
    assert 'id="audioFormat"' in html
    assert 'id="audioOnly"' in html
    assert 'id="iosCompatible"' in html
    assert 'id="playlist"' in html
    assert 'id="advPanel"' in html
    assert 'id="subLangs"' in html
    assert 'id="rateLimit"' in html
    assert 'id="retries"' in html
    assert 'id="extraArgs"' in html


def test_progress_polling_and_completion_refresh_history():
    js = APP_JS.read_text(encoding="utf-8")

    assert "setInterval" in js
    assert "/api/jobs" in js
    assert "loadHistory(1)" in js
    assert "renderJobs" in js


def test_history_search_pagination_and_delete_apis():
    js = APP_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="searchInput"' in html
    assert 'id="pagination"' in html
    assert "/api/history" in js
    assert "/api/history/delete" in js
    assert "deleteItem" in js


def test_mobile_breakpoints_from_readme_exist():
    html = INDEX.read_text(encoding="utf-8")

    assert "@media (max-width: 600px)" in html
    assert "@media (max-width: 400px)" in html
    assert "max-width: 800px" in html


def test_frontend_extracts_app_share_text_and_ios_toggle_is_youtube_scoped():
    js = APP_JS.read_text(encoding="utf-8")

    assert "extractUrl" in js
    assert "isYouTubeUrl" in js
    assert "iosCompatible" in js
    assert "ios_compatible" in js
    assert "disabled" in js


def test_toggle_chips_do_not_double_toggle_hidden_checkbox():
    js = APP_JS.read_text(encoding="utf-8")

    assert "cb.addEventListener('change'" in js
    assert "el.addEventListener('click'" not in js


def test_player_modal_supports_video_preview_and_actions():
    js = APP_JS.read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    assert 'id="playerModal"' in html
    assert 'id="playerVideo"' in html
    assert 'id="playerThumbBg"' in html
    assert 'id="playerOpenBtn"' in html
    assert 'id="playerDownloadBtn"' in html
    assert "openPlayer" in js
    assert "preview_url" in js
    assert "object-fit: contain" in html


def test_progress_bar_shimmer_and_backend_tick_remain_smooth():
    app_py = (ROOT / "app.py").read_text(encoding="utf-8")
    html = INDEX.read_text(encoding="utf-8")

    assert "time.sleep(0.25)" in app_py
    assert ".dl-progress-bar" in html
    assert "shimmer" in html
