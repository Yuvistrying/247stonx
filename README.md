# 247Stonx - 24/7 Stock Price Tracker

A web application that tracks stock prices from Robinhood, allowing users to create custom dashboards with their favorite tickers.

## Features

- Real-time stock price tracking using data from Robinhood
- User authentication system for personalized dashboards
- Add and remove stock tickers with a simple interface
- Automatic price refreshing every 30 seconds
- Color-coded price changes and market status indicators
- Mobile-responsive design
- SQLite database for storing user preferences

## Requirements

- Python 3.8+
- Flask and related extensions
- SQLite database

## Installation

1. Clone the repository:
```
git clone https://github.com/yourusername/247stonx.git
cd 247stonx
```

2. Create a virtual environment:
```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```
pip install -r requirements.txt
```

4. Initialize the database:
```
python app.py
```

## Usage

1. Start the application:
```
python app.py
```

2. Open your browser and navigate to http://127.0.0.1:5000/

3. Register a new account and start adding tickers to track

## Deployment on PythonAnywhere

This application is designed to be easily deployed on PythonAnywhere:

1. Sign up for a free PythonAnywhere account

2. Upload your files to PythonAnywhere:
   - Create a new web app with Flask
   - Upload your files to the designated directory
   - Install the required packages using pip

3. Configure WSGI file:
```python
import sys
path = '/home/yourusername/247stonx'
if path not in sys.path:
    sys.path.append(path)

from app import app as application
```

4. Start the web app from the PythonAnywhere dashboard

## Configuration Options

You can set the following environment variables:
- `SECRET_KEY`: Used for session security (set a strong random key in production)
- `DATABASE_URL`: SQLite database URI (default is 'sqlite:///stocks.db')

## Limitations

- The free tier of PythonAnywhere may have limited CPU resources
- Scheduled tasks on free tier are limited to daily runs
- Consider upgrading to a paid plan for better performance if needed

## Security Considerations

- The application uses Werkzeug's password hashing for securing user passwords
- It's recommended to use HTTPS in production
- Consider adding rate limiting to the API endpoints in production

## License

MIT License