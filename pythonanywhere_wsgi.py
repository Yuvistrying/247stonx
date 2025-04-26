import sys
import os

# Add the application directory to the Python path
path = '/home/YOURUSERNAME/247stonx'
if path not in sys.path:
    sys.path.append(path)

# Set production environment variables
os.environ['PRODUCTION'] = 'true'
os.environ['SECRET_KEY'] = 'your-secure-production-key-change-this'  # IMPORTANT: Change this to a secure random key

# Import the Flask application
from app import app as application 