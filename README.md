# doubao-seedream-plugin | 豆包 Seedream 文生图工具

**QwenPaw plugin for AI image generation via Doubao Seedream** — with auto-download and inline display in WebUI.

一个 [QwenPaw](https://github.com/agentscope-ai/QwenPaw) 工具插件，调用豆包 Seedream 文生图模型生成图片，**自动下载到本地并在 WebUI 中内联展示**。

## Features | 特性

- 🎨 **文生图** — 文字描述生成高质量图片
- 🖼️ **图生图** — 支持 1-14 张参考图进行风格/内容迁移
- 📐 **多分辨率** — 1024x1024 / 2K / 3K / 4K（取决于模型）
- 🔍 **联网搜索增强** — doubao-seedream-5.0-lite 支持
- 💾 **自动下载 + 内联展示** — 图片下载到本地，WebUI 直接看到（非临时链接）
- 🔧 **OpenAI 兼容** — 也支持 GPT Image、Flux 等其他兼容 API

## Supported Models | 支持的模型

| Model ID | Resolution |
|----------|-----------|
| `doubao-seedream-4-0-250828` | 1K, 2K, 4K |
| `doubao-seedream-4-5-251128` | 2K, 4K |
| `doubao-seedream-5-0-260128` | 2K, 3K |
| `doubao-seedream-5.0-lite` | 1024x1024, 1792x1024, 1024x1792, 2K, 3K |

## Installation | 安装

### Quick Install | 一键安装

```bash
qwenpaw plugin install https://github.com/scad12138/doubao-seedream-qwenpaw-plugin/archive/refs/heads/main.zip
```

### From Source | 从源码安装

```bash
git clone https://github.com/scad12138/doubao-seedream-qwenpaw-plugin.git
qwenpaw plugin install ./doubao-seedream-plugin
```

## Configuration | 配置

安装后重启 QwenPaw，在 WebUI → Tools 中找到 `generate_image`，填写：

| Field | Value |
|-------|-------|
| **API Key** | 火山方舟 API Key（[获取地址](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)） |
| **Base URL** | `https://ark.cn-beijing.volces.com/api/v3` |
| **模型名称** | 如 `doubao-seedream-5.0-lite` |
| **默认分辨率** | `2K` |
| **超时** | `90`（3K/4K 建议 120+） |

配置完成后启用工具即可使用。

## Usage | 使用

在任意已启用此工具的 Agent 对话中直接描述想要的图片：

```
帮我生成一张赛博朋克风格的橘猫，霓虹灯背景，2K
```

### Tool Parameters | 工具参数

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | str | **required** | 图片描述，越详细越好 |
| `size` | str | `"2K"` | 分辨率，取决于模型支持 |
| `n` | int | `1` | 生成数量（1-4） |
| `style` | str | `"auto"` | 风格：auto / realistic / vivid / natural |
| `image` | str/list | None | 参考图（本地路径/URL/base64，最多14张） |
| `web_search` | bool | `False` | 联网搜索增强（仅 5.0-lite） |

### Generated Files | 生成文件位置

图片自动保存到：`~/Pictures/QwenPaw_Generated/`

文件名格式：`{提示词前20字}_{随机ID}_{序号}.{扩展名}`

## Differences from Original | 与原版插件的差异

本插件基于 [lioneltan1234/qwenpaw-image-generation-plugin](https://github.com/lioneltan1234/qwenpaw-image-generation-plugin) 重构，主要改进：

1. **自动下载 + 内联展示** — API 返回的临时 URL 图片自动下载到本地，通过 ImageBlock 在 WebUI 直接展示，不再依赖 24 小时过期的临时链接
2. **模型分辨率速查** — 在 docstring 和配置中列出各 Seedream 模型支持的分辨率
3. **参考图安全沙箱** — 限制参考图只能从 `~/Pictures/` 读取，防止路径遍历
4. **更清晰的错误信息** — 所有错误提示使用中文，明确指出缺失了哪个配置项
5. **默认超时 90s** — 大图生成（3K/4K）常需 60s+，90s 默认值更稳妥
6. **代码精简** — 合并重复逻辑，统一 URL 和 base64 的本地保存流程

## License

MIT
