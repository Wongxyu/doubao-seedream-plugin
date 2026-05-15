# -*- coding: utf-8 -*-
"""Doubao Seedream image generation tool for QwenPaw.

Supports text-to-image and image-to-image generation via Doubao Seedream
models (4.0/4.5/5.0/5.0-lite) and any OpenAI-compatible image generation API.

Key feature: auto-downloads generated images to local disk and returns
ImageBlock for inline display in QwenPaw WebUI.
"""
import base64
import logging
import os
import re
import uuid
from pathlib import Path
from typing import List, Optional, Union

import httpx

from agentscope.message import ImageBlock, TextBlock
from agentscope.tool import ToolResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path.home() / "Pictures" / "QwenPaw_Generated"
REF_IMAGE_DIR = Path(os.path.realpath(Path.home() / "Pictures"))
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_B64_LEN = MAX_FILE_SIZE * 4 // 3 + 1024
DEFAULT_TIMEOUT = 90.0
DEFAULT_SIZE = "2K"
DEFAULT_N = 1

# Doubao Seedream model resolution reference
MODEL_RESOLUTIONS = {
    "doubao-seedream-4-0-250828": ["1024x1024", "2K", "4K"],
    "doubao-seedream-4-5-251128": ["2K", "4K"],
    "doubao-seedream-5-0-260128": ["2K", "3K"],
    "doubao-seedream-5.0-lite": ["1024x1024", "1792x1024", "1024x1792", "2K", "3K"],
}

# Magic bytes for image format detection
_FORMAT_SIGNATURES = [
    (b"\x89PNG", "png"),
    (b"\xff\xd8", "jpg"),
    (b"RIFF", "webp"),   # needs secondary check
    (b"BM", "bmp"),
    (b"GIF8", "gif"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _error(msg: str) -> ToolResponse:
    """Create an error ToolResponse."""
    return ToolResponse(content=[TextBlock(type="text", text=f"❌ {msg}")])


def _detect_format(data: bytes) -> str:
    """Detect image format from magic bytes."""
    if len(data) < 4:
        return "png"
    for sig, fmt in _FORMAT_SIGNATURES:
        if data.startswith(sig):
            if fmt == "webp" and data[8:12] != b"WEBP":
                continue
            return fmt
    return "png"


def _sanitize_filename(text: str, max_len: int = 20) -> str:
    """Sanitize text for use in filename."""
    cleaned = re.sub(r"[^\w\s-]", "", text[:max_len]).strip()
    return cleaned.replace(" ", "_") + "_" if cleaned else ""


def _get_config() -> dict:
    """Read tool config from plugin registry."""
    try:
        from qwenpaw.app.agent_context import get_current_agent_id
        from qwenpaw.plugins.registry import PluginRegistry

        agent_id = get_current_agent_id() or "default"
        return PluginRegistry().get_tool_config("generate_image", agent_id) or {}
    except Exception:
        logger.debug("Failed to load tool config", exc_info=True)
        return {}


def _save_image_bytes(data: bytes, index: int, prefix: str = "") -> str:
    """Save raw image bytes to OUTPUT_DIR, return absolute path."""
    ext = _detect_format(data)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{_sanitize_filename(prefix)}{uuid.uuid4().hex[:8]}_{index}.{ext}"
    path = OUTPUT_DIR / filename
    path.write_bytes(data)
    return str(path.resolve())


# ---------------------------------------------------------------------------
# Reference image processing
# ---------------------------------------------------------------------------
def _process_ref_images(
    images: Union[str, List[str]],
) -> Union[List[str], ToolResponse]:
    """Convert reference image inputs to API-compatible format."""
    if isinstance(images, str):
        images = [images]

    if len(images) > 14:
        return _error("最多支持 14 张参考图")

    result = []
    for img in images:
        img = img.strip()
        if not img:
            continue
        if img.startswith("https://"):
            result.append(img)
        elif img.startswith("http://"):
            return _error(f"参考图 URL 必须使用 HTTPS: {img[:50]}...")
        elif img.startswith("data:image/"):
            result.append(img)
        else:
            # Local file path
            expanded = os.path.expanduser(img)
            resolved = os.path.realpath(expanded)
            try:
                Path(resolved).relative_to(REF_IMAGE_DIR)
            except ValueError:
                return _error(
                    f"参考图仅允许从 ~/Pictures/ 读取，当前路径: {resolved}"
                )
            if not os.path.isfile(resolved):
                return _error(f"参考图文件不存在: {resolved}")
            if os.path.getsize(resolved) > MAX_FILE_SIZE:
                return _error(f"参考图文件超过 20MB 限制: {resolved}")
            with open(resolved, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = Path(resolved).suffix.lstrip(".").lower()
            mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/png")
            result.append(f"data:{mime};base64,{b64}")
    return result


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------
async def _download(url: str, index: int, prefix: str = "") -> Optional[str]:
    """Download image from URL to local disk."""
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return _save_image_bytes(resp.content, index, prefix)
    except Exception as e:
        logger.warning("Download failed for %s: %s", url, e)
        return None


# ---------------------------------------------------------------------------
# Core tool function
# ---------------------------------------------------------------------------
async def generate_image(
    prompt: str,
    size: str = DEFAULT_SIZE,
    n: int = DEFAULT_N,
    style: str = "auto",
    image: Optional[Union[str, List[str]]] = None,
    web_search: bool = False,
) -> ToolResponse:
    """Generate images using Doubao Seedream or other OpenAI-compatible image API.

    Automatically downloads generated images and returns ImageBlock for
    inline display in QwenPaw WebUI.

    Args:
        prompt:
            Text description of the image to generate.
            Be specific and detailed for best results.
        size:
            Output resolution. Defaults to "2K".
            Doubao Seedream supported values:
              - 4.0: 1024x1024, 2K, 4K
              - 4.5: 2K, 4K
              - 5.0: 2K, 3K
              - 5.0-lite: 1024x1024, 1792x1024, 1024x1792, 2K, 3K
        n:
            Number of images to generate (1-4). Defaults to 1.
        style:
            Image style. Defaults to "auto" (not sent to API).
            Common values: "auto", "realistic", "vivid", "natural".
            Supported values depend on backend model.
        image:
            Optional reference image(s) for image-to-image generation.
            Accepts: local path (under ~/Pictures/), HTTPS URL, or base64 data URL.
            Up to 14 reference images supported.
        web_search:
            Enable web search enhancement (doubao-seedream-5.0-lite only).
            Defaults to False.

    Returns:
        ToolResponse with ImageBlock(s) for inline display and text metadata.
    """
    # --- Config ---
    cfg = _get_config()
    if not cfg:
        return _error("工具未配置，请在 Tools 设置中填写 API Key")

    api_key = (cfg.get("api_key") or "").strip()
    base_url = (cfg.get("base_url") or "").strip()
    model = (cfg.get("model") or "").strip()

    if not api_key:
        return _error("API Key 未配置")
    if not base_url:
        return _error("Base URL 未配置")
    if not model:
        return _error("模型名称未配置")

    # Security: enforce HTTPS (allow localhost for dev)
    if not base_url.startswith("https://") and not base_url.startswith(
        ("http://localhost", "http://127.0.0.1")
    ):
        return _error("Base URL 必须使用 HTTPS")

    try:
        timeout = float(cfg.get("timeout", DEFAULT_TIMEOUT))
        if timeout <= 0:
            timeout = DEFAULT_TIMEOUT
    except (ValueError, TypeError):
        timeout = DEFAULT_TIMEOUT

    # --- Validate params ---
    if not prompt.strip():
        return _error("提示词不能为空")

    size = (size or DEFAULT_SIZE).strip() or DEFAULT_SIZE
    style = (style or "auto").strip().lower()

    try:
        n = int(n)
    except (ValueError, TypeError):
        return _error(f"无效的数量参数: {n}")
    if not 1 <= n <= 4:
        return _error("数量必须在 1-4 之间")

    # --- Build payload ---
    payload: dict = {
        "model": model,
        "prompt": prompt.strip(),
        "size": size,
        "n": n,
    }
    if style and style != "auto":
        payload["style"] = style
    if web_search:
        payload["web_search"] = True

    # Reference images
    if image:
        processed = _process_ref_images(image)
        if isinstance(processed, ToolResponse):
            return processed
        if processed:
            payload["image"] = processed if len(processed) > 1 else processed[0]

    # --- Call API ---
    endpoint = base_url.rstrip("/") + "/images/generations"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return _error(f"请求超时（{timeout}s），大图建议增加超时时间")
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            err = exc.response.json()
            detail = err.get("error", {}).get("message", err.get("message", str(exc)))
        except Exception:
            detail = str(exc)
        return _error(f"API 请求失败: {detail}")
    except Exception as exc:
        logger.exception("Unexpected error")
        return _error(f"未知错误: {exc}")

    # --- Parse response ---
    if "data" not in data or not isinstance(data.get("data"), list):
        err_msg = "未知错误"
        if isinstance(data, dict):
            err_msg = data.get("error", {}).get("message", data.get("message", err_msg))
        return _error(f"API 返回异常: {err_msg}")

    items = data["data"]
    if not items:
        return _error("API 未返回图片")

    # --- Download & build response ---
    content: list = []
    lines = [f"✅ 成功生成 {len(items)} 张图片：\n"]

    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            lines.append(f"- 第 {i} 张: 格式异常")
            continue

        url = item.get("url", "")
        b64 = item.get("b64_json", "")
        revised = item.get("revised_prompt", "")
        item_size = item.get("size", size)

        local_path = None

        # URL: download to local for inline display
        if url:
            local_path = await _download(url, i, prompt[:20])
            if local_path:
                # Add ImageBlock for WebUI inline display
                file_url = local_path.replace("\\", "/")
                if not file_url.startswith("/"):
                    file_url = "/" + file_url
                content.append(ImageBlock(
                    type="image",
                    source={"type": "url", "url": f"file://{file_url}"},
                ))
            lines.append(f"**第 {i} 张** ({item_size}):")
            lines.append(f"🔗 {url}")
            if local_path:
                lines.append(f"💾 {local_path}")
            lines.append("")

        # Base64: save to local file
        elif b64:
            if len(b64) > MAX_B64_LEN:
                lines.append(f"- 第 {i} 张: base64 数据过大")
                continue
            try:
                img_bytes = base64.b64decode(b64)
                local_path = _save_image_bytes(img_bytes, i, prompt[:20])
                file_url = local_path.replace("\\", "/")
                if not file_url.startswith("/"):
                    file_url = "/" + file_url
                content.append(ImageBlock(
                    type="image",
                    source={"type": "url", "url": f"file://{file_url}"},
                ))
                lines.append(f"**第 {i} 张** ({item_size}):")
                lines.append(f"💾 {local_path}")
                lines.append("")
            except Exception as e:
                logger.warning("Failed to save b64 image: %s", e)
                lines.append(f"- 第 {i} 张: 保存失败")

        else:
            lines.append(f"- 第 {i} 张: 无图片数据")

        if revised and revised != prompt:
            lines.append(f"_优化提示词: {revised}_\n")

    # Usage info
    if isinstance(data.get("usage"), dict):
        ws = data["usage"].get("web_search", 0)
        if ws:
            lines.append(f"🔍 联网搜索次数: {ws}")

    content.append(TextBlock(type="text", text="\n".join(lines)))
    return ToolResponse(content=content)
