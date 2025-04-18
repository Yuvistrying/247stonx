"""
WSGI configuration file for PythonAnywhere deployment
"""

import sys
import os

# Add your project directory to the sys.path
path = '/home/yuvalalalalal/247stonx'
if path not in sys.path:
    sys.path.append(path)

# Set production environment variables
os.environ['PRODUCTION'] = 'true'
os.environ['SECRET_KEY'] = 'your-production-secret-key'  # Change this to a secure random value
# os.environ['DATABASE_URL'] = 'sqlite:///stocks.db'  # Default SQLite path

# Import your Flask app
from app import app as application 
"""
Replace {username} with your actual PythonAnywhere username when deploying.
Make sure to set a strong SECRET_KEY in the PythonAnywhere dashboard or directly in this file.
""" 