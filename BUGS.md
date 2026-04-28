# BUGS

## 🐛 活跃

目前暂无未归档的新 bug。若 B-003 在 iPad 上仍影响使用，需要改成 HTTPS 或改交互，不是纯前端 JS 能强制解决。

## ✅ 已修复 / 已处理

### B-001: 下载完成后页面不停刷新（回归）
**严重程度**：中 → 已修复  
**描述**：下载完成后，任务卡片不消失，页面持续刷新  
**根因**：`startPolling()` 启动后没有在任务结束时清理 `pollTimer`，所以只要触发过下载，就会持续刷新  
**修复**：`loadJobs()` 返回任务列表；polling 每轮检查是否还有 queued/running 任务，没有则 `clearInterval`  
**日期**：2026-04-28

### B-002: B站下载的视频无法在 iPad 播放/存相册
**严重程度**：高 → 已修复  
**描述**：B站下载得到 `.mp4`，但 iPad 无法直接播放，也无法存入相册  
**根因**：B站 HEVC 视频流封装为 `hev1` tag；iOS/照片 App 对 `hev1` 兼容不如 `hvc1`  
**修复**：B站下载完成后自动检测 `.mp4` 首个视频流；仅当 `codec_name=hevc && codec_tag_string=hev1` 时执行无损 remux：`ffmpeg -i input.mp4 -c:v copy -c:a copy -tag:v hvc1 tmp.mp4`，再替换原文件  
**影响范围**：只作用于 B站 + HEVC + hev1；X / YouTube / B站 H.264 / 已是 hvc1 的文件都不动  
**日期**：2026-04-28

### B-003: 粘贴剪贴板在 iPad 上无效
**严重程度**：低 → 已缓解  
**描述**：在 iPad Safari 上点击“粘贴剪切板”按钮无响应  
**原因**：`navigator.clipboard.readText()` 在非 HTTPS / iPad Safari 下受浏览器权限限制，无法通过 JS 强制读取  
**处理**：读取失败时自动聚焦并选中输入框，引导长按/⌘V 手动粘贴  
**日期**：2026-04-28

### B-004: 网址过长导致任务信息“破窗”
**严重程度**：低 → 已修复  
**描述**：当 URL 很长时（如带有大量 query params），任务卡片的 URL 行会溢出或破坏布局  
**修复**：任务卡片 URL 增加 `overflow-wrap:anywhere` 与 `word-break:break-word`  
**日期**：2026-04-28

### B-005: B站 playurl API 返回 HTTP 412
**严重程度**：高 → 已修复  
**描述**：yt-dlp 获取 B站视频信息时报 HTTP 412 Precondition Failed  
**修复**：对 B站链接自动添加 `Origin:https://www.bilibili.com` 请求头  
**日期**：2026-04-28
