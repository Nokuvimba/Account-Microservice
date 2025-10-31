from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, DateTime, Numeric, Index, UniqueConstraint, ForeignKey

# Define the base class for declarative models
class Base(DeclarativeBase):
    pass

# Define the AccountDB model
class AccountDB(Base):
    __tablename__ = "accounts" 

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_number: Mapped[str] = mapped_column(String(6), unique=True, index=True)
    account_name: Mapped[str] = mapped_column(String(128))
    balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    # timezone-aware default on the server
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
 # Relationship to TransactionDB
    transactions: Mapped[list["TransactionDB"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )

# Define the TransactionDB model
class TransactionDB(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
# Relationship back to AccountDB
    account: Mapped[AccountDB] = relationship(back_populates="transactions")

# Define indexes and constraints
Index("ix_accounts_created_at", AccountDB.created_at)
UniqueConstraint("account_number", name="uq_accounts_account_number")