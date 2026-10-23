from pydantic import BaseModel


class ShellConfig(BaseModel):
    allowed_binaries: list[str]


class PrometheusConfig(BaseModel):
    url: str
