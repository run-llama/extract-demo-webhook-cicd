from pydantic import BaseModel, Field
from typing import Optional


class InvoiceSchema(BaseModel):
    """Schema for extracting key fields from receipt/invoice images.

    Supports merchant name, transaction date, and total amount extraction.
    """

    merchant_name: Optional[str] = Field(
        default=None,
        description="The name of the store or merchant on the receipt",
    )
    date: Optional[str] = Field(
        default=None,
        description="The date of the transaction, in YYYY-MM-DD format",
    )
    total: Optional[str] = Field(
        default=None,
        description="The total amount charged, including currency symbol if present",
    )
