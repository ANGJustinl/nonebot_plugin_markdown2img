import asyncio

from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata

from .config import Config
from .renderer import render_markdown_to_base64

__plugin_meta__ = PluginMetadata(
    name="nonebot_plugin_markdown2img",
    description="可作为函数调用的Markdown渲染图片插件",
    usage="`md2img` + 想要生成图片的markdown文本",
    type="application",
    homepage="https://github.com/ANGJustinl/nonebot_plugin_markdown2img",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "ANGJustinl angjustinl@gmail.com"},
)

md_command = on_command("md2img", aliases={"markdown2img", "markdown2image", "md2image"}, priority=5)


@md_command.handle()
async def handle_first_receive(args: Message = CommandArg()):
    md_text = args.extract_plain_text().strip()
    if not md_text:
        await md_command.finish("请发送需要格式化的Markdown文本。")

    # await md_command.send( "markdown图片生成中...请稍等...（如文本量大则响应时间稍久）")
    try:
        image_base64 = await asyncio.to_thread(
            render_markdown_to_base64,
            md_text,
        )
        await md_command.send(MessageSegment.image(file=image_base64))
    except Exception as e:
        logger.error(f"Markdown渲染图片失败: {e}")
        await md_command.finish(f"Markdown渲染图片失败，原因:{e}. 请检查日志。")
