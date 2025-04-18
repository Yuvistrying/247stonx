# Deploying 247 Stonx to PythonAnywhere

This guide provides step-by-step instructions for deploying your 247 Stonx application on PythonAnywhere.

## 1. Create a PythonAnywhere Account

1. Go to [PythonAnywhere](https://www.pythonanywhere.com) and sign up for an account (free tier for testing, paid for production).
2. After signing up, log in to your dashboard.

## 2. Upload Your Code

There are multiple ways to get your code to PythonAnywhere:

### Option A: Using Git (Recommended)

1. If your code is in a Git repository:
   ```bash
   # On PythonAnywhere Bash console
   git clone https://github.com/yourusername/247stonx.git
   ```

### Option B: Manual Upload

1. Go to the Files tab on PythonAnywhere
2. Create a new directory called `247stonx`
3. Upload all your project files to this directory

## 3. Set Up a Virtual Environment

1. Open a Bash console on PythonAnywhere
2. Create and activate a virtual environment:
   ```bash
   mkvirtualenv --python=python3.9 stonx-env
   cd ~/247stonx
   pip install -r requirements.txt
   ```

## 4. Create a Web App

1. Go to the Web tab on PythonAnywhere
2. Click "Add a new web app"
3. Choose your domain name (it will be yourusername.pythonanywhere.com)
4. Select "Manual configuration"
5. Choose Python 3.9 (match the version used in your virtualenv)

## 5. Configure the Web App

1. In the "Virtualenv" section, enter: `stonx-env`
2. In the "Code" section:
   - Set the "Source code" path to `/home/yourusername/247stonx`
   - Set the "Working directory" to `/home/yourusername/247stonx`

3. In the "WSGI configuration file" section, click on the link to edit the WSGI file
4. Replace the content with the proper WSGI configuration:
   ```python
   import sys
   import os
   
   # Add your project directory to the sys.path
   path = '/home/yourusername/247stonx'
   if path not in sys.path:
       sys.path.append(path)
   
   # Import your Flask app
   from app import app as application
   
   # Set environment variables for production
   os.environ['SECRET_KEY'] = 'your-secure-production-key'
   ```
   
   > **IMPORTANT**: Replace 'yourusername' with your actual PythonAnywhere username and set a strong SECRET_KEY.

## 6. Set Up the Database

1. The app uses SQLite by default. In the PythonAnywhere bash console:
   ```bash
   cd ~/247stonx
   workon stonx-env
   python
   ```

2. In the Python console:
   ```python
   from app import db, app
   with app.app_context():
       db.create_all()
   exit()
   ```

## 7. Configure Static Files

1. Go back to the Web tab
2. In the "Static Files" section, add:
   - URL: /static/
   - Directory: /home/yourusername/247stonx/static/

## 8. Reload the Web App

1. Click the green "Reload" button at the top of the Web tab
2. Visit yourusername.pythonanywhere.com to see your deployed app

## Troubleshooting

If you encounter issues:

1. Check the error logs in the Web tab
2. Make sure all dependencies are installed in your virtualenv
3. Verify that the database is properly set up
4. Ensure the wsgi.py file has the correct path
5. Check for any hardcoded localhost URLs in your code

Remember that on the free tier of PythonAnywhere:
- Your web app will go to sleep after a period of inactivity
- Access to external sites is limited (but Robinhood scraping should work)
- You have CPU and bandwidth quotas

For production use, consider upgrading to a paid plan. 