# Helpers
# --------------------------
def _create_account(client, num="AB1234", name="Test User", bal="100.00"):
    r = client.post("/accounts", json={
        "account_number": num,
        "account_name": name,
        "opening_balance": bal
    })
    assert r.status_code == 201, r.text
    body = r.json()
    return body["id"], body["account_number"]


# --------------------------
# Accounts
# --------------------------
def test_create_account_201(client):
    r = client.post("/accounts", json={
        "account_number": "AC1111",
        "account_name": "Natalie Main",
        "opening_balance": "100.00",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["account_number"] == "AC1111"
    assert body["balance"] == "100.00"
    assert body["currency"] == "EUR"


def test_duplicate_account_number_409(client):
    payload = {"account_number": "ZZ9999", "account_name": "Dup", "opening_balance": "0.00"}
    assert client.post("/accounts", json=payload).status_code == 201
    assert client.post("/accounts", json=payload).status_code == 409


def test_invalid_account_number_422(client):
    # Fails regex: needs AA9999
    payload = {"account_number": "123456", "account_name": "Invalid", "opening_balance": "0.00"}
    r = client.post("/accounts", json=payload)
    assert r.status_code == 422


def test_get_account_by_id_200(client):
    acc_id, acc_num = _create_account(client, num="CD5678", name="Oliver Twist", bal="250.00")
    r = client.get(f"/accounts/{acc_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["account_number"] == "CD5678"
    assert body["balance"] == "250.00"


def test_get_unknown_id_404(client):
    assert client.get("/accounts/999999").status_code == 404


def test_health_check_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_update_account_by_id(client):
    acc_id, acc_num = _create_account(client, num="UP1111", name="Before Update", bal="100.00")
    update_data = {
        "account_number": "UP1111",
        "account_name": "After Update",
        "opening_balance": "200.00"
    }
    r = client.put(f"/accounts/{acc_id}", json=update_data)
    assert r.status_code == 200
    body = r.json()
    assert body["account_name"] == "After Update"
    assert body["balance"] == "200.00"


def test_update_account_not_found(client):
    update_data = {"account_number": "XX9999", "account_name": "Ghost Account", "opening_balance": "0.00"}
    assert client.put("/accounts/9999", json=update_data).status_code == 404


def test_delete_account(client):
    acc_id, acc_num = _create_account(client, num="DD1111", name="To Delete", bal="50.00")
    assert client.delete(f"/accounts/{acc_id}").status_code == 200
    assert client.get(f"/accounts/{acc_id}").status_code == 404


def test_delete_account_not_found(client):
    assert client.delete("/accounts/9999").status_code == 404



# Transactions 

def test_deposit_transaction_by_number(client):
    acc_id, acc_num = _create_account(client, num="TD0001", bal="10.00")
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={
        "amount": "5.50", "description": "top-up"
    })
    assert r.status_code == 201, r.text
    acc = client.get(f"/accounts/{acc_id}").json()
    assert acc["balance"] == "15.50"


def test_withdrawal_transaction_by_number(client):
    acc_id, acc_num = _create_account(client, num="TW0001", bal="20.00")
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={
        "amount": "7.00", "description": "atm"
    })
    assert r.status_code == 201, r.text
    acc = client.get(f"/accounts/{acc_id}").json()
    assert acc["balance"] == "13.00"


def test_insufficient_funds_withdraw(client):
    acc_id, acc_num = _create_account(client, num="TW0002", bal="5.00")
    r = client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "10.00"})
    assert r.status_code == 400
    assert r.json()["detail"] == "Insufficient funds."


def test_negative_amount_rejected_deposit(client):
    acc_id, acc_num = _create_account(client, num="TE0001", bal="5.00")
    r = client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "-1.00"})
    assert r.status_code == 400


def test_list_transactions_by_number(client):
    acc_id, acc_num = _create_account(client, num="TL0001", bal="10.00")
    client.post(f"/accounts/by-number/{acc_num}/deposit", json={"amount": "2.00"})
    client.post(f"/accounts/by-number/{acc_num}/withdraw", json={"amount": "1.00"})
    r = client.get(f"/accounts/by-number/{acc_num}/transactions")
    assert r.status_code == 200
    items = r.json()
    kinds = [i["tx_type"] for i in items]
    assert "deposit" in kinds and "withdrawal" in kinds


def test_transfer_success_by_number(client):
    s_id, s_num = _create_account(client, "TX1001", "Sender", "50.00")
    r_id, r_num = _create_account(client, "TX2002", "Receiver", "5.00")

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": r_num,
        "amount": "12.34",
        "description": "lunch"
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body[0]["tx_type"] == "transfer_out"
    assert body[1]["tx_type"] == "transfer_in"

    s = client.get(f"/accounts/{s_id}").json()
    assert s["balance"] == "37.66"

    rcv = client.get(f"/accounts/by-number/{r_num}").json()
    assert rcv["balance"] == "17.34"


def test_transfer_insufficient_funds_by_number(client):
    s_id, s_num = _create_account(client, "TX3003", "Poor", "1.00")
    r_id, r_num = _create_account(client, "TX4004", "Rich", "0.00")

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": r_num, "amount": "2.00"
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Insufficient funds."


def test_transfer_to_self_rejected_by_number(client):
    s_id, s_num = _create_account(client, "TX5005", "Narcissist", "100.00")

    r = client.post(f"/accounts/by-number/{s_num}/transfer", json={
        "to_account_number": s_num, "amount": "10.00"
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "Cannot transfer to the same account."
