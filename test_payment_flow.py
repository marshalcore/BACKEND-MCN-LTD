#!/usr/bin/env python3
"""
Payment Flow Test Script
Run this on your local machine with proper .env settings
"""
import requests
import json
import time

BASE_URL = "https://api.marshalcoreofnigeria.ng"  # Update if different

def test_payment_flow():
    print("=" * 60)
    print("MCN PAYMENT FLOW TEST")
    print("=" * 60)
    
    # Test 1: Health Check
    print("\n📡 Test 1: Health Check")
    try:
        resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.json()}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return
    
    # Test 2: Get Recent Payments
    print("\n📋 Test 2: Recent Payments")
    try:
        resp = requests.get(f"{BASE_URL}/api/payments/recent", timeout=10)
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            payments = resp.json()
            print(f"   Found {len(payments.get('payments', []))} recent payments")
            for p in payments.get('payments', [])[:5]:
                print(f"   - {p.get('payment_reference', 'N/A')}")
                print(f"     Email: {p.get('user_email', 'N/A')}")
                print(f"     Amount: ₦{p.get('amount', 0):,}")
                print(f"     Status: {p.get('status', 'N/A')}")
                print(f"     Paystack Ref: {p.get('paystack_reference', 'N/A')}")
                print()
        else:
            print(f"   Response: {resp.text[:500]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 3: Initiate Test Payment
    print("\n💳 Test 3: Initiate Test Payment (Regular)")
    test_email = f"test_{int(time.time())}@test.com"
    payload = {
        "email": test_email,
        "payment_type": "regular",
        "user_type": "pre_applicant"
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/api/payments/initiate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ Payment Initiated!")
            print(f"   Reference: {data.get('payment_reference')}")
            print(f"   Paystack Reference: {data.get('paystack_reference')}")
            print(f"   Authorization URL: {data.get('authorization_url', 'N/A')[:60]}...")
            
            # Test 4: Verify Payment Lookup
            print("\n🔍 Test 4: Verify Payment Lookup (both references)")
            ref = data.get('payment_reference')
            ps_ref = data.get('paystack_reference')
            
            # Try our custom reference
            resp1 = requests.get(f"{BASE_URL}/api/payments/verify/{ref}", timeout=10)
            print(f"   Lookup by custom ref: {resp1.status_code}")
            
            # Note: Can't test paystack_reference lookup without actual payment
            print(f"   Paystack ref stored: {ps_ref}")
        else:
            print(f"   Response: {resp.text[:500]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Test 5: VIP Payment
    print("\n💎 Test 5: Initiate Test Payment (VIP)")
    test_email_vip = f"vip_test_{int(time.time())}@test.com"
    payload_vip = {
        "email": test_email_vip,
        "payment_type": "vip",
        "user_type": "pre_applicant"
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/api/payments/initiate",
            json=payload_vip,
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ VIP Payment Initiated!")
            print(f"   Amount: ₦{data.get('amount', 0):,}")
            print(f"   Reference: {data.get('payment_reference')}")
        else:
            print(f"   Response: {resp.text[:500]}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\n💡 To test webhook, complete a payment on the frontend")
    print("   and check that paystack_reference is captured!")

if __name__ == "__main__":
    test_payment_flow()
