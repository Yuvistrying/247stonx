// Dashboard functionality for 247Stonx

// Configuration
const MAX_RETRIES = 3; // Increased retries
const RETRY_DELAY = 2000; // 2 seconds between retries
const SESSION_KEEPALIVE_INTERVAL = 15000; // 15 seconds for session keepalive
const AUTO_REFRESH_INTERVAL = 10000; // 10 seconds (changed from 5 seconds)

// Toast notification function
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1050';
        document.body.appendChild(toastContainer);
    }
    
    // Create a unique ID for the toast
    const toastId = 'toast-' + Date.now();
    
    // Set toast color based on type
    let bgColor = 'bg-info';
    if (type === 'success') bgColor = 'bg-success';
    if (type === 'error') bgColor = 'bg-danger';
    if (type === 'warning') bgColor = 'bg-warning';
    
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast ${bgColor} text-white`;
    toast.id = toastId;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.innerHTML = `
        <div class="toast-header">
            <strong class="me-auto">247Stonx</strong>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    // Add toast to container
    toastContainer.appendChild(toast);
    
    // Initialize Bootstrap toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: 5000
    });
    
    // Show toast
    bsToast.show();
    
    // Remove toast after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

// Function to update a single ticker card with data
function updateTickerCard(ticker, data) {
    const cardContainer = document.querySelector(`.ticker-card-container[data-ticker="${ticker}"]`);
    if (!cardContainer) return;
    
    const dataEl = cardContainer.querySelector('.ticker-data');
    const priceEl = cardContainer.querySelector('.price');
    const changeEl = cardContainer.querySelector('.change');
    const marketStatusEl = cardContainer.querySelector('.market-status');
    
    // Ensure data is visible
    dataEl.style.display = 'block';
    
    // Update price
    priceEl.textContent = data.price;
    
    // Update change with color coding
    changeEl.textContent = data.change;
    changeEl.className = 'change mb-0';
    if (data.change.includes('+')) {
        changeEl.classList.add('price-up');
    } else if (data.change.includes('-')) {
        changeEl.classList.add('price-down');
    } else {
        changeEl.classList.add('price-neutral');
    }
    
    // Update market status
    marketStatusEl.textContent = data.market_status;
    marketStatusEl.className = 'market-status badge';
    
    if (data.market_status === 'Market Open') {
        marketStatusEl.classList.add('market-open');
    } else if (data.market_status === 'Market Closed') {
        marketStatusEl.classList.add('market-closed');
    } else if (data.market_status === 'After Hours' || data.market_status === 'Pre-market') {
        marketStatusEl.classList.add('market-' + data.market_status.toLowerCase().replace(' ', '-'));
    }
}

// Function to handle errors
function handleError(ticker, error, retryCount = 0) {
    console.log(`Error loading data for ${ticker}: ${error} (retry: ${retryCount})`);
    
    // Check if error is due to session expiration (redirect to login)
    if (error.includes('Unauthorized') || error.includes('login') || error === 'Failed to fetch') {
        console.log('Session expired or network issue. Attempting to reconnect...');
        
        // Immediately try to keep session alive
        keepSessionAlive();
        
        if (retryCount < MAX_RETRIES) {
            // Retry after delay
            setTimeout(() => {
                fetchTickerData(ticker, retryCount + 1);
            }, RETRY_DELAY);
            return;
        } else if (window.location.pathname !== '/login') {
            // Check login status before redirecting
            checkLoginStatus()
              .then(isLoggedIn => {
                  if (!isLoggedIn) {
                      console.log('Session confirmed expired, redirecting to login');
                      window.location.href = '/login';
                  }
              });
            return;
        }
    }
    
    if (retryCount < MAX_RETRIES) {
        // Retry after delay
        setTimeout(() => {
            fetchTickerData(ticker, retryCount + 1);
        }, RETRY_DELAY);
        return;
    }
    
    const cardContainer = document.querySelector(`.ticker-card-container[data-ticker="${ticker}"]`);
    if (!cardContainer) return;
    
    const dataEl = cardContainer.querySelector('.ticker-data');
    dataEl.style.display = 'block';
    
    // Show error
    const priceEl = cardContainer.querySelector('.price');
    priceEl.textContent = 'Error';
    
    const changeEl = cardContainer.querySelector('.change');
    changeEl.textContent = 'Could not load data';
    changeEl.className = 'change mb-0 text-danger';
    
    // Show toast for persistent errors
    if (retryCount >= MAX_RETRIES) {
        showToast(`Unable to load data for ${ticker} after several attempts.`, 'error');
    }
}

// Function to check login status
function checkLoginStatus() {
    return fetch('/dashboard', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        },
        redirect: 'manual' // Don't follow redirects
    })
    .then(response => {
        return response.ok && !response.redirected;
    })
    .catch(() => {
        return false;
    });
}

// Function to fetch data for a single ticker
function fetchTickerData(ticker, retryCount = 0) {
    const cardContainer = document.querySelector(`.ticker-card-container[data-ticker="${ticker}"]`);
    if (!cardContainer) return;
    
    // Create a controller for aborting the request if it takes too long
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000); // 8 second timeout
    
    fetch(`/api/stock_data?ticker=${ticker}&_=${Date.now()}`, { // Add cache-busting parameter
        signal: controller.signal,
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        clearTimeout(timeoutId);
        if (!response.ok) {
            if (response.status === 401 || response.status === 302 || response.redirected) {
                throw new Error('Unauthorized - Session may have expired');
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        updateTickerCard(ticker, data);
    })
    .catch(error => {
        console.error(`Error fetching data for ${ticker}:`, error);
        if (error.name === 'AbortError') {
            handleError(ticker, 'Request timed out', retryCount);
        } else {
            handleError(ticker, error.message || 'Failed to fetch', retryCount);
        }
    });
}

// Function to keep session alive
function keepSessionAlive() {
    fetch('/api/session/keep-alive', {
        method: 'GET',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        },
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`Session keepalive failed: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Session kept alive:', data.timestamp);
    })
    .catch(error => {
        console.log('Session keepalive error:', error);
    });
}

// Setup session keepalive interval
setInterval(keepSessionAlive, SESSION_KEEPALIVE_INTERVAL);

// Start a session keepalive immediately
keepSessionAlive();

// Function to refresh all tickers
function refreshAllTickers() {
    const tickerCards = document.querySelectorAll('.ticker-card-container');
    
    // If no tickers, don't do anything
    if (tickerCards.length === 0) return;
    
    // First keep session alive to ensure we're logged in
    keepSessionAlive();
    
    // Refresh each ticker with a slight delay to avoid rate limiting
    tickerCards.forEach((card, index) => {
        const ticker = card.getAttribute('data-ticker');
        if (ticker) {
            // Use a staggered approach with smaller delays since we're refreshing more frequently
            setTimeout(() => {
                fetchTickerData(ticker);
            }, index * 200); // 200ms delay between requests (reduced from 300ms)
        }
    });
}

// Set up automatic refresh every 10 seconds
document.addEventListener('DOMContentLoaded', function() {
    console.log('Setting up automatic refresh every 10 seconds');
    
    // Initial refresh of all tickers
    refreshAllTickers();
    
    // Set up automatic refresh
    setInterval(refreshAllTickers, AUTO_REFRESH_INTERVAL);
    
    // Add ticker functionality
    const addTickerForm = document.getElementById('addTickerForm');
    if (addTickerForm) {
        addTickerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const tickerInput = document.getElementById('tickerSymbol');
            const ticker = tickerInput.value.trim().toUpperCase();
            
            if (!ticker) {
                showToast('Please enter a ticker symbol', 'warning');
                return;
            }
            
            // Submit form via AJAX
            fetch('/add_ticker', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `ticker=${ticker}`
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Network response was not ok');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Show success message before reloading
                    showToast(`Added ${ticker} to your dashboard`, 'success');
                    // Reload the page to show the new ticker
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000); // Delay reload to show toast
                } else {
                    showToast(data.error || 'Failed to add ticker', 'error');
                }
            })
            .catch(error => {
                console.error('Error adding ticker:', error);
                if (error.message.includes('already added')) {
                    showToast(`You already have ${ticker} in your dashboard`, 'warning');
                } else if (error.message.includes('Could not find ticker')) {
                    showToast(`Could not find ticker ${ticker}. Please check the symbol and try again.`, 'error');
                } else {
                    showToast('Failed to add ticker. Please try again.', 'error');
                }
            });
            
            // Clear the input
            tickerInput.value = '';
        });
    }
    
    // Remove ticker functionality
    document.querySelectorAll('.delete-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const tickerId = this.getAttribute('data-ticker');
            if (!tickerId) return;
            
            if (confirm(`Are you sure you want to remove ${tickerId} from your watchlist?`)) {
                fetch(`/remove_ticker/${tickerId}`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(data => {
                            throw new Error(data.error || 'Network response was not ok');
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // Remove the card from the DOM
                        const card = document.querySelector(`.ticker-card-container[data-ticker="${tickerId}"]`);
                        if (card) {
                            card.remove();
                            showToast(`Removed ${tickerId} from your dashboard`, 'success');
                        }
                    } else {
                        showToast(data.error || 'Failed to remove ticker', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error removing ticker:', error);
                    showToast('Failed to remove ticker. Please try again.', 'error');
                });
            }
        });
    });
}); 