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
    
def test_update_account(client):
    # Create an account first
    create_data = {
        "account_number": "UP1111",
        "account_name": "Before Update",
        "opening_balance": "100.00"
    }
    create_resp = client.post("/accounts", json=create_data)
    account_id = create_resp.json()["id"]

    # Update the account
    update_data = {
        "account_number": "UP1111",
        "account_name": "After Update",
        "opening_balance": "200.00"
    }
    response = client.put(f"/accounts/{account_id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["account_name"] == "After Update"
    assert response.json()["balance"] == "200.00"


def test_update_account_not_found(client):
    update_data = {
        "account_number": "XX9999",
        "account_name": "Ghost Account",
        "opening_balance": "0.00"
    }
    response = client.put("/accounts/9999", json=update_data)
    assert response.status_code == 404


def test_delete_account(client):
    # Create account to delete
    create_data = {
        "account_number": "DD1111",
        "account_name": "To Delete",
        "opening_balance": "50.00"
    }
    create_resp = client.post("/accounts", json=create_data)
    account_id = create_resp.json()["id"]

    # Delete it
    response = client.delete(f"/accounts/{account_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Account deleted successfully."

    # Verify deleted
    check = client.get(f"/accounts/{account_id}")
    assert check.status_code == 404


def test_delete_account_not_found(client):
    response = client.delete("/accounts/9999")
    assert response.status_code == 404
    
    