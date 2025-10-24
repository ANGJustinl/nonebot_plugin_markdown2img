from typing import Optional
from pydantic import BaseModel


class Config(BaseModel):
    font_path: Optional[str] = None
    disable_gpu: Optional[bool] = True
    disable_linkify: Optional[bool] = True
    pass
