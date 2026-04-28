# yt-dlp Web

局域网可访问的 yt-dlp 下载页面。

## 启动

```bash
cd ~/yt-dlp-web
./app.py --host 0.0.0.0 --port 8765
```

浏览器打开：`http://<这台机器IP>:8765/`

## 保存目录

- X/Twitter: `~/Downloads/x-videos/`
- YouTube: `~/Downloads/youtube-videos/`
- B站: `~/Downloads/bilibili-videos/`
- 其他: `~/Downloads/yt-dlp-videos/`

## systemd 用户服务

已提供 `yt-dlp-web.service`，可复制到 `~/.config/systemd/user/` 后启用。
