from pydantic import BaseModel, Field


class ProposedChange(BaseModel):
    """One repository-relative file: its complete new content, or its deletion."""

    file_path: str = Field(description="The repository-relative path of one file, never a directory.")
    content: str = Field(default="", description="The file's complete new content; empty when it is deleted.")
    delete: bool = Field(default=False, description="True to delete this existing file instead of writing it.")
