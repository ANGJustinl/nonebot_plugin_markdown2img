from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    markdown2img_font_path: Optional[str] = None
    markdown2img_disable_gpu: Optional[bool] = True
    markdown2img_disable_linkify: Optional[bool] = True
    pass
