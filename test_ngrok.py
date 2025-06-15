#!/usr/bin/env python3
"""
Test script to verify ngrok setup for Leyla Cuisine Bot
"""

import requests
import sys

def test_ngrok_connection():
    """Test if the ngrok domain is accessible"""
    ngrok_url = "https://conversation.ngrok.app"
    
    print(f"Testing connection to {ngrok_url}...")
    
    try:
        response = requests.get(ngrok_url, timeout=10)
        if response.status_code == 200:
            print("✅ SUCCESS: ngrok domain is accessible")
            print(f"Response: {response.status_code}")
            if "Leyla Cuisine Bot" in response.text:
                print("✅ SUCCESS: Bot server is responding correctly")
            else:
                print("⚠️  WARNING: Server responded but content doesn't match expected")
            return True
        else:
            print(f"❌ ERROR: Server responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to {ngrok_url}")
        print(f"Error details: {e}")
        return False

def test_oauth_endpoint():
    """Test if the OAuth callback endpoint is accessible"""
    oauth_url = "https://conversation.ngrok.app/oauth2callback"
    
    print(f"\nTesting OAuth endpoint {oauth_url}...")
    
    try:
        # Test with no parameters (should return error page)
        response = requests.get(oauth_url, timeout=10)
        if response.status_code == 200:
            print("✅ SUCCESS: OAuth endpoint is accessible")
            if "Missing authorization code" in response.text:
                print("✅ SUCCESS: OAuth endpoint is handling errors correctly")
            else:
                print("⚠️  WARNING: OAuth endpoint responded but error handling may not be working")
            return True
        else:
            print(f"❌ ERROR: OAuth endpoint responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Could not connect to OAuth endpoint")
        print(f"Error details: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Testing ngrok setup for Leyla Cuisine Bot\n")
    
    success = True
    success &= test_ngrok_connection()
    success &= test_oauth_endpoint()
    
    print("\n" + "="*50)
    if success:
        print("🎉 All tests passed! Your ngrok setup is working correctly.")
        print("\nNext steps:")
        print("1. Update your Google Cloud Console OAuth settings")
        print("2. Update your .env file with the ngrok domain")
        print("3. Test the full OAuth flow with your bot")
    else:
        print("❌ Some tests failed. Please check your setup:")
        print("1. Make sure your bot is running")
        print("2. Make sure ngrok is running and pointing to port 8080")
        print("3. Check that the ngrok domain matches conversation.ngrok.app")
    
    sys.exit(0 if success else 1) 