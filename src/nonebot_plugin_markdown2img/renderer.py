from __future__ import annotations

import base64
import hashlib
import inspect
import io
import os
from pathlib import Path
import re
import tempfile

from html2image import Html2Image
import httpx
import markdown_it
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from mdit_py_plugins.texmath import texmath_plugin
from nonebot import get_plugin_config
from nonebot.log import logger

try:
    from .config import Config

    plugin_config: Config = get_plugin_config(Config)
except Exception:

    class Config:
        markdown2img_font_path: str | None = None
        markdown2img_disable_gpu: bool | None = True
        markdown2img_disable_linkify: bool | None = True
        pass

    plugin_config = Config()

# 临时文件路径
TEMP_DIR = Path(tempfile.gettempdir()) / "markdown_renderer"
TEMP_DIR.mkdir(exist_ok=True)

# 图片缓存目录
IMAGE_CACHE_DIR = TEMP_DIR / "image_cache"
IMAGE_CACHE_DIR.mkdir(exist_ok=True)

DEFAULT_FONT_PATH = Path(plugin_config.markdown2img_font_path) if plugin_config.markdown2img_font_path else None
disable_gpu = plugin_config.markdown2img_disable_gpu
disable_linkify = plugin_config.markdown2img_disable_linkify

if disable_gpu is True:
    logger.warning("Markdown2Img: GPU 加速已禁用以提高兼容性。")
else:
    logger.warning("Markdown2Img: GPU 加速未禁用，若在无头服务器环境中运行可能会失败。")

if disable_linkify is True:
    logger.warning("Markdown2Img: 链接自动识别已禁用。")


def download_and_cache_image(url: str) -> str:
    """
    下载图片并缓存到本地，返回本地文件URI

    Args:
        url: 图片URL

    Returns:
        本地文件URI (file://...)
    """
    # 检查URL格式，确保有协议前缀
    if not url.startswith(("http://", "https://")):
        logger.warning(f"图片URL缺少协议前缀: {url}")
        return url  # 返回原始URL，让浏览器处理

    # 创建URL的哈希值作为文件名
    url_hash = hashlib.md5(url.encode()).hexdigest()
    file_ext = url.split(".")[-1] if "." in url.split("/")[-1] else "jpg"
    cache_file = IMAGE_CACHE_DIR / f"{url_hash}.{file_ext}"

    # 如果文件已存在，直接返回
    if cache_file.exists():
        logger.info(f"使用缓存的图片: {url}")
        return cache_file.as_uri()

    try:
        # 使用httpx下载图片，添加更多配置
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # noqa
        }

        # 使用同步方式下载，避免异步问题
        with httpx.Client(
            timeout=5.0,  # 减少超时时间
            follow_redirects=True,
            headers=headers,
            verify=False,  # 禁用SSL证书验证
        ) as client:
            response = client.get(url)
            response.raise_for_status()

            # 保存到缓存
            with open(cache_file, "wb") as f:
                f.write(response.content)

            logger.info(f"图片已缓存: {url} -> {cache_file}")
            return cache_file.as_uri()

    except Exception as e:
        logger.error(f"下载图片失败: {url}, 错误: {e}")
        # 返回原始URL，让浏览器尝试加载
        return url


def process_images_in_html(html_content: str) -> str:
    """
    处理HTML中的图片链接，下载并缓存图片

    Args:
        html_content: HTML内容

    Returns:
        处理后的HTML内容
    """
    # 匹配HTML img标签中的src属性
    img_pattern = r'<img[^>]+src="([^"]+)"[^>]*>'

    # 找到所有图片URL
    img_urls = []
    for match in re.finditer(img_pattern, html_content):
        src_url = match.group(1)
        if src_url.startswith("https://"):
            img_urls.append((match.group(0), src_url))

    # 如果没有HTTPS图片，直接返回
    if not img_urls:
        return html_content

    logger.warning(f"检测到 {len(img_urls)} 个 HTTPS 图片链接，正在缓存以避免SSL问题。")

    # 简化处理：只下载前3张图片，避免阻塞
    max_images = 3
    limited_img_urls = img_urls[:max_images]

    # 同步下载图片，避免异步问题
    local_uris = []
    for _, src_url in limited_img_urls:
        try:
            local_uri = download_and_cache_image(src_url)
            local_uris.append(local_uri)
        except Exception as e:
            logger.error(f"处理图片失败: {src_url}, 错误: {e}")
            local_uris.append(src_url)  # 使用原始URL

    # 替换HTML中的图片URL
    processed_html = html_content
    for i, (img_tag, src_url) in enumerate(limited_img_urls):
        local_uri = local_uris[i]
        processed_html = processed_html.replace(img_tag, img_tag.replace(src_url, local_uri))

    return processed_html


def markdown_to_html(md_text: str, font_path: Path | None = None) -> str:
    """
    将 Markdown 文本转换为功能齐全的 HTML (使用 markdown-it-py)
    """

    # 1. 定义代码高亮函数
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name

    def highlight_code(code: str, lang: str, lang_attrs: str = "") -> str:
        """使用 Pygments 进行代码高亮"""
        if not lang:
            return f"<pre><code>{code}</code></pre>"

        try:
            lexer = get_lexer_by_name(lang)
            formatter = HtmlFormatter()
            return highlight(code, lexer, formatter)
        except Exception:
            # 如果语言不支持，返回原始代码
            return f"<pre><code>{code}</code></pre>"

    # 2. 初始化 Markdown 解析器
    md = (
        markdown_it.MarkdownIt("gfm-like", {"highlight": highlight_code, "linkify": not disable_linkify})
        .use(footnote_plugin)
        .use(tasklists_plugin)
        .use(texmath_plugin, delimiters="dollars")
    )

    # 2. 获取代码高亮 CSS
    pygments_css = HtmlFormatter(style="default").get_style_defs(".highlight")

    # 3. 处理字体
    font_face_css = ""
    font_family_name = "STSong-Light, 'SimSun', serif"  # 默认回退字体

    if font_path and font_path.exists():
        # 确保路径是绝对路径，然后创建本地 URL (file:///...)
        absolute_font_path = font_path.resolve()
        font_url = absolute_font_path.as_uri()
        font_family_name = "CustomFont"  # 使用自定义字体

        font_face_css = f"""
        @font-face {{
            font-family: '{font_family_name}';
            src: url("{font_url}");
        }}
        """

    # 4. 组装 HTML
    html_fragment = md.render(md_text)

    # 5. 处理图片缓存
    html_fragment = process_images_in_html(html_fragment)

    html = f"""
    <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <style type="text/css">
            /* 注入字体 */
            {font_face_css}

            /* 注入代码高亮 */
            {pygments_css}

            /* 移除 @page 和 @frame 相关的 CSS */

            /* 合并你原来的样式和现代浏览器样式 */
            body {{
                /* 添加背景色 */
                background-color: #f8f9fa;
                /* 使用自定义字体 */
                font-family: "{font_family_name}", STSong-Light, "SimSun", serif;
                font-size: 16pt; /* 稍稍调大, 截图效果更好 */

                /* 浏览器会自动处理换行 */
                word-wrap: break-word;
                overflow-wrap: break-word;
                line-height: 1.6;
                margin: 0;
                padding: 1.5em; /* 增加一些内边距 */
            }}
            p {{
                margin: 0.5em 0;
            }}
            h1, h2, h3, h4, h5, h6 {{
                font-family: "{font_family_name}", STSong-Light, "SimSun", serif;
                font-weight: bold;
                margin-top: 1em;
                margin-bottom: 0.5em;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }}
            table, th, td {{
                border: 1px solid black;
            }}
            th, td {{
                padding: 8px;
                text-align: left;
            }}
            pre {{
                /* pygments 会处理 pre/code 样式 */
                overflow: auto;
                margin: 1em 0;
            }}
            code {{
                font-family: "Courier New", monospace;
            }}
            /* 行内 code 样式 */
            :not(pre) > code {{
                 background: #f4f4f4;
                 padding: 3px;
            }}
            blockquote {{
                border-left: 4px solid #ccc;
                margin: 1em 0;
                padding-left: 1em;
                color: #666;
            }}
            ul, ol {{
                margin: 1em 0;
                padding-left: 2em;
            }}
            li {{
                margin: 0.5em 0;
            }}
            a {{
                color: #0066cc;
                text-decoration: underline;
            }}
        </style>
    </head>
    <body>
        {html_fragment}
    </body>
    </html>
    """
    return html


def render_markdown_to_image_bytes(
    markdown_text: str,
    font_path: Path | None = None,
    canvas_width: int = 800,  # 调整了默认宽度
    zoom: float = 2.0,  # 2.0 对应 2x 缩放 (视网膜屏), 3.0 可能太大了
) -> bytes:
    """
    将 Markdown 文本渲染为 PNG 图片并返回字节数据。

    Args:
        markdown_text: 要渲染的 Markdown 文本
        font_path: 自定义字体文件路径
        canvas_width: 截图的宽度
        zoom: 缩放因子 (DPI), 2.0 意味着 2x 分辨率

    Returns:
        PNG 图片的字节数据 (单张长图)
    """

    # 定义临时截图文件名
    temp_img_name = f"temp_{os.getpid()}_{id(markdown_text)}.png"
    temp_img_path = TEMP_DIR / temp_img_name

    try:
        # 1. 转换为 HTML, 注入字体
        html = markdown_to_html(markdown_text, font_path)

        # 检查Markdown文本中是否包含HTTPS图片链接
        if "https://" in markdown_text and "![](" in markdown_text:
            logger.warning("Markdown文本中包含HTTPS图片链接，正在缓存图片以避免SSL问题")

        # 2. 初始化 html2image
        hti_kwargs = {
            "output_path": str(TEMP_DIR),
        }
        post_scale_factor = 1.0

        try:
            init_signature = inspect.signature(Html2Image.__init__)
        except (TypeError, ValueError):
            init_signature = None

        if zoom != 1.0:
            if init_signature and "device_scale_factor" in init_signature.parameters:
                hti_kwargs["device_scale_factor"] = zoom
            else:
                # Fallback for html2image versions without device_scale_factor support.
                post_scale_factor = zoom

        # 尝试在初始化时设置浏览器标志
        browser_flags = [
            "--disable-gpu",
            "--disable-gpu-sandbox",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            # 添加SSL相关标志以处理HTTPS图片加载问题
            "--ignore-certificate-errors",
            "--ignore-ssl-errors",
            "--ignore-certificate-errors-spki-list",
            "--allow-running-insecure-content",
            "--disable-extensions",
            "--disable-webgl",
            "--disable-gl-drawing-for-tests",
            "--disable-accelerated-2d-canvas",
            "--disable-accelerated-video-decode",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--disable-translate",
            "--hide-scrollbars",
            "--mute-audio",
            "--no-first-run",
            "--safebrowsing-disable-auto-update",
            "--disable-ipc-flooding-protection",
            "--disable-logging",
            "--disable-permissions-api",
            "--disable-notifications",
        ]

        # 如果支持browser_flags参数，则直接传递
        if init_signature and "browser_flags" in init_signature.parameters:
            hti_kwargs["browser_flags"] = browser_flags

        hti = Html2Image(**hti_kwargs)

        # 在无头服务器环境中彻底禁用所有图形相关功能
        browser = getattr(hti, "browser", None)
        if browser and hasattr(browser, "flags"):
            try:
                flags = browser.flags
                if flags is None:
                    flags = []
                elif isinstance(flags, (tuple, set)):
                    flags = list(flags)

                # 添加全面的禁用标志
                for flag in browser_flags:
                    if flag not in flags:
                        flags.append(flag)

                browser.flags = flags
            except Exception:
                pass

        # 3. 截图（自适应高度）
        from PIL import Image, ImageChops

        min_canvas_width = max(1, canvas_width)
        text_lines = len(markdown_text.split("\n"))
        code_blocks = markdown_text.count("```")
        # 基础高度：每行约20px，每个代码块额外增加200px
        estimated_height = max(text_lines * 20 + code_blocks * 200, 800)
        max_height = 50000  # 增加最大高度限制
        margin_threshold = 120  # 增加边距阈值
        attempts = 0
        final_bbox = None

        def capture_once(viewport_height: int) -> Path:
            image_paths = hti.screenshot(
                html_str=html,
                save_as=temp_img_name,
                size=(min_canvas_width, viewport_height),
            )
            if not image_paths:
                raise ValueError("html2image failed to return image paths")

            output_file = Path(image_paths[0])
            if not output_file.exists():
                raise ValueError("html2image failed to generate an image file")

            return output_file

        image_file = capture_once(estimated_height)

        while attempts < 4:
            attempts += 1
            with Image.open(image_file) as probe:
                alpha_bbox = None
                if "A" in probe.getbands():
                    alpha_bbox = probe.getchannel("A").getbbox()
                else:
                    bg_color = probe.getpixel((0, 0))
                    diff = ImageChops.difference(probe, Image.new(probe.mode, probe.size, bg_color))
                    alpha_bbox = diff.getbbox()

                final_bbox = alpha_bbox
                if alpha_bbox is None:
                    break

                bottom_margin = probe.height - alpha_bbox[3]
                if bottom_margin > margin_threshold or probe.height >= max_height:
                    break

            if attempts >= 6 or estimated_height >= max_height:  # 增加尝试次数
                break

            # 更激进的高度增长策略
            if attempts < 3:
                estimated_height = int(min(estimated_height * 2, max_height))
            else:
                estimated_height = int(min(estimated_height * 1.5, max_height))
            image_file = capture_once(estimated_height)

        # 4. 读取字节并按需裁剪/缩放
        with Image.open(image_file) as img:
            top = 0
            bottom = img.height

            if final_bbox:
                vertical_padding = 32
                top = max(0, final_bbox[1] - vertical_padding)
                bottom = min(img.height, final_bbox[3] + vertical_padding)

            if top > 0 or bottom < img.height:
                img = img.crop((0, top, img.width, bottom))

            if post_scale_factor != 1.0:
                target_size = (
                    max(1, int(img.width * post_scale_factor)),
                    max(1, int(img.height * post_scale_factor)),
                )
                if target_size != img.size:
                    resample_filter = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
                    img = img.resize(target_size, resample_filter)

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

        return image_bytes

    except Exception as e:
        # 提供更详细的错误信息
        error_msg = str(e)
        if not error_msg:
            if "SSL" in str(type(e)) or "certificate" in str(type(e)).lower():
                error_msg = "SSL证书验证失败，可能是由于HTTPS图片链接导致的"
            else:
                error_msg = f"渲染失败: {type(e).__name__}"

        logger.error(f"Markdown渲染图片失败: {error_msg}")
        logger.error(f"异常类型: {type(e).__name__}")
        logger.error(f"异常详情: {e!r}")

        # 重新抛出异常，确保错误信息能够正确传递
        raise RuntimeError(error_msg) from e

    finally:
        # 清理临时文件
        if temp_img_path.exists():
            temp_img_path.unlink()


def render_markdown_to_base64(
    markdown_text: str, font_path: Path | None = DEFAULT_FONT_PATH, canvas_width: int = 800, zoom: float = 2.0
) -> str:
    """
    渲染 Markdown 并返回 base64 格式，便于直接发送图片消息。
    """
    byte_data = render_markdown_to_image_bytes(markdown_text, font_path, canvas_width, zoom)
    return "base64://" + base64.b64encode(byte_data).decode("utf-8")


def clean_up():
    """
    清理所有遗留的临时截图文件
    """
    for file_path in TEMP_DIR.glob("temp_*.png"):  # 改为清理 png
        if file_path.exists():
            try:
                file_path.unlink()
            except PermissionError:
                # Handle potential file locks on Windows
                pass


__all__ = ["clean_up", "render_markdown_to_base64", "render_markdown_to_image_bytes"]


if __name__ == "__main__":
    # 测试用例
    test_markdown = """
# 标题测试

这是一个 **Markdown 渲染器** 的测试文档。

## 功能特性

- 支持 *斜体* 和 **粗体** 文本
- 支持 `行内代码` 和代码块：
```python
def hello_world():
    print("Hello, World!")
    return True
```
- 支持表格：

| 功能 | 状态 |
|------|------|
| Markdown解析 | ✅ 完成 |
| HTML渲染 | ✅ 完成 |
| 图片生成 | ✅ 完成 |

- 支持列表：
  1. 第一项
  2. 第二项
  3. 第三项

- 支持引用：

> 这是一个引用块，用于展示引用样式。

- 支持数学公式：$E = mc^2$

- 支持脚注测试[^1]

[^1]: 这是一个脚注说明

---

## 测试结果

如果一切正常，这段 Markdown 文本将被正确渲染为图片。
"""

    print("开始测试 Markdown 渲染器...")

    try:
        # 测试 1: Markdown 转 HTML
        print("\n1. 测试 Markdown 转 HTML...")
        html_output = markdown_to_html(test_markdown)
        print(f"HTML 输出长度: {len(html_output)} 字符")
        print("HTML 转换成功 ✓")

        # 测试 2: Markdown 转图片字节流
        print("\n2. 测试 Markdown 转图片字节流...")
        image_bytes = render_markdown_to_image_bytes(test_markdown)
        print(f"图片大小: {len(image_bytes)} 字节")
        print("图片生成成功 ✓")

        # 保存测试图片到文件
        test_image_path = "test_markdown_output.png"
        with open(test_image_path, "wb") as f:
            f.write(image_bytes)
        print(f"测试图片已保存到: {test_image_path}")

        # 测试 3: Markdown 转 base64
        print("\n3. 测试 Markdown 转 base64...")
        base64_output = render_markdown_to_base64(test_markdown)
        print(f"Base64 输出长度: {len(base64_output)} 字符")
        print("Base64 转换成功 ✓")

        # 测试 4: 清理临时文件
        print("\n4. 测试清理临时文件...")
        clean_up()
        print("临时文件清理完成 ✓")

        print("\n🎉 所有测试通过！Markdown 渲染器工作正常。")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
