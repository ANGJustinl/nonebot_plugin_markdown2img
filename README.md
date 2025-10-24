<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-markdown2img

_✨ 可作为函数调用的Markdown渲染图片插件 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/ANGJustinl/nonebot_plugin_markdown2img.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot_plugin_markdown2img">
    <img src="https://img.shields.io/pypi/v/nonebot_plugin_markdown2img.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="python">

</div>

## 📖 介绍

可作为函数调用的Markdown渲染图片插件

### 直接作为插件使用

安装并配置好插件后，无需额外导入函数，直接在群聊中发送指令即可使用。例如：

发送 `md2img # 标题\n\n这是一段**粗体**文本。`，即可收到渲染后的图片。

### 作为函数调用
你可以直接导入并使用渲染函数：

```python
from nonebot_plugin_markdown2img.renderer import render_markdown_to_base64
# or
# from src.nonebot_plugin_markdown2img.renderer import render_markdown_to_base64

# 渲染Markdown文本为base64图片
markdown_text = "# 标题\n\n这是一段**粗体**文本。"
base64_image = render_markdown_to_base64(markdown_text)
```


## 💿 安装

> 若遇到缺少`Markdown渲染图片失败，原因:Linkify enabled but not installed.. 请检查日志。`报错,  请额外安装`linkify-it-py`!

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot_plugin_markdown2img

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot_plugin_markdown2img
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot_plugin_markdown2img
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot_plugin_markdown2img
</details>
<details>
<summary>conda</summary>

    conda install nonebot_plugin_markdown2img
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_markdown2img"]

</details>

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| font_path | 否 | 无 | 字体文件路径 |
| disable_gpu | 否 | True | 是否禁用Gpu |

## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| md2img | 群员 | 否 | 群聊 | `md2img` + 想要生成图片的markdown文本 |

### 效果图
![test_markdown_output](test_markdown_output.png)

## 🙏 特别感谢
感谢 [nonebot_plugin_easymarkdown](https://github.com/phquathi/nonebot_plugin_easymarkdown) 项目提供的灵感和参考。
