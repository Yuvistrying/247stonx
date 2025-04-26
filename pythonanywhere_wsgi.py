import sys
import os

# Add the application directory to the Python path
path = '/home/yuvalalalalal/247stonx'
if path not in sys.path:
    sys.path.append(path)

# Set production environment variables
os.environ['PRODUCTION'] = 'true'
os.environ['SECRET_KEY'] = 'af8d1cbc41ba4e91b756c8e9e4c2e3a9f7g6h5j4k3l2m1'  # Random secure key

# Import the Flask application
from app import app as application 