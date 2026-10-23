from datetime import date

from pydantic import BaseModel, Field


class Security(BaseModel):
    isin: str
    name: str
    listing_symbol: str
    country: str
    main_exchange: str


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SourceQuote(BaseModel):
    source_url: str = Field(description="URL of the page that states the fact, exactly as passed to fetch_page.")
    quote: str = Field(
        description="One sentence or table row copied verbatim from that page's fetch_page text that states the fact."
    )


class DividendAnswer(BaseModel):
    announced: bool = Field(
        description="True only when an official source announces an upcoming dividend for this security."
    )
    ex_date: date | None = Field(description="Ex-dividend date on the listing exchange, when a source states it.")
    ex_date_evidence: SourceQuote | None = Field(description="Quote stating ex_date.")
    record_date: date | None = Field(description="Record date, when a source states it.")
    record_date_evidence: SourceQuote | None = Field(description="Quote stating record_date.")
    payment_date: date | None = Field(description="Payment date, when a source states it.")
    payment_date_evidence: SourceQuote | None = Field(description="Quote stating payment_date.")
    amount: float | None = Field(description="Gross dividend per share for this payment, as stated by the source.")
    currency: str | None = Field(description="ISO 4217 currency of amount.")
    amount_evidence: SourceQuote | None = Field(description="Quote stating amount.")
    announced_on: date | None = Field(description="Date the source was published.")
    summary: str = Field(description="One or two sentences on what was found, or why no upcoming dividend was found.")
