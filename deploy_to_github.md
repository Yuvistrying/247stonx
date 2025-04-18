# GitHub and PythonAnywhere Deployment Guide

This guide will walk you through setting up your GitHub repository and configuring automatic deployments to PythonAnywhere.

## Step 1: Push Your Code to GitHub

First, let's push your code to GitHub. You've already initialized a git repository locally:

```bash
# Make sure you're in your project directory
cd /Users/yuval/247stonx

# Create a GitHub repository (do this in your browser)
# Visit https://github.com/new
# Name the repository: 247stonx

# After creating the repository, set up the remote and push
git branch -M main
git remote add origin https://github.com/yourusername/247stonx.git
git push -u origin main
```

Replace `yourusername` with your actual GitHub username.

## Step 2: Set Up PythonAnywhere Account

1. Sign up for a PythonAnywhere account at https://www.pythonanywhere.com/
2. Choose a plan that fits your needs (free tier for testing, paid for production)

## Step 3: Generate an API Token in PythonAnywhere

1. Log into your PythonAnywhere account
2. Go to Account settings (click on your username in the top right)
3. Navigate to the "API Token" tab
4. Click "Create new API token"
5. Save this token securely - you'll need it to automate deployments

## Step 4: Manual Initial Deployment to PythonAnywhere

For the first setup, we'll deploy manually:

1. In PythonAnywhere, open a Bash console (from the "Consoles" tab)
2. Clone your repository:
   ```bash
   git clone https://github.com/yourusername/247stonx.git
   ```
3. Set up a virtual environment:
   ```bash
   cd 247stonx
   mkvirtualenv --python=python3.9 stonx-env
   pip install -r requirements.txt
   ```
4. Create a new web app from the "Web" tab:
   - Select "Manual configuration"
   - Choose Python 3.9
   - Set Source code directory: `/home/yourusername/247stonx`
   - Set Working directory: `/home/yourusername/247stonx`
   - Set Virtual environment: `/home/yourusername/.virtualenvs/stonx-env`
   - Configure the WSGI file (click the link in the Web tab):
     ```python
     import sys
     import os
     
     # Add your project directory to the sys.path
     path = '/home/yourusername/247stonx'
     if path not in sys.path:
         sys.path.append(path)
     
     # Set production environment variables
     os.environ['PRODUCTION'] = 'true'
     os.environ['SECRET_KEY'] = 'your-secure-random-string'
     
     # Import Flask app
     from app import app as application
     ```
5. Add static files mapping:
   - URL: `/static/`
   - Directory: `/home/yourusername/247stonx/static`
6. Initialize the database:
   ```bash
   cd ~/247stonx
   python -c "from app import db, app; with app.app_context(): db.create_all()"
   ```
7. Click "Reload" to start your web app

## Step 5: Create a Deployment Script on PythonAnywhere

Create a file called `deploy.py` in your PythonAnywhere home directory:

```bash
cd ~
nano deploy.py
```

Add the following content:

```python
#!/usr/bin/env python3
"""
Deployment script for 247 Stonx
This script pulls the latest changes from GitHub and reloads the web app
"""

import os
import sys
import subprocess
import datetime

# Configuration
PROJECT_DIR = '/home/yourusername/247stonx'
VENV_PATH = '/home/yourusername/.virtualenvs/stonx-env'
WEBAPP_NAME = 'yourusername.pythonanywhere.com'  # Change to your webapp name

# Log setup
LOG_FILE = os.path.join(PROJECT_DIR, 'deploy_log.txt')

def log(message):
    """Log a message to file and stdout"""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    with open(LOG_FILE, 'a') as f:
        f.write(log_message + '\n')

def run_command(command, cwd=None):
    """Run a shell command and log output"""
    log(f"Running: {command}")
    try:
        result = subprocess.run(command, shell=True, check=True, cwd=cwd,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True)
        log(f"Success: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Error: {e}")
        log(f"Output: {e.stdout}")
        log(f"Error output: {e.stderr}")
        return False

def main():
    """Main deployment function"""
    log("Starting deployment")
    
    # Activate virtualenv
    activate_cmd = f"source {VENV_PATH}/bin/activate"
    
    # Pull latest changes
    if not run_command(f"{activate_cmd} && git pull", cwd=PROJECT_DIR):
        log("Failed to pull changes")
        return
    
    # Install or update dependencies
    if not run_command(f"{activate_cmd} && pip install -r requirements.txt", cwd=PROJECT_DIR):
        log("Failed to install dependencies")
        return
    
    # Run database migrations if needed
    if not run_command(f"{activate_cmd} && python -c 'from app import db, app; with app.app_context(): db.create_all()'", cwd=PROJECT_DIR):
        log("Failed to run database migrations")
        return
    
    # Touch the WSGI file to reload the app
    if not run_command(f"touch /var/www/{WEBAPP_NAME}_wsgi.py"):
        log("Failed to reload web app")
        return
    
    log("Deployment completed successfully")

if __name__ == "__main__":
    main()
```

Make it executable:

```bash
chmod +x deploy.py
```

## Step 6: Set up a GitHub Action for Automated Deployment

Now, we'll create a GitHub Actions workflow file in your repository. Create this file in your local repository:

```bash
mkdir -p .github/workflows
touch .github/workflows/deploy.yml
```

Edit the `deploy.yml` file:

```yaml
name: Deploy to PythonAnywhere

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
    
    - name: Run tests
      run: |
        pytest
    
    - name: Deploy to PythonAnywhere
      env:
        PYTHON_ANYWHERE_API_TOKEN: ${{ secrets.PYTHON_ANYWHERE_API_TOKEN }}
        PA_USERNAME: ${{ secrets.PA_USERNAME }}
      run: |
        # Create a console
        response=$(curl -s -X POST \
          "https://www.pythonanywhere.com/api/v0/user/$PA_USERNAME/consoles/" \
          -H "Authorization: Token $PYTHON_ANYWHERE_API_TOKEN" \
          -d "executable=python3.9" \
          -d "arguments=/home/$PA_USERNAME/deploy.py" \
          -d "working_directory=/home/$PA_USERNAME/")
        
        console_id=$(echo $response | python -c "import sys, json; print(json.load(sys.stdin)['id'])")
        
        echo "Console created with ID: $console_id"
        
        # The deploy script will run and close automatically
        echo "Deployment started on PythonAnywhere"
```

## Step 7: Add Secrets to GitHub Repository

1. Go to your GitHub repository
2. Click "Settings" > "Secrets and variables" > "Actions"
3. Add these secrets:
   - `PYTHON_ANYWHERE_API_TOKEN`: Your PythonAnywhere API token
   - `PA_USERNAME`: Your PythonAnywhere username

## Step 8: Commit and Push Your Workflow File

```bash
git add .github/workflows/deploy.yml
git commit -m "Add automated deployment workflow"
git push origin main
```

## Step 9: Test the Deployment Pipeline

1. Make a change to your repository
2. Commit and push the change
3. Visit GitHub Actions tab to see the workflow running
4. Once completed, visit your PythonAnywhere app to see the changes

## Troubleshooting

If you encounter issues:

1. Check the GitHub Actions logs for errors
2. Look at the `deploy_log.txt` file in your PythonAnywhere project
3. Check the PythonAnywhere error logs in the Web tab

## Additional Tips

1. For more security, consider using SSH keys for Git instead of HTTPS
2. Set up database backups using the backup script provided in this repository
3. For more advanced CI/CD, consider adding linting, more extensive testing, and staging environments

Remember to replace `yourusername` with your actual GitHub and PythonAnywhere usernames throughout this guide. 