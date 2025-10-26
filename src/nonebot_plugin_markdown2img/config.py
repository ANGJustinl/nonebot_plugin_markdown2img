from pydantic import BaseModel


class Config(BaseModel):
    markdown2img_font_path: str | None = None
    markdown2img_disable_gpu: bool | None = True
    markdown2img_disable_linkify: bool | None = True
    pass
