# app/main.py
import os
import time
import random
import string
from decimal import Decimal, ROUND_HALF_UP
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pybreaker import CircuitBreakerError

from app.database import engine, get_db
from app.circuit import login_cb
from app.models import Base, AccountDB, TransactionDB
from app.schemas import (
    AccountRead,
    DepositCreate, WithdrawCreate, TransferCreate,
    TransactionRead,
)
from app.publisher import publish_transaction_event

# -------------------------
# Service-to-service config
# -------------------------

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(
    title="Account Microservice",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOGIN_BASE_URL = os.getenv("LOGIN_BASE_URL", "http://localhost:8000")
# ---------- helpers ----------
@login_cb
def fetch_user_from_login(user_id: int) -> dict[str, Any]:
    url = f"{LOGIN_BASE_URL}/api/users/{user_id}"

    with httpx.Client() as client:
        r = client.get(url, timeout=5.0)

    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="User not found")

    r.raise_for_status()
    return r.json()

def safe_fetch_user_from_login(user_id: int) -> dict[str, Any]:
    try:
        return fetch_user_from_login(user_id)

    except CircuitBreakerError:
        raise HTTPException(
            status_code=503,
            detail="Login service temporarily unavailable (circuit open)."
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Signup/User service unavailable."
        )

    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="Signup/User service returned an error."
        )

# def fetch_user_from_login(user_id: int) -> dict[str, Any]:
#     url = f"{LOGIN_BASE_URL}/api/users/{user_id}"
#     print("Calling Login URL:", url)

#     try:
#         with httpx.Client() as client:
#             r = client.get(url, timeout=5.0)

#         if r.status_code == 404:
#             raise HTTPException(status_code=404, detail="User not found in Signup/User service.")

#         r.raise_for_status()
#         return r.json()
        
#     except CircuitBreakerError:
#         raise HTTPException(status_code=503, detail="Login service temporarily unavailable (circuit open).")
#     except httpx.RequestError:
#         raise HTTPException(status_code=503, detail="Signup/User service unavailable.")
#     except httpx.HTTPStatusError:
#         raise HTTPException(status_code=502, detail="Signup/User service returned an error.")
    
def money(x: Decimal) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def get_by_number(db: Session, account_number: str) -> AccountDB:
    row = db.query(AccountDB).filter(AccountDB.account_number == account_number).first()
    if not row:
        raise HTTPException(status_code=404, detail="Account number not found.")
    return row

def get_by_user_id(db: Session, user_id: int) -> AccountDB:
    row = db.query(AccountDB).filter(AccountDB.user_id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Account for this user not found.")
    return row

def generate_account_number() -> str:
    letters = "".join(random.choice(string.ascii_uppercase) for _ in range(2))
    digits = random.randint(0, 9999)
    return f"{letters}{digits:04d}"


# ---------- health ----------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/proxy-user/{user_id}")
def proxy_user(user_id: int):
    user = safe_fetch_user_from_login(user_id)
    return {"account_service": True, "login_user": user}


# ---------- accounts (ONLY from user_id) ----------

@app.post("/accounts/from-user/{user_id}", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account_from_user(user_id: int, db: Session = Depends(get_db)):
    # 1) confirm user exists + grab their details
    user = safe_fetch_user_from_login(user_id)

    # 2) prevent duplicates (one user -> one account)
    existing = db.query(AccountDB).filter(AccountDB.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account already exists for this user.")

    # 3) create account (account_name derived from user full_name)
    row = AccountDB(
        user_id=user_id,
        account_number=generate_account_number(),
        account_name=user.get("full_name", f"User {user_id}"),
        balance=Decimal("0.00"),
        currency="EUR",
    )
    try:
        db.add(row); db.commit(); db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create account (conflict).")

@app.get("/accounts/by-user/{user_id}", response_model=AccountRead)
def get_account_by_user(user_id: int, db: Session = Depends(get_db)):
    return get_by_user_id(db, user_id)

@app.get("/accounts/by-user/{user_id}/details")
def get_account_details(user_id: int, db: Session = Depends(get_db)):
    acct = get_by_user_id(db, user_id)
    user = safe_fetch_user_from_login(user_id)

    return {
        "account": {
            "id": acct.id,
            "user_id": acct.user_id,
            "account_number": acct.account_number,
            "account_name": acct.account_name,
            "balance": str(acct.balance),
            "currency": acct.currency,
            "created_at": acct.created_at,
        },
        "user": user,
    }

@app.delete("/accounts/by-user/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account_by_user(user_id: int, db: Session = Depends(get_db)):
    row = db.query(AccountDB).filter(AccountDB.user_id == user_id).first()
    if not row:
        # idempotent (nice for service-to-service deletes)
        return
    db.delete(row)
    db.commit()
    return

# ---------- transactions (KEEP as-is) ----------

@app.post("/accounts/by-number/{account_number}/deposit",
          response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def deposit(account_number: str, data: DepositCreate, db: Session = Depends(get_db)):
    receiver = get_by_number(db, account_number)
    amt = money(data.amount)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero.")

    receiver.balance = money(Decimal(receiver.balance) + amt)
    tx = TransactionDB(
        account_id=receiver.id,
        tx_type="deposit",
        amount=amt,
        description=data.description,
        sender_name="External",
        receiver_account_id=receiver.id,
        receiver_account_number=receiver.account_number,
        receiver_name=receiver.account_name,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    publish_transaction_event(
        event_type="deposit",
        transaction_id=tx.id,
        account_id=receiver.id,
        account_number=receiver.account_number,
        account_name=receiver.account_name,
        amount=amt,
    ) 
    return tx

@app.post("/accounts/by-number/{account_number}/withdraw",
          response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def withdraw(account_number: str, data: WithdrawCreate, db: Session = Depends(get_db)):
    sender = get_by_number(db, account_number)
    amt = money(data.amount)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero.")
    if money(sender.balance) < amt:
        raise HTTPException(status_code=400, detail="Insufficient funds.")

    sender.balance = money(Decimal(sender.balance) - amt)
    tx = TransactionDB(
        account_id=sender.id,
        tx_type="withdrawal",
        amount=amt,
        description=data.description,
        sender_account_id=sender.id,
        sender_account_number=sender.account_number,
        sender_name=sender.account_name,
        receiver_name="ATM/External",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    publish_transaction_event(
        event_type="withdrawal",
        transaction_id=tx.id,
        account_id=sender.id,
        account_number=sender.account_number,
        account_name=sender.account_name,
        amount=amt,
    )

    return tx

@app.post("/accounts/by-number/{account_number}/transfer",
          response_model=list[TransactionRead], status_code=status.HTTP_201_CREATED)
def transfer(account_number: str, data: TransferCreate, db: Session = Depends(get_db)):
    sender = get_by_number(db, account_number)
    receiver = get_by_number(db, data.to_account_number)

    if sender.id == receiver.id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account.")

    amt = money(data.amount)
    if money(sender.balance) < amt:
        raise HTTPException(status_code=400, detail="Insufficient funds.")

    sender.balance = money(Decimal(sender.balance) - amt)
    receiver.balance = money(Decimal(receiver.balance) + amt)

    out_tx = TransactionDB(
        account_id=sender.id,
        tx_type="transfer_out",
        amount=amt,
        description=data.description,
        sender_account_id=sender.id,
        sender_account_number=sender.account_number,
        sender_name=sender.account_name,
        receiver_account_id=receiver.id,
        receiver_account_number=receiver.account_number,
        receiver_name=receiver.account_name,
    )

    in_tx = TransactionDB(
        account_id=receiver.id,
        tx_type="transfer_in",
        amount=amt,
        description=data.description or f"From {sender.account_name}",
        sender_account_id=sender.id,
        sender_account_number=sender.account_number,
        sender_name=sender.account_name,
        receiver_account_id=receiver.id,
        receiver_account_number=receiver.account_number,
        receiver_name=receiver.account_name,
    )

    db.add_all([out_tx, in_tx])
    db.commit()
    db.refresh(out_tx)
    db.refresh(in_tx)

    # Event for sender (money leaving)
    publish_transaction_event(
        event_type="transfer_out",
        transaction_id=out_tx.id,
        account_id=sender.id,
        account_number=sender.account_number,
        account_name=sender.account_name,
        counterparty_account_number=receiver.account_number,
        counterparty_name=receiver.account_name,
        amount=amt,
    )

    # Event for receiver (money arriving)
    publish_transaction_event(
        event_type="transfer_in",
        transaction_id=in_tx.id,
        account_id=receiver.id,
        account_number=receiver.account_number,
        account_name=receiver.account_name,
        counterparty_account_number=sender.account_number,
        counterparty_name=sender.account_name,
        amount=amt,
    )

    return [out_tx, in_tx]

@app.get("/accounts/by-number/{account_number}/transactions", response_model=list[TransactionRead])
def list_transactions_for_number(account_number: str, db: Session = Depends(get_db)):
    acct = get_by_number(db, account_number)
    return (
        db.query(TransactionDB)
        .filter(TransactionDB.account_id == acct.id)
        .order_by(TransactionDB.created_at.desc(), TransactionDB.id.desc())
        .all()
    )

@app.get("/transactions", response_model=list[TransactionRead])
def list_transactions(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    return (
        db.query(TransactionDB)
        .order_by(TransactionDB.created_at.desc(), TransactionDB.id.desc())
        .offset(offset).limit(limit).all()
    )

