from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from decimal import Decimal

from app.database import engine, get_db
from app.models import Base, AccountDB
from app.schemas import AccountCreate, AccountRead

# Initialize FastAPI app and create database tables
app = FastAPI()
# Create database tables
Base.metadata.create_all(bind=engine)

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}

# Endpoint to create a new account
@app.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)): 
    row = AccountDB(
        account_number=payload.account_number,
        account_name=payload.account_name,
        balance=payload.opening_balance or Decimal("0.00"),
        currency="EUR",
    )
    try: # Try to add the new account to the database
        db.add(row)
        db.commit()
        db.refresh(row)
    except IntegrityError: # Handle unique constraint violation
        db.rollback()
        raise HTTPException(status_code=409, detail="Account number already exists.")
    return row

# retrieve account details by account ID
@app.get("/accounts/{account_id}", response_model=AccountRead)
def get_account(account_id: int, db: Session = Depends(get_db)):
    row = db.get(AccountDB, account_id)
    if not row:
        raise HTTPException(status_code=404, detail="Account not found.")
    return row

# Update account details
@app.put("/accounts/{account_id}", response_model=AccountRead)
def update_account(account_id: int, data: AccountCreate, db: Session = Depends(get_db)):
    account = db.query(AccountDB).filter(AccountDB.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    # Update fields
    account.account_number = data.account_number
    account.account_name = data.account_name
    account.balance = data.opening_balance or account.balance

    db.commit()
    db.refresh(account)
    return account


# Delete an account
@app.delete("/accounts/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    account = db.query(AccountDB).filter(AccountDB.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")

    db.delete(account)
    db.commit()
    return {"message": "Account deleted successfully."}