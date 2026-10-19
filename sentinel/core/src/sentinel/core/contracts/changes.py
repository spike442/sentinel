from pydantic import BaseModel


class ProposedChange(BaseModel):
    """The complete new content of one repository-relative file."""

    file_path: str
    content: str
