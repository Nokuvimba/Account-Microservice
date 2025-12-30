import pytest
from unittest.mock import patch, Mock
import httpx
from pybreaker import CircuitBreakerError
from fastapi import HTTPException

from app.circuit import login_cb


def test_circuit_breaker_configuration():
    """Test that circuit breaker is configured correctly"""
    assert login_cb.fail_max == 3
    assert login_cb.reset_timeout == 30


def test_circuit_breaker_decorator_success(client):
    """Test that circuit breaker allows successful calls"""
    with patch('httpx.Client.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "full_name": "Test User"}
        mock_get.return_value = mock_response
        
        r = client.post("/accounts/from-user/1")
        assert r.status_code == 201


def test_circuit_breaker_opens_after_failures(client):
    """Test that circuit breaker opens after consecutive failures"""
    with patch('httpx.Client.get') as mock_get:
        # Simulate failures
        mock_get.side_effect = httpx.RequestError("Connection failed")
        
        # First 3 failures should still attempt the call
        for i in range(3):
            r = client.post("/accounts/from-user/1")
            assert r.status_code == 503
        
        # 4th call should be blocked by circuit breaker
        with patch('app.main.fetch_user_from_login') as mock_fetch:
            mock_fetch.side_effect = CircuitBreakerError()
            r = client.post("/accounts/from-user/1")
            assert r.status_code == 503
            assert "circuit open" in r.json()["detail"]


def test_circuit_breaker_handles_404_correctly(client):
    """Test that 404 errors are handled properly without opening circuit"""
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.side_effect = HTTPException(status_code=404, detail="User not found")
        r = client.post("/accounts/from-user/999")
        assert r.status_code == 404
        assert "User not found" in r.json()["detail"]


def test_circuit_breaker_proxy_endpoint(client):
    """Test circuit breaker behavior in proxy endpoint"""
    with patch('app.main.fetch_user_from_login') as mock_fetch:
        mock_fetch.side_effect = CircuitBreakerError()
        r = client.get("/api/proxy-user/1")
        assert r.status_code == 503
        assert "circuit open" in r.json()["detail"]


def test_circuit_breaker_account_details_endpoint(client):
    """Test circuit breaker behavior in account details endpoint"""
    # First create an account
    with patch('app.main.safe_fetch_user_from_login') as mock_fetch:
        mock_fetch.return_value = {"id": 1, "full_name": "Test User"}
        client.post("/accounts/from-user/1")
    
    # Then test circuit breaker on details endpoint
    with patch('app.main.fetch_user_from_login') as mock_fetch:
        mock_fetch.side_effect = CircuitBreakerError()
        r = client.get("/accounts/by-user/1/details")
        assert r.status_code == 503
        assert "circuit open" in r.json()["detail"]