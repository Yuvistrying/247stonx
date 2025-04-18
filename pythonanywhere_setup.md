# Setting up 247 Stonx on PythonAnywhere

This guide provides detailed steps for setting up your 247 Stonx application on PythonAnywhere.

## 1. Sign up for PythonAnywhere

1. Visit [PythonAnywhere](https://www.pythonanywhere.com/) and sign up for an account
2. Free tier works for testing, but consider a paid plan for better performance

## 2. Create a Web App

1. From your PythonAnywhere dashboard, click on the **Web** tab
2. Click on **Add a new web app**
3. Choose your domain (yourusername.pythonanywhere.com)
4. Select **Manual configuration** (not "Flask")
5. Choose **Python 3.9** (or the version you developed with)

## 3. Set Up Virtual Environment

1. Go to the **Consoles** tab and start a new **Bash console**
2. Create a virtual environment:
   ```bash
   mkvirtualenv --python=python3.9 stonx-env
   ```
3. You should see the prompt change to show the environment is active

## 4. Upload or Clone Your Code

### Option A: If your code is on GitHub:
```bash
git clone https://github.com/yourusername/247stonx.git
cd 247stonx
```

### Option B: If uploading manually:
1. In your Bash console:
   ```bash
   mkdir 247stonx
   cd 247stonx
   ```
2. Use the **Files** tab to upload your files to this directory

## 5. Install Dependencies

1. In your Bash console (with virtualenv active):
   ```bash
   cd ~/247stonx
   pip install -r requirements.txt
   ```

## 6. Configure Your Web App

1. Go back to the **Web** tab
2. Under **Virtualenv**, enter: `/home/yourusername/.virtualenvs/stonx-env`
3. Under **Code**, set:
   - Source code: `/home/yourusername/247stonx`
   - Working directory: `/home/yourusername/247stonx`

## 7. Configure WSGI File

1. Under the **Code** section, click the link to edit the WSGI configuration file
2. Delete all the existing content and replace with:
   ```python
   import sys
   import os
   
   # Add your project directory to the sys.path
   path = '/home/yourusername/247stonx'
   if path not in sys.path:
       sys.path.append(path)
   
   # Set environment variables
   os.environ['PRODUCTION'] = 'true'
   os.environ['SECRET_KEY'] = 'your-secure-random-string-here'
   
   # Import Flask app
   from app import app as application
   ```
   
   **IMPORTANT**: Replace `yourusername` with your actual PythonAnywhere username and set a strong random string for `SECRET_KEY`.

## 8. Set Up Database

1. In your Bash console (make sure the virtualenv is active):
   ```bash
   cd ~/247stonx
   python -c "from app import db, app; with app.app_context(): db.create_all()"
   ```

## 9. Configure Static Files

1. In the **Web** tab, under **Static files**:
2. Add the following mapping:
   - URL: `/static/`
   - Directory: `/home/yourusername/247stonx/static`

## 10. Configure Security Settings

1. In the **Web** tab, under **Security**:
2. Consider enabling **Force HTTPS** (recommended for production)

## 11. Start Your App

1. Click the green **Reload** button at the top of the Web tab
2. Visit your site at `https://yourusername.pythonanywhere.com`

## 12. Set Up Database Backup (Optional)

1. Go to the **Tasks** tab
2. Set up a scheduled task to run daily:
   ```bash
   cd /home/yourusername/247stonx && /home/yourusername/.virtualenvs/stonx-env/bin/python backup_database.py
   ```

## Troubleshooting

If your app doesn't work:

1. Check the **Error logs** in the Web tab
2. Verify all dependencies are installed in your virtualenv
3. Make sure your database is initialized
4. Check for path issues in the WSGI file
5. Ensure there are no hardcoded localhost URLs in your code

## Maintenance Tips

1. **Updating your app**:
   ```bash
   # In the Bash console
   cd ~/247stonx
   git pull  # If using git
   workon stonx-env
   pip install -r requirements.txt  # If dependencies changed
   ```
   Then click the "Reload" button in the Web tab

2. **Checking logs**:
   - Access logs: Web tab → Log files → Access log
   - Error logs: Web tab → Log files → Error log
   - Server logs: Web tab → Log files → Server log

3. **Database backups**:
   - Run the backup script manually:
     ```bash
     cd ~/247stonx
     workon stonx-env
     python backup_database.py
     ```
   - Or set up scheduled backups in the Tasks tab as described above

## Resource Management

On the free tier:
- Your web app goes to sleep after a period of inactivity
- You have CPU time and bandwidth quotas
- Consider upgrading to a paid plan for better performance and reliability 