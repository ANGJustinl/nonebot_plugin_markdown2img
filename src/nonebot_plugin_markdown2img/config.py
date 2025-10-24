from pydantic import BaseModel


class Config(BaseModel):
    font_path: str | None = None
    disable_gpu: bool | None = True
    disable_linkify: bool | None = True
    browser: str | None = "chrome"
    browser_executable: str | None = None
    pass
