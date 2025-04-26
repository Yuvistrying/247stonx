import os
import logging
import time
import datetime
import hashlib
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from threading import Lock
import threading
import argparse

# Import scrapers
from scraper import scrape_stock_data
from threaded_scraper import ThreadedScraper

# Configure app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_change_in_production')
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=24)  # 24 hour session timeout
app.config['SESSION_REFRESH_EACH_REQUEST'] = True

# Configure database - optimized connection settings
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///247stonx.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,  # Verify connection validity before use
    'pool_recycle': 280,    # Recycle connections after 280 seconds
    'pool_size': 20,        # Increased pool size (from 10)
    'max_overflow': 20,     # Increased max overflow (from 15)
    'pool_timeout': 60      # Increased timeout (from default 30)
}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('247stonx')

# Initialize database
db = SQLAlchemy(app)

# Initialize the threaded scraper with optimized settings
# - Use 6 workers for better parallelization
# - Use a moderate cache_ttl of 300 seconds (5 minutes) to balance freshness and performance
default_scraper = ThreadedScraper(max_workers=6, cache_ttl=300)  # 5 minutes cache TTL

# A lock to ensure thread-safety when accessing the scraper
scraper_lock = Lock()

# Ensure database sessions are properly managed
@app.teardown_request
def teardown_request(exception=None):
    """Ensures database session is closed after each request."""
    if hasattr(g, 'db_session'):
        try:
            g.db_session.remove()
        except:
            pass
    
    # Always close the session to avoid connection leaks
    db.session.close()

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Define database models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    
class UserTicker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ticker = db.Column(db.String(20))
    __table_args__ = (db.UniqueConstraint('user_id', 'ticker', name='_user_ticker_uc'),)

@login_manager.user_loader
def load_user(user_id):
    try:
        user = User.query.get(int(user_id))
        return user
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {e}")
        return None
    finally:
        db.session.close()

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Create a simple form dict to pass to the template with proper lambda functions
    form = {
        'hidden_tag': lambda: '',
        'username': {
            'label': lambda **kwargs: f'<label for="username" class="{kwargs.get("class", "")}"">Username</label>',
            'errors': [],
            '__call__': lambda **kwargs: f'<input type="text" name="username" id="username" class="{kwargs.get("class", "")}" required>'
        },
        'password': {
            'label': lambda **kwargs: f'<label for="password" class="{kwargs.get("class", "")}"">Password</label>',
            'errors': [],
            '__call__': lambda **kwargs: f'<input type="password" name="password" id="password" class="{kwargs.get("class", "")}" required>'
        },
        'remember': {
            'label': lambda **kwargs: f'<label for="remember" class="{kwargs.get("class", "")}"">Remember Me</label>',
            'errors': [],
            '__call__': lambda **kwargs: f'<input type="checkbox" name="remember" id="remember" class="{kwargs.get("class", "")}">'
        },
        'submit': lambda **kwargs: f'<button type="submit" class="{kwargs.get("class", "")}">Log In</button>'
    }
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        try:
            user = User.query.filter_by(username=username).first()
            
            if not user or not check_password_hash(user.password, password):
                flash('Please check your login details and try again.')
                return redirect(url_for('login'))
            
            login_user(user, remember=remember)
            session.permanent = True
            
            # Redirect to the page requested before login
            next_page = request.args.get('next')
            if not next_page or next_page.startswith('//'):
                next_page = url_for('dashboard')
                
            return redirect(next_page)
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('An error occurred during login. Please try again.')
            return redirect(url_for('login'))
        finally:
            db.session.close()
    
    return render_template('login.html', form=form)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Create a simple form dict to pass to the template with proper lambda functions
    form = {
        'hidden_tag': lambda: '',
        'username': {
            'label': lambda **kwargs: f'<label for="username" class="{kwargs.get("class", "")}">Username</label>',
            'errors': [],
            '__call__': lambda **kwargs: f'<input type="text" name="username" id="username" class="{kwargs.get("class", "")}" required>'
        },
        'email': {
            'label': lambda **kwargs: f'<label for="email" class="{kwargs.get("class", "")}">Email</label>',
            'errors': [],
            '__call__': lambda **kwargs: f'<input type="email" name="email" id="email" class="{kwargs.get("class", "")}" required>'
        },
        'password': {
            'label': lambda **kwargs: f'<label for="password" class="{kwargs.get("class", "")}">Password</label>',
            'errors': [],
            '__call__': lambda **kwargs: f'<input type="password" name="password" id="password" class="{kwargs.get("class", "")}" required>'
        },
        'submit': lambda **kwargs: f'<button type="submit" class="{kwargs.get("class", "")}">Sign Up</button>'
    }
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Check if username or email already exists
            user_with_username = User.query.filter_by(username=username).first()
            user_with_email = User.query.filter_by(email=email).first()
            
            if user_with_username:
                flash('Username already exists.')
                return redirect(url_for('signup'))
                
            if user_with_email:
                flash('Email address already in use.')
                return redirect(url_for('signup'))
            
            # Create new user
            new_user = User(
                username=username,
                email=email,
                password=generate_password_hash(password, method='pbkdf2:sha256')
            )
            
            # Add default tickers for new users
            db.session.add(new_user)
            db.session.commit()
            
            # Add some default tickers
            default_tickers = ['SPY', 'AAPL', 'MSFT', 'GOOGL', 'AMZN']
            for ticker in default_tickers:
                user_ticker = UserTicker(user_id=new_user.id, ticker=ticker)
                db.session.add(user_ticker)
            
            db.session.commit()
            
            # Log the user in
            login_user(new_user)
            session.permanent = True
            
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()  # Rollback on error
            logger.error(f"Signup error: {e}")
            flash('An error occurred during sign up. Please try again.')
            return redirect(url_for('signup'))
        finally:
            db.session.close()
    
    return render_template('signup.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        # Get user's tickers
        user_tickers = UserTicker.query.filter_by(user_id=current_user.id).all()
        tickers = [ut.ticker for ut in user_tickers]
        
        # If this is an AJAX request, return JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"authenticated": True})
        
        # For fresh page loads, prefetch ticker data with fast mode to make the initial experience quicker
        if tickers:
            try:
                with scraper_lock:
                    # Use fast_mode=True for initial page loads to reduce delays
                    default_scraper.get_multiple_stock_data(tickers, fast_mode=True)
                    logger.info(f"Prefetched data for {len(tickers)} tickers on dashboard load (fast mode)")
            except Exception as e:
                # If prefetch fails, just log it and continue - the frontend will still work
                logger.error(f"Prefetch error: {e}")
            
        return render_template('dashboard.html', tickers=tickers)
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash('An error occurred. Please try again.')
        return redirect(url_for('login'))
    finally:
        db.session.close()

@app.route('/add_ticker', methods=['POST'])
@login_required
def add_ticker():
    ticker = request.form.get('ticker', '').strip().upper()
    
    if not ticker:
        return jsonify({"success": False, "error": "No ticker symbol provided"}), 400
        
    try:
        # Check if ticker already exists for this user
        existing_ticker = UserTicker.query.filter_by(user_id=current_user.id, ticker=ticker).first()
        if existing_ticker:
            return jsonify({"success": False, "error": f"{ticker} is already in your watchlist"}), 400
            
        # Validate the ticker by attempting to get data for it
        try:
            with scraper_lock:
                ticker_data = default_scraper.get_stock_data(ticker)
                
            if not ticker_data or 'error' in ticker_data:
                error_msg = ticker_data.get('error', f"Could not find ticker {ticker}")
                return jsonify({"success": False, "error": error_msg}), 404
        except Exception as e:
            logger.error(f"Error validating ticker {ticker}: {e}")
            return jsonify({"success": False, "error": f"Could not validate ticker {ticker}"}), 500
            
        # Add ticker to user's watchlist
        new_ticker = UserTicker(user_id=current_user.id, ticker=ticker)
        db.session.add(new_ticker)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()  # Rollback on error
        logger.error(f"Error adding ticker {ticker}: {e}")
        return jsonify({"success": False, "error": "An error occurred. Please try again."}), 500
    finally:
        db.session.close()

@app.route('/remove_ticker/<ticker>', methods=['POST'])
@login_required
def remove_ticker(ticker):
    try:
        ticker = ticker.strip().upper()
        ticker_record = UserTicker.query.filter_by(user_id=current_user.id, ticker=ticker).first()
        
        if not ticker_record:
            return jsonify({"success": False, "error": f"{ticker} not found in your watchlist"}), 404
            
        db.session.delete(ticker_record)
        db.session.commit()
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()  # Rollback on error
        logger.error(f"Error removing ticker {ticker}: {e}")
        return jsonify({"success": False, "error": "An error occurred. Please try again."}), 500
    finally:
        db.session.close()

@app.route('/api/stock_data')
@login_required
def get_stock_data():
    ticker = request.args.get('ticker', '').strip().upper()
    
    if not ticker:
        return jsonify({"error": "No ticker symbol provided"}), 400
        
    try:
        start_time = time.time()
        
        # Add timestamp to avoid caching on client side
        with scraper_lock:
            data = default_scraper.get_stock_data(ticker)
        
        end_time = time.time()
        logger.info(f"Fetched data for {ticker} in {end_time - start_time:.2f}s")
        
        # Add Cache-Control headers to prevent caching
        response = jsonify(data)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
    except Exception as e:
        logger.error(f"Error getting stock data for {ticker}: {e}")
        return jsonify({"error": f"Failed to fetch data for {ticker}"}), 500

@app.route('/api/bulk_stock_data')
@login_required
def get_bulk_stock_data():
    # Get tickers from request or use user's tickers if not specified
    tickers_param = request.args.get('tickers', '')
    
    # Check if this is an initial load request (we'll use fast mode if it is)
    initial_load = request.args.get('initial_load', '').lower() == 'true'
    
    try:
        if tickers_param:
            # If tickers are specified in the request, use those
            tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
        else:
            # Otherwise, use all of the user's tickers
            try:
                user_tickers = UserTicker.query.filter_by(user_id=current_user.id).all()
                tickers = [ut.ticker for ut in user_tickers]
            except Exception as db_error:
                logger.error(f"Database error fetching user tickers: {db_error}")
                return jsonify({"error": "Failed to fetch user tickers"}), 500
        
        if not tickers:
            return jsonify({"error": "No tickers available"}), 400
        
        # Log request details
        logger.info(f"Bulk data request for {len(tickers)} tickers: {', '.join(tickers[:5])}{' ...' if len(tickers) > 5 else ''}{' (fast mode)' if initial_load else ''}")
        
        start_time = time.time()
        
        try:
            # Get data for all tickers at once using the threaded scraper
            with scraper_lock:
                data = default_scraper.get_multiple_stock_data(tickers, fast_mode=initial_load)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Get statistics from the scraper
            stats = default_scraper.get_stats()
            cache_info = default_scraper.get_cache_info() if hasattr(default_scraper, 'get_cache_info') else None
            
            # Add enhanced metadata about the request
            # Fix: Check if cached_tickers and uncached_tickers are lists before calling len()
            cached_tickers = data['metadata'].get('cached_tickers', []) if 'metadata' in data else []
            uncached_tickers = data['metadata'].get('uncached_tickers', []) if 'metadata' in data else []
            
            # Fix: Ensure cached_tickers and uncached_tickers are treated as values, not lists if they're integers
            cache_hits = len(cached_tickers) if isinstance(cached_tickers, list) else cached_tickers
            cache_misses = len(uncached_tickers) if isinstance(uncached_tickers, list) else uncached_tickers
            
            data['metadata'] = {
                'total_time': total_time,
                'tickers_count': len(tickers),
                'average_time_per_ticker': total_time / max(len(tickers), 1),
                'cache_hits': cache_hits,
                'cache_misses': cache_misses,
                'cache_size': stats.get('cache_size', 0),
                'fast_mode': initial_load,
                'success_rate': f"{len([t for t in tickers if t in data and data[t].get('price') != 'N/A']) / len(tickers) * 100:.1f}%"
            }
            
            logger.info(f"Fetched bulk data for {len(tickers)} tickers in {total_time:.2f}s " +
                      f"(cache hits: {data['metadata']['cache_hits']}, misses: {data['metadata']['cache_misses']})")
            
            # Add Cache-Control headers to prevent caching
            response = jsonify(data)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            
            return response
            
        except Exception as scraper_error:
            logger.error(f"Scraper error: {scraper_error}")
            
            # Try to get any partial results that might be in the cache
            partial_results = {}
            try:
                for ticker in tickers:
                    with scraper_lock:
                        result = default_scraper.get_stock_data(ticker)
                        if result:
                            partial_results[ticker] = result
            except:
                # If even that fails, return the error
                pass
                
            if partial_results:
                logger.info(f"Returning {len(partial_results)} partial results after scraper error")
                partial_results['metadata'] = {
                    'error': str(scraper_error),
                    'partial_results': True,
                    'success_count': len(partial_results),
                    'total_requested': len(tickers)
                }
                return jsonify(partial_results)
            else:
                return jsonify({"error": f"Scraper error: {str(scraper_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Error getting bulk stock data: {e}")
        return jsonify({"error": f"Failed to fetch bulk stock data: {str(e)}"}), 500

@app.route('/api/session/keep-alive')
@login_required
def keep_session_alive():
    # Update the session to keep it active
    session.modified = True
    return jsonify({"status": "success", "timestamp": datetime.datetime.now().isoformat()})

@app.route('/api/clear_cache', methods=['POST'])
@login_required
def clear_cache():
    try:
        with scraper_lock:
            default_scraper.clear_cache()
            stats = default_scraper.get_stats()
        
        return jsonify({
            "status": "success", 
            "message": "Cache cleared successfully",
            "stats": stats
        })
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/force_refresh', methods=['POST'])
@login_required
def force_refresh():
    try:
        # Reset the scraper's cache and stats
        with scraper_lock:
            default_scraper.clear_cache()
            default_scraper.reset_stats()
        
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error during force refresh: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/test/stock_data')
def test_stock_data():
    """Test endpoint for the scraper that doesn't require authentication"""
    tickers_param = request.args.get('tickers', 'AAPL,MSFT,GOOGL')
    
    # Check if this is an initial load request (we'll use fast mode if it is)
    initial_load = request.args.get('initial_load', '').lower() == 'true'
    
    try:
        # Use the tickers from the request
        tickers = [t.strip().upper() for t in tickers_param.split(',') if t.strip()]
        
        if not tickers:
            return jsonify({"error": "No tickers specified"}), 400
        
        # Limit the number of tickers to 5 for this test endpoint
        if len(tickers) > 5:
            tickers = tickers[:5]
            
        logger.info(f"Test API request for tickers: {', '.join(tickers)}{' (fast mode)' if initial_load else ''}")
        
        start_time = time.time()
        
        try:
            # Get data for all tickers using the threaded scraper
            with scraper_lock:
                data = default_scraper.get_multiple_stock_data(tickers, fast_mode=initial_load)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Add metadata about the request
            # Fix: Ensure we don't call len() on non-list types
            if 'metadata' in data:
                data['metadata']['total_time'] = total_time
                data['metadata']['test_endpoint'] = True
            
            logger.info(f"Test fetch completed in {total_time:.2f}s")
            
            return jsonify(data)
            
        except Exception as scraper_error:
            logger.error(f"Test endpoint scraper error: {scraper_error}")
            return jsonify({"error": f"Scraper error: {str(scraper_error)}"}), 500
            
    except Exception as e:
        logger.error(f"Test endpoint error: {e}")
        return jsonify({"error": f"Test endpoint error: {str(e)}"}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(error):
    logger.error(f"Server error: {error}")
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run the 247stonx Flask application')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    args = parser.parse_args()
    
    with app.app_context():
        # Create all tables
        db.create_all()
    
    # Use the port from command line arguments
    app.run(debug=True, host='0.0.0.0', port=args.port) 