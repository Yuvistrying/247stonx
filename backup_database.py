#!/usr/bin/env python3
"""
Database backup script for 247 Stonx application.
This script creates a timestamped backup of the SQLite database.

Usage:
  python backup_database.py

To schedule on PythonAnywhere:
  - Go to the Tasks tab
  - Add a scheduled task that runs this script daily
"""

import os
import shutil
import sqlite3
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('database_backup.log'), logging.StreamHandler()]
)

def backup_database():
    """Create a backup of the SQLite database."""
    try:
        # Define source and destination paths
        src_db = 'instance/stocks.db'  # Adjust if your database path is different
        backup_dir = 'database_backups'
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            logging.info(f"Created backup directory: {backup_dir}")
        
        # Generate timestamp for backup filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dst_db = f"{backup_dir}/stocks_{timestamp}.db"
        
        # Check if source database exists
        if not os.path.exists(src_db):
            logging.error(f"Source database not found: {src_db}")
            return False
        
        # Create backup copy
        # Connect to source database to ensure it's not in the middle of a transaction
        conn = sqlite3.connect(src_db)
        conn.execute('PRAGMA wal_checkpoint;')  # Ensure WAL file is flushed
        conn.close()
        
        # Make the actual backup
        shutil.copy2(src_db, dst_db)
        logging.info(f"Database backup created: {dst_db}")
        
        # Cleanup old backups (keep only the 7 most recent)
        backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('stocks_')], 
                           key=lambda x: os.path.getctime(os.path.join(backup_dir, x)))
        
        if len(backups) > 7:
            for old_backup in backups[:-7]:
                os.remove(os.path.join(backup_dir, old_backup))
                logging.info(f"Removed old backup: {old_backup}")
                
        return True
        
    except Exception as e:
        logging.error(f"Error backing up database: {str(e)}")
        return False

if __name__ == "__main__":
    logging.info("Starting database backup process")
    result = backup_database()
    logging.info(f"Database backup {'completed successfully' if result else 'failed'}") 