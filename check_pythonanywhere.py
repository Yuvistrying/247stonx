#!/usr/bin/env python3
"""
PythonAnywhere Configuration Checker

This script helps diagnose issues with the PythonAnywhere deployment
by checking the API connection and server status.

Usage:
    python check_pythonanywhere.py --username YOUR_USERNAME --token YOUR_API_TOKEN

Requirements:
    requests
"""

import argparse
import requests
import json
import sys

def check_api_token(username, token):
    """Check if the API token is valid by making a simple API call."""
    headers = {"Authorization": f"Token {token}"}
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print(f"✅ API token is valid for user: {username}")
            return True
        else:
            print(f"❌ API token validation failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking API token: {e}")
        return False

def check_webapp_exists(username, token):
    """Check if the web app exists."""
    headers = {"Authorization": f"Token {token}"}
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/webapps/"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            webapps = response.json()
            if webapps:
                for webapp in webapps:
                    print(f"✅ Found web app: {webapp['domain_name']}")
                return True
            else:
                print("❌ No web apps found for this user")
                return False
        else:
            print(f"❌ Failed to get web apps with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking web apps: {e}")
        return False

def check_files_exist(username, token):
    """Check if the project files exist on PythonAnywhere."""
    headers = {"Authorization": f"Token {token}"}
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path/home/{username}/247stonx/"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            files = response.json()
            if files:
                print(f"✅ Project directory exists with {len(files)} files/directories")
                
                # Check for crucial files
                important_files = ["app.py", "requirements.txt", "threaded_scraper.py"]
                for file in important_files:
                    if any(f["name"] == file for f in files):
                        print(f"  ✅ Found critical file: {file}")
                    else:
                        print(f"  ❌ Missing critical file: {file}")
                
                return True
            else:
                print("❌ Project directory exists but is empty")
                return False
        elif response.status_code == 404:
            print("❌ Project directory does not exist at /home/{username}/247stonx/")
            return False
        else:
            print(f"❌ Failed to check files with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error checking files: {e}")
        return False

def update_wsgi_file(username, token):
    """Attempt to update the WSGI file for the web app."""
    print("\nWould you like to update the WSGI file? (y/n)")
    choice = input().lower()
    
    if choice != 'y':
        print("Skipping WSGI file update.")
        return
    
    wsgi_content = f"""import sys
import os

# Add the application directory to the Python path
path = '/home/{username}/247stonx'
if path not in sys.path:
    sys.path.append(path)

# Set production environment variables
os.environ['PRODUCTION'] = 'true'
os.environ['SECRET_KEY'] = 'your-secure-production-key-change-this'  # Change this!

# Import the Flask application
from app import app as application
"""
    
    headers = {"Authorization": f"Token {token}"}
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path/var/www/{username}_pythonanywhere_com_wsgi.py/"
    
    try:
        # First check if the file exists
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("✅ WSGI file exists")
            
            # Ask before overwriting
            print("\nWARNING: This will overwrite your existing WSGI file.")
            print("Are you sure you want to continue? (y/n)")
            overwrite = input().lower()
            
            if overwrite != 'y':
                print("Skipping WSGI file update.")
                return
            
            # Update the file
            response = requests.post(
                url,
                headers=headers,
                data={"content": wsgi_content}
            )
            
            if response.status_code == 200:
                print("✅ WSGI file updated successfully")
                
                # Reload the web app
                reload_url = f"https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{username}.pythonanywhere.com/reload/"
                reload_response = requests.post(reload_url, headers=headers)
                
                if reload_response.status_code == 200:
                    print("✅ Web app reloaded successfully")
                else:
                    print(f"❌ Failed to reload web app with status code: {reload_response.status_code}")
            else:
                print(f"❌ Failed to update WSGI file with status code: {response.status_code}")
                print(f"Response: {response.text}")
        else:
            print(f"❌ WSGI file does not exist or cannot be accessed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error updating WSGI file: {e}")

def main():
    parser = argparse.ArgumentParser(description="Check PythonAnywhere configuration")
    parser.add_argument("--username", "-u", required=True, help="PythonAnywhere username")
    parser.add_argument("--token", "-t", required=True, help="PythonAnywhere API token")
    
    args = parser.parse_args()
    
    print("PythonAnywhere Configuration Checker")
    print("====================================")
    
    # Run checks
    api_valid = check_api_token(args.username, args.token)
    
    if not api_valid:
        print("\n❌ API token is invalid. Please check your token and try again.")
        sys.exit(1)
    
    webapp_exists = check_webapp_exists(args.username, args.token)
    files_exist = check_files_exist(args.username, args.token)
    
    # Offer to update the WSGI file if needed
    if api_valid and webapp_exists:
        update_wsgi_file(args.username, args.token)
    
    print("\nChecks completed.")

if __name__ == "__main__":
    main() 