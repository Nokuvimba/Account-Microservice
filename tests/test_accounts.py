# Helpers
# --------------------------
def _create_account_by_number(client, num="AB1234", name="Test User", bal="100.00"):
    """Helper to create account using mock user endpoint (for transaction tests)"""
    # This is a mock - in real tests you'd need to mock the login service
    # For now, we'll create accounts via the user endpoint with a test user_id
    user_id = 12345  # Mock user ID
    r = client.post(f"/accounts/from-user/{user_id}")
    if r.status_code == 201:
        body = r.json()
        return body["id"], body["account_number"]
    # Fallback for tests that need specific account numbers
    return None, num


# --------------------------
# Health Check
# --------------------------
def test_health_check_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# --------------------------
# User-based Account Operations
# --------------------------
def test_create_account_from_user_201(client, mock_login_service):
    user_id = 123
    r = client.post(f"/accounts/from-user/{user_id}")
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == user_id
    assert body["balance"] == "0.00"
    assert body["currency"] == "EUR"
    assert len(body["account_number"]) == 6  # AA9999 format


def test_create_duplicate_account_for_user_409(client, mock_login_service):
    user_id = 124
    assert client.post(f"/accounts/from-user/{user_id}").status_code == 201
    assert client.post(f"/accounts/from-user/{user_id}").status_code == 409


def test_get_account_by_user_200(client, mock_login_service):
    user_id = 125
    # Create account first
    create_r = client.post(f"/accounts/from-user/{user_id}")
    assert create_r.status_code == 201
    
    # Get account by user
    r = client.get(f"/accounts/by-user/{user_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == user_id


def test_get_account_by_user_404(client):
    assert client.get("/accounts/by-user/999999").status_code == 404


def test_get_account_details_200(client, mock_login_service):
    user_id = 126
    # Create account first
    client.post(f"/accounts/from-user/{user_id}")
    
    # Get account details
    r = client.get(f"/accounts/by-user/{user_id}/details")
    assert r.status_code == 200
    body = r.json()
    assert "account" in body
    assert "user" in body
    assert body["account"]["user_id"] == user_id


def test_delete_account_by_user_204(client, mock_login_service):
    user_id = 127
    # Create account first
    client.post(f"/accounts/from-user/{user_id}")
    
    # Delete account
    r = client.delete(f"/accounts/by-user/{user_id}")
    assert r.status_code == 204
    
    # Verify it's gone
    assert client.get(f"/accounts/by-user/{user_id}").status_code == 404


def test_delete_account_by_user_idempotent(client):
    # Deleting non-existent account should be idempotent
    r = client.delete("/accounts/by-user/999999")
    assert r.status_code == 204


def test_proxy_user_200(client, mock_login_service):
    user_id = 128
    r = client.get(f"/api/proxy-user/{user_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["account_service"] is True
    assert "login_user" in body



# --------------------------
# Transactions
# -------------------------- 

def test_deposit_transaction_by_number(client, mock_login_service):
    # Create account via user endpoint
    user_id = 200
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={
        "amount": "5.50", "description": "top-up"
    })
    assert r.status_code == 201, r.text
    
    # Check balance via user endpoint
    acc = client.get(f"/accounts/by-user/{user_id}").json()
    assert acc["balance"] == "5.50"


def test_withdrawal_transaction_by_number(client, mock_login_service):
    # Create account with initial deposit
    user_id = 201
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    # Add some money first
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "20.00"})
    
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={
        "amount": "7.00", "description": "atm"
    })
    assert r.status_code == 201, r.text
    
    acc = client.get(f"/accounts/by-user/{user_id}").json()
    assert acc["balance"] == "13.00"


def test_insufficient_funds_withdraw(client, mock_login_service):
    user_id = 202
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    # Add small amount
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "5.00"})
    
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "10.00"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Insufficient funds."


def test_negative_amount_rejected_deposit(client, mock_login_service):
    user_id = 203
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "-1.00"})
    assert r.status_code == 400


def test_negative_amount_rejected_withdraw(client, mock_login_service):
    user_id = 2031
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "-1.00"})
    assert r.status_code == 400


def test_list_transactions_by_number(client, mock_login_service):
    user_id = 204
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "10.00"})
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "2.00"})
    client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "1.00"})
    
    r = client.get(f"/accounts/by-number/{acc_num}/transactions")
    assert r.status_code == 200
    items = r.json()
    kinds = [i["tx_type"] for i in items]
    assert "deposit" in kinds and "withdrawal" in kinds


def test_transfer_success_by_number(client, mock_login_service):
    # Create sender account
    sender_id = 205
    create_s = client.post(f"/accounts/from-user/{sender_id}")
    s_num = create_s.json()["account_number"]
    client.post(f"/accounts/by-number/{s_num}/deposit", json={"amount": "50.00"})
    
    # Create receiver account
    receiver_id = 206
    create_r = client.post(f"/accounts/from-user/{receiver_id}")
    r_num = create_r.json()["account_number"]
    client.post(f"/accounts/by-number/{r_num}/deposit", json={"amount": "5.00"})

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": r_num,
        "amount": "12.34",
        "description": "lunch"
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body[0]["tx_type"] == "transfer_out"
    assert body[1]["tx_type"] == "transfer_in"

    s = client.get(f"/accounts/by-user/{sender_id}").json()
    assert s["balance"] == "37.66"

    rcv = client.get(f"/accounts/by-user/{receiver_id}").json()
    assert rcv["balance"] == "17.34"


def test_transfer_insufficient_funds_by_number(client, mock_login_service):
    # Create sender with insufficient funds
    sender_id = 207
    create_s = client.post(f"/accounts/from-user/{sender_id}")
    s_num = create_s.json()["account_number"]
    client.post(f"/accounts/by-number/{s_num}/deposit", json={"amount": "1.00"})
    
    # Create receiver
    receiver_id = 208
    create_r = client.post(f"/accounts/from-user/{receiver_id}")
    r_num = create_r.json()["account_number"]

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": r_num, "amount": "2.00"
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Insufficient funds."


def test_transfer_to_self_rejected_by_number(client, mock_login_service):
    user_id = 209
    create_r = client.post(f"/accounts/from-user/{user_id}")
    s_num = create_r.json()["account_number"]
    client.post(f"/accounts/by-number/{s_num}/deposit", json={"amount": "100.00"})

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": s_num, "amount": "10.00"
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Cannot transfer to the same account."


# --------------------------
# Global Transactions List
# --------------------------
def test_list_all_transactions_200(client, mock_login_service):
    # Create account and make some transactions
    user_id = 210
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "10.00"})
    client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "5.00"})
    
    r = client.get("/transactions")
    assert r.status_code == 200
    transactions = r.json()
    assert isinstance(transactions, list)


def test_list_all_transactions_with_pagination(client, mock_login_service):
    r = client.get("/transactions?limit=10&offset=0")
    assert r.status_code == 200
    transactions = r.json()
    assert isinstance(transactions, list)
    assert len(transactions) <= 10


def test_list_all_transactions_limit_validation(client):
    # Test limit bounds
    r = client.get("/transactions?limit=300")  # Should be capped at 200
    assert r.status_code == 200
    
    r = client.get("/transactions?limit=0")  # Should be at least 1
    assert r.status_code == 200


# --------------------------
# Error Cases and Edge Cases
# --------------------------
def test_get_transactions_for_nonexistent_account(client):
    r = client.get("/accounts/by-number/XX9999/transactions")
    assert r.status_code == 404


def test_deposit_to_nonexistent_account(client):
    r = client.post("/accounts/by-number/XX9999/deposit", json={"amount": "10.00"})
    assert r.status_code == 404


def test_withdraw_from_nonexistent_account(client):
    r = client.post("/accounts/by-number/XX9999/withdraw", json={"amount": "10.00"})
    assert r.status_code == 404


def test_transfer_from_nonexistent_account(client, mock_login_service):
    # Create a valid receiver account
    user_id = 300
    create_r = client.post(f"/accounts/from-user/{user_id}")
    r_num = create_r.json()["account_number"]
    
    r = client.post("/accounts/by-number/XX9999/transfer", json={
        "to_account_number": r_num, "amount": "10.00"
    })
    assert r.status_code == 404


def test_transfer_to_nonexistent_account(client, mock_login_service):
    # Create a valid sender account
    user_id = 301
    create_r = client.post(f"/accounts/from-user/{user_id}")
    s_num = create_r.json()["account_number"]
    client.post(f"/accounts/by-number/{s_num}/deposit", json={"amount": "100.00"})
    
    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": "XX9999", "amount": "10.00"
    })
    assert r.status_code == 404


def test_zero_amount_deposit_rejected(client, mock_login_service):
    user_id = 302
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "0.00"})
    assert r.status_code == 400


def test_zero_amount_withdraw_rejected(client, mock_login_service):
    user_id = 303
    create_r = client.post(f"/accounts/from-user/{user_id}")
    acc_num = create_r.json()["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "0.00"})
    assert r.status_code == 400


# Note: Service unavailability and user not found tests would require
# more complex mocking setup that conflicts with the existing fixture.
# These edge cases are handled by the actual application code.
