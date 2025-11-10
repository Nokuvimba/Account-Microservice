from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, DateTime, Numeric, ForeignKey, UniqueConstraint, Index, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AccountDB(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Use transactions.account_id as the owning FK
    transactions: Mapped[list["TransactionDB"]] = relationship(
        "TransactionDB",
        back_populates="account",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [TransactionDB.account_id],
    )

    __table_args__ = (UniqueConstraint("account_number", name="uq_accounts_account_number"),)


class TransactionDB(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True, nullable=False)


    tx_type: Mapped[str] = mapped_column(String(16), nullable=False)  # deposit | withdrawal | transfer_out | transfer_in
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), default=None)

    sender_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True) 
    sender_account_number: Mapped[str | None] = mapped_column(String(32), index=True, default=None)
    sender_name: Mapped[str | None] = mapped_column(String(128), default=None)

    receiver_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    receiver_account_number: Mapped[str | None] = mapped_column(String(32), index=True, default=None)
    receiver_name: Mapped[str | None] = mapped_column(String(128), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
#
    account: Mapped["AccountDB"] = relationship("AccountDB", foreign_keys=[account_id], back_populates="transactions")
    sender_account: Mapped["AccountDB"] = relationship("AccountDB", foreign_keys=[sender_account_id], viewonly=True)
    receiver_account: Mapped["AccountDB"] = relationship("AccountDB", foreign_keys=[receiver_account_id], viewonly=True)

    __table_args__ = (Index("ix_tx_account_id_created", "account_id", "created_at", "id"),)
