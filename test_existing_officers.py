#!/usr/bin/env python3
"""
Test script for Existing Officers system.
Run with: python test_existing_officers.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    print("✅ Health check passed")

def test_existing_officers_endpoints():
    """Test existing officers endpoints"""
    
    # Test verify endpoint
    verify_data = {
        "officer_id": "OFF123456",
        "email": "test.officer@example.com"
    }
    
    response = client.post("/api/existing-officers/verify", json=verify_data)
    print(f"Verify response: {response.status_code} - {response.json()}")
    
    # Test register endpoint
    register_data = {
        "officer_id": "OFF123456",
        "email": "test.officer@example.com",
        "phone": "+2348012345678",
        "password": "securepassword123",
        "full_name": "Test Officer",
        "nin_number": "12345678901",
        "gender": "male",
        "date_of_birth": "1990-01-01",
        "place_of_birth": "Lagos",
        "nationality": "Nigerian",
        "marital_status": "single",
        "residential_address": "123 Test Street, Lagos",
        "state_of_residence": "Lagos",
        "local_government_residence": "Ikeja",
        "country_of_residence": "Nigeria",
        "state_of_origin": "Lagos",
        "local_government_origin": "Ikeja",
        "rank": "Inspector",
        "position": "Field Officer",
        "years_of_service": "5",
        "service_number": "SVC123456",
        "religion": "Christian",
        "additional_skills": "First Aid, Driving",
        "bank_name": "First Bank",
        "account_number": "1234567890"
    }
    
    response = client.post("/api/existing-officers/register", json=register_data)
    print(f"Register response: {response.status_code} - {response.json()}")

if __name__ == "__main__":
    print("🚀 Testing Existing Officers System...")
    print("-" * 50)
    
    try:
        test_health()
        print("-" * 50)
        test_existing_officers_endpoints()
        print("-" * 50)
        print("✅ All tests completed!")
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        sys.exit(1)