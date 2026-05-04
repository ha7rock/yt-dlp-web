# yt-dlp Web

局域网视频下载 Web UI，基于 yt-dlp，支持 YouTube、B站、X/Twitter 等数百个平台。

![界面截图](static/ytlogo.png)

## 功能

- **多平台**：YouTube、B站（含 B23 短链、412 防护、HEVC 修复）、X/Twitter、及 yt-dlp 支持的其他站点
- **格式预览**：下载前解析视频信息，按需选择分辨率/格式/音轨
- **App 分享文案解析**：直接粘贴 B站、微博等 App 的分享文字，自动提取 URL
- **实时进度**：进度条、速度、ETA、日志，可取消任务
- **历史管理**：分页浏览、关键词搜索（全库搜索）、视频预览播放、下载到本机、删除
- **主题**：浅色 / 深色 / 跟随系统，无闪烁切换
- **移动端友好**：响应式布局，iOS Safari 兼容

---

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|----------|------|
| Python | 3.10 + | 标准库 + Flask |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 最新 | 需在 `PATH` 中可执行 |
| [ffmpeg](https://ffmpeg.org/) | 任意 | 合流、音频转换必需 |
| Flask | 3.x | 唯一 Python 依赖 |

---

## 安装

### 1. 克隆项目

```bash
git clone https://github.com/ha7rock/yt-dlp-web.git
cd yt-dlp-web
```

### 2. 安装 Flask

根据你的 Python 环境选择一种方式：

**虚拟环境（推荐）**
```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install flask
```

**直接安装到用户目录**
```bash
pip install --user flask
```

**macOS（Homebrew 管理的 Python）**
```bash
pip3 install flask
```

### 3. 安装 yt-dlp 和 ffmpeg

**Linux**
```bash
# yt-dlp（推荐直接用官方二进制，始终最新）
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod +x /usr/local/bin/yt-dlp

# ffmpeg（Ubuntu/Debian）
sudo apt install ffmpeg
```

**macOS**
```bash
brew install yt-dlp ffmpeg
```

**Windows（WSL2）**
```bash
# 在 WSL2 内按 Linux 方式安装即可
```

---

## 运行

### 直接运行

```bash
# 激活 venv（如有）
source .venv/bin/activate

python3 app.py
```

默认监听 `0.0.0.0:8765`，局域网内其他设备可直接访问 `http://<本机IP>:8765/`。

### 自定义地址和端口

```bash
# 命令行参数
python3 app.py --host 127.0.0.1 --port 9000

# 或环境变量
YTDLP_WEB_HOST=127.0.0.1 YTDLP_WEB_PORT=9000 python3 app.py
```

---

## 后台服务（可选）

### Linux — systemd 用户服务

编辑 `yt-dlp-web.service`，将路径替换为实际路径：

```ini
[Service]
WorkingDirectory=/path/to/yt-dlp-web
Environment=PATH=/path/to/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/path/to/.venv/bin/python3 /path/to/yt-dlp-web/app.py
```

然后安装并启动：

```bash
cp yt-dlp-web.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now yt-dlp-web
```

查看日志：
```bash
journalctl --user -u yt-dlp-web -f
```

### macOS — launchd

创建 `~/Library/LaunchAgents/com.ytdlpweb.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ytdlpweb</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/.venv/bin/python3</string>
    <string>/path/to/yt-dlp-web/app.py</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>WorkingDirectory</key><string>/path/to/yt-dlp-web</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.ytdlpweb.plist
```

---

## 下载保存目录

所有文件保存在 `~/Downloads/` 的子目录，按平台自动分类：

| 平台 | 目录 |
|------|------|
| YouTube | `~/Downloads/youtube-videos/` |
| X / Twitter | `~/Downloads/x-videos/` |
| B站 | `~/Downloads/bilibili-videos/` |
| 其他 | `~/Downloads/yt-dlp-videos/` |

历史记录存储于 `~/.local/share/yt-dlp-web/history.json`。

---

## HTTPS 访问（可选）

浏览器剪贴板 API（粘贴按钮）在 HTTP 下受限。若需要在局域网内完整体验，建议通过以下方式启用 HTTPS：

- **Tailscale**：`tailscale serve --bg https / http://127.0.0.1:8765`
- **Nginx 反代 + 自签证书**：配置 `proxy_pass http://127.0.0.1:8765`
- **localhost 访问**：直接在本机用 `http://localhost:8765/` 即可，浏览器视为安全上下文

---

## 技术栈

- **后端**：Python 3 + Flask，单文件，零数据库
- **前端**：原生 HTML / CSS / JavaScript，零框架依赖
- **下载核心**：yt-dlp subprocess
- **测试**：pytest（`tests/` 目录）

```bash
pip install pytest
pytest tests/ -q
```

---

## License

MIT
