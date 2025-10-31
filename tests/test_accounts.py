def test_create_account_201(client): # Create account successfully
    payload = {
        "account_number": "AB1234",
        "account_name": "Natalie Main",
        "opening_balance": "100.00"
    }
    r = client.post("/accounts", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["account_number"] == "AB1234"
    assert body["balance"] == "100.00"
    # Verify default currency
    assert body["currency"] == "EUR"            

# Attempt to create duplicate account number
def test_duplicate_account_number_409(client):
    payload = {"account_number": "ZZ9999", "account_name": "Dup", "opening_balance": "0.00"}
    assert client.post("/accounts", json=payload).status_code == 201
    assert client.post("/accounts", json=payload).status_code == 409
    
 # Attempt to create account with invalid account number
def test_invalid_account_number_422(client):
    payload = {"account_number": "123456", "account_name": "Invalid", "opening_balance": "0.00"}
    r = client.post("/accounts", json=payload)
    assert r.status_code == 422    
    
# Retrieve created account successfully
def test_get_account_200(client):
    payload = {
        "account_number": "CD5678",
        "account_name": "Oliver Twist",
        "opening_balance": "250.00"
    }
    r = client.post("/accounts", json=payload)
    assert r.status_code == 201
    account_id = r.json()["id"]

    r = client.get(f"/accounts/{account_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["account_number"] == "CD5678"
    assert body["balance"] == "250.00"
    
# Attempt to retrieve unknown account ID
def test_get_unknown_id_404(client):
    r = client.get("/accounts/999999")
    assert r.status_code == 404
    
# Health check endpoint
def test_health_check_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}