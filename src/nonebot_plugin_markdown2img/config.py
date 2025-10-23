from pydantic import BaseModel


class Config(BaseModel):
    font_path: str | None = None
    disable_gpu: bool | None = True
    pass
