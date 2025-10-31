from datetime import datetime
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, Field, condecimal
from pydantic import ConfigDict  # Pydantic v2

# Define reusable types
AccountNumber = Annotated[str, Field(pattern=r"^[A-Z]{2}\d{4}$")]
Money = condecimal(max_digits=18, decimal_places=2)

# Define Pydantic models for account creation and reading
class AccountCreate(BaseModel):
    account_number: AccountNumber
    account_name: str
    opening_balance: Money | None = Decimal("0.00")

#
class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_number: AccountNumber
    account_name: str
    balance: Money
    currency: str = "EUR"
    created_at: datetime