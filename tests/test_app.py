import os
from pathlib import Path

import pytest

from app import (
    classify_url,
    build_yt_dlp_command,
    safe_job_id,
    parse_progress_line,
    normalize_input_url,
    Job,
    record_history_for_job,
    list_history,
    resolve_media_path,
    delete_history_item,
)


def test_classify_url_routes_known_sites_to_expected_download_folders(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    assert classify_url("https://x.com/someone/status/123").name == "x-videos"
    assert classify_url("https://twitter.com/someone/status/123").name == "x-videos"
    assert classify_url("https://www.youtube.com/watch?v=abc").name == "youtube-videos"
    assert classify_url("https://youtu.be/abc").name == "youtube-videos"
    assert classify_url("https://www.bilibili.com/video/BV123").name == "bilibili-videos"
    assert classify_url("https://example.com/video").name == "yt-dlp-videos"


def test_normalize_input_url_extracts_url_from_app_share_text():
    raw = "【爱是一万次的春和景明，小乖永远幸福下去吧-哔哩哔哩】 https://b23.tv/0nlH5Oy"

    assert normalize_input_url(raw) == "https://b23.tv/0nlH5Oy"


def test_normalize_input_url_strips_trailing_punctuation():
    assert normalize_input_url("看看这个 https://www.bilibili.com/video/BV123，") == "https://www.bilibili.com/video/BV123"


def test_build_command_uses_selected_format_quality_and_output_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cmd, output_dir = build_yt_dlp_command({
        "url": "分享给你 https://www.youtube.com/watch?v=abc",
        "format": "bv*+ba/b",
        "quality": "1080",
        "merge_output_format": "mp4",
        "write_subs": True,
        "write_auto_subs": True,
        "sub_langs": "zh-Hans,en",
        "embed_metadata": True,
        "extra_args": "--no-mtime --restrict-filenames",
    })

    assert output_dir == tmp_path / "Downloads" / "youtube-videos"
    assert cmd[:2] == ["yt-dlp", "https://www.youtube.com/watch?v=abc"]
    assert "-f" in cmd
    assert "bv*[height<=1080]+ba/b[height<=1080]" in cmd
    assert "--merge-output-format" in cmd
    assert "mp4" in cmd
    assert "--write-subs" in cmd
    assert "--write-auto-subs" in cmd
    assert ["--sub-langs", "zh-Hans,en"] == cmd[cmd.index("--sub-langs"):cmd.index("--sub-langs") + 2]
    assert "--embed-metadata" in cmd
    assert "--no-mtime" in cmd
    assert "--restrict-filenames" in cmd
    assert any(str(output_dir) in part for part in cmd)


def test_build_command_audio_only_extracts_mp3(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cmd, _ = build_yt_dlp_command({
        "url": "https://x.com/a/status/1",
        "audio_only": True,
        "audio_format": "mp3",
    })

    assert "-x" in cmd
    assert "--audio-format" in cmd
    assert "mp3" in cmd
    assert "-f" not in cmd


def test_bilibili_default_format_prefers_h264_for_ipad_compatibility(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cmd, _ = build_yt_dlp_command({"url": "https://www.bilibili.com/video/BV123", "format": "bv*+ba/b"})

    fmt = cmd[cmd.index("-f") + 1]
    assert fmt.startswith("bv*[vcodec^=avc1]")
    assert "+ba/" in fmt


def test_exact_source_format_is_not_overridden_by_quality(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cmd, _ = build_yt_dlp_command({
        "url": "https://www.bilibili.com/video/BV123",
        "format": "137+140",
        "quality": "1080",
    })

    assert cmd[cmd.index("-f") + 1] == "137+140"


def test_bilibili_command_adds_origin_header_to_avoid_412(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cmd, _ = build_yt_dlp_command({"url": "https://www.bilibili.com/video/BV1J5o6BsE1i?share_source=COPY"})

    assert "--add-header" in cmd
    header_index = cmd.index("--add-header") + 1
    assert cmd[header_index] == "Origin:https://www.bilibili.com"


def test_build_command_rejects_missing_or_invalid_url():
    with pytest.raises(ValueError):
        build_yt_dlp_command({"url": ""})
    with pytest.raises(ValueError):
        build_yt_dlp_command({"url": "file:///etc/passwd"})


def test_safe_job_id_is_short_filesystem_safe():
    job_id = safe_job_id()
    assert len(job_id) >= 8
    assert all(ch.isalnum() or ch in "-_" for ch in job_id)


def test_parse_progress_line_extracts_percentage_speed_eta_and_stage():
    progress = parse_progress_line("[download]  42.3% of 12.34MiB at 1.23MiB/s ETA 00:17")

    assert progress["stage"] == "download"
    assert progress["percent"] == 42.3
    assert progress["speed"] == "1.23MiB/s"
    assert progress["eta"] == "00:17"
    assert "42.3%" in progress["label"]


def test_job_updates_progress_without_filling_log_with_progress_noise():
    job = Job(id="abc", url="https://x.com/a/status/1", output_dir="/tmp", command=["yt-dlp"])

    job.handle_output_line("[download]  42.3% of 12.34MiB at 1.23MiB/s ETA 00:17")

    assert job.progress["percent"] == 42.3
    assert job.progress["eta"] == "00:17"
    assert job.log == []


def test_history_records_downloaded_files_and_paginates(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    for i in range(12):
        f = tmp_path / "Downloads" / "x-videos" / f"video-{i}.mp4"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("video")
        job = Job(id=f"job-{i}", url=f"https://x.com/a/status/{i}", output_dir=str(f.parent), command=["yt-dlp"])
        job.files = [str(f)]
        job.status = "done"
        record_history_for_job(job)

    first_page = list_history(page=1, per_page=10)
    second_page = list_history(page=2, per_page=10)

    assert first_page["total"] == 12
    assert first_page["page"] == 1
    assert first_page["per_page"] == 10
    assert len(first_page["items"]) == 10
    assert len(second_page["items"]) == 2
    assert first_page["items"][0]["title"].endswith(".mp4")
    assert first_page["items"][0]["download_url"].startswith("/media/")
    assert first_page["items"][0]["preview_url"].startswith("/media/")


def test_bilibili_probe_command_adds_origin_header():
    from app import build_probe_command

    cmd = build_probe_command("https://www.bilibili.com/video/BV1J5o6BsE1i?share_source=COPY")

    assert cmd[:3] == ["yt-dlp", "-J", "--no-playlist"]
    assert ["--add-header", "Origin:https://www.bilibili.com"] == cmd[3:5]


def test_resolve_media_path_allows_downloads_but_blocks_traversal(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    f = tmp_path / "Downloads" / "x-videos" / "safe.mp4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("video")

    token = str(f.relative_to(tmp_path / "Downloads"))
    assert resolve_media_path(token) == f.resolve()

    with pytest.raises(ValueError):
        resolve_media_path("../.ssh/id_rsa")


def test_delete_history_item_removes_file_and_marks_item_deleted(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    f = tmp_path / "Downloads" / "youtube-videos" / "safe.mp4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("video")
    job = Job(id="job-del", url="https://youtube.com/watch?v=1", output_dir=str(f.parent), command=["yt-dlp"])
    job.files = [str(f)]
    job.status = "done"
    item = record_history_for_job(job)[0]

    result = delete_history_item(item["id"])

    assert result["deleted"] is True
    assert not f.exists()
    assert list_history(page=1, per_page=10)["total"] == 0
