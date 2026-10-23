from pydantic import BaseModel, Field


class ExcerptConfig(BaseModel):
    focus_terms: list[str] = Field(min_length=1)
    window_chars: int = Field(gt=0)
    max_chars: int = Field(gt=0)
