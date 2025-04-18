import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session, make_response, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from forms import LoginForm, RegisterForm, AddTickerForm
import scraper

# Check for production environment
PRODUCTION = os.environ.get('PRODUCTION', 'false').lower() == 'true'

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///stocks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Set session timeout to 24 hours instead of the default
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
# Set session cookie secure options - adjust for production
app.config['SESSION_COOKIE_SECURE'] = PRODUCTION  # True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Initialize database
db = SQLAlchemy(app)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    tickers = db.relationship('UserTicker', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class UserTicker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ticker = db.Column(db.String(10), nullable=False)
    added_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'ticker', name='_user_ticker_uc'),)

@login_manager.user_loader
def load_user(user_id):
    # Updated to use get_or_404 for SQLAlchemy 2.0 compatibility
    try:
        return db.session.get(User, int(user_id))
    except:
        # Fallback to legacy method if needed
        return User.query.get(int(user_id))

@app.before_request
def before_request():
    # Make session permanent and set expiry time (24 hours)
    session.permanent = True
    # Renew the session on every request
    session.modified = True
    
    # If this is an API request and user is authenticated, extend the session
    if request.path.startswith('/api/') and current_user.is_authenticated:
        # Set a long-lived cookie to help with session persistence
        if not request.cookies.get('auth_check'):
            response = make_response()
            response.set_cookie('auth_check', '1', max_age=86400)

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Ensure session is renewed
    session.permanent = True
    session.modified = True
    
    user_tickers = UserTicker.query.filter_by(user_id=current_user.id).all()
    ticker_symbols = [user_ticker.ticker for user_ticker in user_tickers]
    form = AddTickerForm()
    return render_template('dashboard.html', tickers=ticker_symbols, form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            # Set session as permanent when logging in
            session.permanent = True
            session.modified = True
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        flash('Invalid username or password')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user is None:
            user = User(username=form.username.data)
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            
            # Add default tickers for new users
            default_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'SPY']
            for ticker in default_tickers:
                user_ticker = UserTicker(user_id=user.id, ticker=ticker)
                db.session.add(user_ticker)
            db.session.commit()
            
            flash('Registration successful! You can now log in.')
            return redirect(url_for('login'))
        flash('Username already exists')
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/add_ticker', methods=['POST'])
@login_required
def add_ticker():
    # Ensure session is renewed
    session.permanent = True
    session.modified = True
    
    ticker = request.form.get('ticker')
    if not ticker:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'No ticker provided'}), 400
        else:
            flash('Please enter a ticker symbol', 'danger')
            return redirect(url_for('dashboard'))
            
    # Check if ticker already exists for this user
    existing_ticker = UserTicker.query.filter_by(user_id=current_user.id, ticker=ticker.upper()).first()
    if existing_ticker:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Ticker already added'}), 400
        else:
            flash(f'You already added {ticker.upper()}', 'warning')
            return redirect(url_for('dashboard'))
    
    # Try to get stock data to validate ticker exists
    try:
        stock_data = scraper.scrape_stock_data(ticker.upper())
        if stock_data['price'] == 'N/A':
            # If price is N/A, ticker probably doesn't exist
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': f'Could not find ticker {ticker.upper()}'}), 400
            else:
                flash(f'Could not find ticker {ticker.upper()}', 'danger')
                return redirect(url_for('dashboard'))
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': f'Error validating ticker: {str(e)}'}), 500
        else:
            flash(f'Error validating ticker: {str(e)}', 'danger')
            return redirect(url_for('dashboard'))
    
    # Add ticker to user's collection
    new_ticker = UserTicker(ticker=ticker.upper(), user_id=current_user.id)
    db.session.add(new_ticker)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    else:
        flash(f'Added {ticker.upper()} to your dashboard', 'success')
        return redirect(url_for('dashboard'))

@app.route('/remove_ticker/<ticker>', methods=['POST'])
@login_required
def remove_ticker(ticker):
    # Ensure session is renewed
    session.permanent = True
    session.modified = True
    
    ticker_record = UserTicker.query.filter_by(user_id=current_user.id, ticker=ticker.upper()).first()
    
    if not ticker_record:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Ticker not found'}), 404
        else:
            flash(f'Ticker {ticker.upper()} not found', 'danger')
            return redirect(url_for('dashboard'))
    
    db.session.delete(ticker_record)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})
    else:
        flash(f'Removed {ticker.upper()} from your dashboard', 'success')
        return redirect(url_for('dashboard'))

@app.route('/api/stock_data', methods=['GET'])
@login_required
def get_stock_data():
    # Renew the session on each API call
    session.permanent = True
    session.modified = True
    
    ticker = request.args.get('ticker')
    
    if not ticker:
        return jsonify({'error': 'No ticker provided'}), 400
    
    try:
        stock_data = scraper.scrape_stock_data(ticker)
        response = jsonify(stock_data)
        # Set Cache-Control headers to prevent caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        return jsonify({
            'ticker': ticker,
            'price': 'N/A',
            'change': 'N/A',
            'market_status': 'Error',
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'error': str(e)
        }), 500  # Return 500 to indicate server error

@app.route('/api/session/keep-alive', methods=['GET'])
@login_required
def keep_session_alive():
    """Endpoint to keep user session alive"""
    session.permanent = True
    # Return current timestamp for confirmation
    return jsonify({
        'status': 'success', 
        'message': 'Session refreshed', 
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# Create all database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001) 