# app/main.py
from decimal import Decimal, ROUND_HALF_UP
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.models import Base, AccountDB, TransactionDB
from app.schemas import (
    AccountCreate, AccountRead,
    DepositCreate, WithdrawCreate, TransferCreate,
    TransactionRead,
)

# Lifespan replaces @app.on_event("startup")
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Make sure tables exist on startup (once).
    Base.metadata.create_all(bind=engine)
    yield

# Create the app with lifespan hook
app = FastAPI(
    title="Account Microservice",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS – dev-friendly; tighten `allow_origins` in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- helpers ----------
def money(x: Decimal) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def get_by_number(db: Session, account_number: str) -> AccountDB:
    row = db.query(AccountDB).filter(AccountDB.account_number == account_number).first()
    if not row:
        raise HTTPException(status_code=404, detail="Account number not found.")
    return row

# ---------- health ----------
@app.get("/health")
def health(): return {"status": "ok"}

# ---------- accounts ----------
#creating an account
@app.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)):
    row = AccountDB(
        account_number=payload.account_number,
        account_name=payload.account_name,
        balance=payload.opening_balance or Decimal("0.00"),
        currency="EUR",
    )
    try:
        db.add(row); db.commit(); db.refresh(row); return row
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="Account number already exists.")

@app.get("/accounts", response_model=list[AccountRead])
def list_accounts(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 200))
    return (
        db.query(AccountDB)
        .order_by(AccountDB.created_at, AccountDB.id)
        .offset(offset).limit(limit).all()
    )

@app.get("/accounts/by-number/{account_number}", response_model=AccountRead)
def get_account_by_number(account_number: str, db: Session = Depends(get_db)):
    return get_by_number(db, account_number)

@app.get("/accounts/{account_id}", response_model=AccountRead)
def get_account_by_id(account_id: int, db: Session = Depends(get_db)):
    row = db.query(AccountDB).filter(AccountDB.id == account_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found.")
    return row

@app.put("/accounts/{account_id}", response_model=AccountRead)
def update_account(account_id: int, data: AccountCreate, db: Session = Depends(get_db)):
    row = db.query(AccountDB).filter(AccountDB.id == account_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found.")
    row.account_name = data.account_name
    row.account_number = data.account_number
    row.balance = data.opening_balance or row.balance
    try:
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Account number already exists.")

@app.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    row = db.query(AccountDB).filter(AccountDB.id == account_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Account not found.")
    db.delete(row)
    db.commit()
    return {"message": "Account deleted successfully."}

# ---------- transactions ----------
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
    db.add(tx); db.commit(); db.refresh(tx); return tx

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
    db.add(tx); db.commit(); db.refresh(tx); return tx

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
        account_id=sender.id, tx_type="transfer_out", amount=amt,
        description=data.description,
        sender_account_id=sender.id, sender_account_number=sender.account_number, sender_name=sender.account_name,
        receiver_account_id=receiver.id, receiver_account_number=receiver.account_number, receiver_name=receiver.account_name,
    )
    in_tx = TransactionDB(
        account_id=receiver.id, tx_type="transfer_in", amount=amt,
        description=data.description or f"From {sender.account_name}",
        sender_account_id=sender.id, sender_account_number=sender.account_number, sender_name=sender.account_name,
        receiver_account_id=receiver.id, receiver_account_number=receiver.account_number, receiver_name=receiver.account_name,
    )
    db.add_all([out_tx, in_tx]); db.commit(); db.refresh(out_tx); db.refresh(in_tx)
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
