from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional, Literal

from pydantic import BaseModel, Field, ConfigDict
from pydantic.types import condecimal

# enforcing AA9999 style (e.g., TA1234)
AccountNumber = Annotated[str, Field(pattern=r"^[A-Z]{2}\d{4}$", examples=["TA1234"])]
Money = condecimal(max_digits=18, decimal_places=2)

# ---- accounts ----

class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int 
    account_number: AccountNumber
    account_name: str
    balance: Money
    currency: str = "EUR"
    created_at: datetime
    is_active: bool = True

# ---- transactions ----
class DepositCreate(BaseModel):
    amount: Money
    description: str | None = None

class WithdrawCreate(BaseModel):
    amount: Money
    description: str | None = None

class TransferCreate(BaseModel):
    to_account_number: AccountNumber
    amount: Money
    description: str | None = None

class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    account_id: int
    tx_type: Literal["deposit", "withdrawal", "transfer_out", "transfer_in"]
    amount: Money
    description: str | None
    sender_name: Optional[str]
    sender_account_number: Optional[str]
    receiver_name: Optional[str]
    receiver_account_number: Optional[str]
    created_at: datetime
