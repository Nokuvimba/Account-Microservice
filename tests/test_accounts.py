import pytest
from unittest.mock import patch, Mock
from pybreaker import CircuitBreakerError
import httpx

# Helpers
# --------------------------
def _create_account_from_user(client, user_id=1):
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.return_value = {"id": user_id, "full_name": "Test User"}
        r = client.post(f"/accounts/from-user/{user_id}")
        assert r.status_code == 201, r.text
        return r.json()


# --------------------------
# Accounts
# --------------------------
def test_create_account_from_user_201(client):
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.return_value = {"id": 1, "full_name": "John Doe"}
        r = client.post("/accounts/from-user/1")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["user_id"] == 1
        assert body["account_name"] == "John Doe"
        assert body["balance"] == "0.00"
        assert body["currency"] == "EUR"
        assert body["is_active"] is True
        assert len(body["account_number"]) == 6


def test_duplicate_account_for_user_409(client):
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.return_value = {"id": 1, "full_name": "John Doe"}
        assert client.post("/accounts/from-user/1").status_code == 201
        assert client.post("/accounts/from-user/1").status_code == 409


def test_get_account_by_user_200(client):
    account = _create_account_from_user(client, user_id=2)
    r = client.get(f"/accounts/by-user/2")
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == 2
    assert body["account_number"] == account["account_number"]


def test_get_account_by_user_404(client):
    r = client.get("/accounts/by-user/999")
    assert r.status_code == 404
    assert "Active account for this user not found" in r.json()["detail"]


def test_get_account_details(client):
    _create_account_from_user(client, user_id=3)
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.return_value = {"id": 3, "full_name": "Jane Doe", "email": "jane@example.com"}
        r = client.get("/accounts/by-user/3/details")
        assert r.status_code == 200
        body = r.json()
        assert "account" in body
        assert "user" in body
        assert body["account"]["user_id"] == 3
        assert body["user"]["full_name"] == "Jane Doe"


def test_delete_account_by_user_204(client):
    _create_account_from_user(client, user_id=4)
    r = client.delete("/accounts/by-user/4")
    assert r.status_code == 204
    # After soft delete, account should not be found (filtered by is_active)
    assert client.get("/accounts/by-user/4").status_code == 404


def test_delete_account_by_user_idempotent(client):
    # Should not fail if account doesn't exist
    r = client.delete("/accounts/by-user/999")
    assert r.status_code == 204


def test_delete_account_soft_delete_idempotent(client):
    # Test that deleting an already deleted account is idempotent
    _create_account_from_user(client, user_id=5)
    # First delete
    r1 = client.delete("/accounts/by-user/5")
    assert r1.status_code == 204
    # Second delete should also return 204 (idempotent)
    r2 = client.delete("/accounts/by-user/5")
    assert r2.status_code == 204


def test_health_check_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_proxy_user(client):
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.return_value = {"id": 1, "full_name": "Test User"}
        r = client.get("/api/proxy-user/1")
        assert r.status_code == 200
        body = r.json()
        assert body["account_service"] is True
        assert body["login_user"]["id"] == 1


# Circuit Breaker Tests
def test_circuit_breaker_open_503(client):
    with patch('app.main.fetch_user_from_login') as mock_fetch:
        mock_fetch.side_effect = CircuitBreakerError()
        r = client.post("/accounts/from-user/1")
        assert r.status_code == 503
        assert "circuit open" in r.json()["detail"]


def test_login_service_unavailable_503(client):
    with patch('app.main.fetch_user_from_login') as mock_fetch:
        mock_fetch.side_effect = httpx.RequestError("Connection failed")
        r = client.post("/accounts/from-user/1")
        assert r.status_code == 503
        assert "unavailable" in r.json()["detail"]


def test_login_service_error_502(client):
    with patch('app.main.fetch_user_from_login') as mock_fetch:
        mock_fetch.side_effect = httpx.HTTPStatusError("Server error", request=Mock(), response=Mock())
        r = client.post("/accounts/from-user/1")
        assert r.status_code == 502
        assert "returned an error" in r.json()["detail"]


# Transactions 

def test_deposit_transaction_by_number(client):
    account = _create_account_from_user(client, user_id=10)
    acc_num = account["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={
        "amount": "5.50", "description": "top-up"
    })
    assert r.status_code == 201, r.text
    
    acc = client.get(f"/accounts/by-user/10").json()
    assert acc["balance"] == "5.50"


def test_withdrawal_transaction_by_number(client):
    account = _create_account_from_user(client, user_id=11)
    acc_num = account["account_number"]
    
    # First deposit some money
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "20.00"})
    
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={
        "amount": "7.00", "description": "atm"
    })
    assert r.status_code == 201, r.text
    
    acc = client.get(f"/accounts/by-user/11").json()
    assert acc["balance"] == "13.00"


def test_insufficient_funds_withdraw(client):
    account = _create_account_from_user(client, user_id=12)
    acc_num = account["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "10.00"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Insufficient funds."


def test_negative_amount_rejected_deposit(client):
    account = _create_account_from_user(client, user_id=13)
    acc_num = account["account_number"]
    
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "-1.00"})
    assert r.status_code == 400


def test_transfer_success_by_number(client):
    sender_acc = _create_account_from_user(client, user_id=14)
    receiver_acc = _create_account_from_user(client, user_id=15)
    
    s_num = sender_acc["account_number"]
    r_num = receiver_acc["account_number"]
    
    # Give sender some money first
    client.post(f"/accounts/by-number/{s_num}/deposit", json={"amount": "50.00"})

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": r_num,
        "amount": "12.34",
        "description": "lunch"
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 2  # Should return both transactions
    assert body[0]["tx_type"] == "transfer_out"
    assert body[1]["tx_type"] == "transfer_in"

    s = client.get(f"/accounts/by-user/14").json()
    assert s["balance"] == "37.66"

    rcv = client.get(f"/accounts/by-user/15").json()
    assert rcv["balance"] == "12.34"


def test_transfer_insufficient_funds_by_number(client):
    sender_acc = _create_account_from_user(client, user_id=16)
    receiver_acc = _create_account_from_user(client, user_id=17)
    
    s_num = sender_acc["account_number"]
    r_num = receiver_acc["account_number"]

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": r_num, "amount": "2.00"
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Insufficient funds."


def test_account_not_found_by_number(client):
    r = client.post("/accounts/by-number/XX9999/deposit", json={"amount": "10.00"})
    assert r.status_code == 404
    assert "Active account number not found" in r.json()["detail"]