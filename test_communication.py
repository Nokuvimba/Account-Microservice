#!/usr/bin/env python3
"""
Test script to verify communication between Login and Account microservices
"""
import requests
import json
import time

LOGIN_BASE = "http://localhost:8001"
ACCOUNT_BASE = "http://localhost:8002"

def test_services():
    print("🔍 Testing microservice communication...")
    
    # Test 1: Create a user in Login service
    print("\n1️⃣ Creating user in Login service...")
    user_data = {
        "full_name": "John Doe",
        "email": "john.doe@example.com", 
        "phone_number": "1234567890",
        "password": "password123"
    }
    
    try:
        response = requests.post(f"{LOGIN_BASE}/api/users", json=user_data)
        if response.status_code == 201:
            user = response.json()
            print(f"✅ User created: ID {user['id']}, Name: {user['full_name']}")
            user_id = user['id']
        else:
            print(f"❌ Failed to create user: {response.status_code} - {response.text}")
            return
    except requests.RequestException as e:
        print(f"❌ Login service unavailable: {e}")
        return

    # Test 2: Create account for user in Account service
    print(f"\n2️⃣ Creating account for user {user_id} in Account service...")
    try:
        response = requests.post(f"{ACCOUNT_BASE}/accounts/from-user/{user_id}")
        if response.status_code == 201:
            account = response.json()
            print(f"✅ Account created: {account['account_number']}, Balance: {account['balance']}")
            account_number = account['account_number']
        else:
            print(f"❌ Failed to create account: {response.status_code} - {response.text}")
            return
    except requests.RequestException as e:
        print(f"❌ Account service unavailable: {e}")
        return

    # Test 3: Get account details (tests communication)
    print(f"\n3️⃣ Getting account details (tests service communication)...")
    try:
        response = requests.get(f"{ACCOUNT_BASE}/accounts/by-user/{user_id}/details")
        if response.status_code == 200:
            details = response.json()
            print(f"✅ Account details retrieved:")
            print(f"   User: {details['user']['full_name']} ({details['user']['email']})")
            print(f"   Account: {details['account']['account_number']} - {details['account']['balance']} {details['account']['currency']}")
        else:
            print(f"❌ Failed to get details: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        print(f"❌ Failed to get details: {e}")

    # Test 4: Test proxy endpoint
    print(f"\n4️⃣ Testing proxy endpoint...")
    try:
        response = requests.get(f"{ACCOUNT_BASE}/api/proxy-user/{user_id}")
        if response.status_code == 200:
            proxy_data = response.json()
            print(f"✅ Proxy test successful: {proxy_data['login_user']['full_name']}")
        else:
            print(f"❌ Proxy test failed: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        print(f"❌ Proxy test failed: {e}")

    # Test 5: Deposit money
    print(f"\n5️⃣ Making a deposit...")
    try:
        deposit_data = {"amount": 100.50, "description": "Initial deposit"}
        response = requests.post(f"{ACCOUNT_BASE}/accounts/by-number/{account_number}/deposit", json=deposit_data)
        if response.status_code == 201:
            transaction = response.json()
            print(f"✅ Deposit successful: {transaction['amount']} {transaction['tx_type']}")
        else:
            print(f"❌ Deposit failed: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        print(f"❌ Deposit failed: {e}")

    print("\n🎉 Communication test completed!")

if __name__ == "__main__":
    test_services()