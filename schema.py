from pydantic import BaseModel, Field
from typing import Optional


class InvoiceSchema(BaseModel):
    """Schema for extracting key fields from receipt/invoice images.

    Supports merchant name, transaction date, and total amount extraction.
    """

    merchant_name: Optional[str] = Field(
        default=None,
        description="The name of the store, merchant, or vendor shown on the receipt or invoice",
    )
    date: Optional[str] = Field(
        default=None,
        description="The date of the transaction or invoice, in YYYY-MM-DD format",
    )
    total: Optional[str] = Field(
        default=None,
        description="The total amount charged including tax, with currency symbol if present",
    )
