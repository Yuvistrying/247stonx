// Dashboard functionality for 247Stonx

// Configuration
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;
const SESSION_KEEPALIVE_INTERVAL = 120000; // 2 minutes between session keepalive pings
const AUTO_REFRESH_INTERVAL = 30000; // Reduced from 60 to 30 seconds
const USE_BULK_ENDPOINT = true; // Always use bulk endpoint for efficiency

// Tracking variables
let isRefreshing = false;
let lastSuccessfulRefresh = 0;
let failedRefreshCount = 0;

// Toast notification function
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-header">
            <strong class="mr-auto">${type.charAt(0).toUpperCase() + type.slice(1)}</strong>
            <button type="button" class="ml-2 mb-1 close" data-dismiss="toast" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    // Find or create toast container
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Add to container
    toastContainer.appendChild(toast);
    
    // Show toast using vanilla JavaScript
    toast.classList.add('show');
    
    // Add event listener for close button
    const closeBtn = toast.querySelector('[data-dismiss="toast"]');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        });
    }
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}

// Function to update a single ticker card with data
function updateTickerCard(ticker, data) {
    const cardContainer = document.querySelector(`.ticker-card-container[data-ticker="${ticker}"]`);
    if (!cardContainer) return;
    
    const priceEl = cardContainer.querySelector('.price');
    const changeTodayEl = cardContainer.querySelector('.change-today');
    const changeAfterHoursEl = cardContainer.querySelector('.change-after-hours');
    const marketStatusEl = cardContainer.querySelector('.market-status');
    
    if (data.error) {
        // Show error
        priceEl.textContent = 'Error';
        changeTodayEl.textContent = data.error;
        changeTodayEl.className = 'change-today mb-1 text-danger';
        changeAfterHoursEl.style.display = 'none';
        return;
    }
    
    // Set price (check if cached)
    priceEl.textContent = data.price;
    if (data.price.includes('cached')) {
        priceEl.classList.add('text-muted');
    } else {
        priceEl.classList.remove('text-muted');
    }
    
    // Check if we have both regular and after-hours changes
    if (data.change && data.change.includes('|')) {
        // Split the change data
        const [todayChange, afterHoursChange] = data.change.split('|').map(s => s.trim());
        
        // Extract the numeric part of the today change for coloring
        const todaySign = todayChange.startsWith('+');
        
        // Update the today's change with proper coloring
        changeTodayEl.innerHTML = '';
        
        // Add the colored part (amount and percentage)
        const colorSpan = document.createElement('span');
        colorSpan.className = todaySign ? 'price-up' : 'price-down';
        colorSpan.textContent = todayChange.replace('Today', '').trim();
        changeTodayEl.appendChild(colorSpan);
        
        // Add "Today" as plain text
        const todaySpan = document.createElement('span');
        todaySpan.className = 'change-label';
        todaySpan.textContent = ' Today';
        changeTodayEl.appendChild(todaySpan);
        
        // Show the after-hours element
        changeAfterHoursEl.style.display = 'block';
        
        // Extract the numeric part of the after hours change for coloring
        const afterHoursMatch = afterHoursChange.match(/([+-][^(]+)/);
        const afterHoursSign = afterHoursMatch ? afterHoursMatch[1].trim().startsWith('+') : false;
        
        // Update the after-hours change with proper coloring
        changeAfterHoursEl.innerHTML = '';
        
        // Add the colored part (amount and percentage)
        const afterHoursColorSpan = document.createElement('span');
        afterHoursColorSpan.className = afterHoursSign ? 'price-up' : 'price-down';
        afterHoursColorSpan.textContent = afterHoursChange.replace('After-hours', '').trim();
        changeAfterHoursEl.appendChild(afterHoursColorSpan);
        
        // Add "After-hours" as plain text
        const afterHoursSpan = document.createElement('span');
        afterHoursSpan.className = 'change-label';
        afterHoursSpan.textContent = ' After-hours';
        changeAfterHoursEl.appendChild(afterHoursSpan);
    } else {
        // Only regular hours data available
        // Extract the numeric part of the change for coloring
        const changeSign = data.change.includes('+');
        
        // Update the today's change with proper coloring
        changeTodayEl.innerHTML = '';
        
        // Add the colored part (amount and percentage)
        const colorSpan = document.createElement('span');
        colorSpan.className = changeSign ? 'price-up' : 'price-down';
        colorSpan.textContent = data.change;
        changeTodayEl.appendChild(colorSpan);
        
        // Hide the after-hours element
        changeAfterHoursEl.style.display = 'none';
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
    } else if (data.market_status.includes('stale')) {
        marketStatusEl.classList.add('text-warning');
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
    
    // Update both change elements to show error
    const changeTodayEl = cardContainer.querySelector('.change-today');
    changeTodayEl.textContent = 'Could not load data';
    changeTodayEl.className = 'change-today mb-1 text-danger';
    
    // Hide after-hours display during error
    const changeAfterHoursEl = cardContainer.querySelector('.change-after-hours');
    changeAfterHoursEl.style.display = 'none';
    
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
    const timeoutId = setTimeout(() => controller.abort(), 12000); // 12 second timeout (increased from 10)
    
    fetch(`/api/stock_data?ticker=${ticker}&_=${Date.now()}`, { // Add cache-busting parameter
        signal: controller.signal,
        credentials: 'same-origin',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
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

/**
 * Refreshes all ticker cards on the dashboard
 */
function refreshAllTickers() {
    // Verify elements still exist (page might have changed)
    if (document.querySelectorAll('.ticker-card-container').length === 0) {
        return;
    }
    
    // Keep the session alive
    keepSessionAlive();
    
    // Get all currently displayed tickers
    const tickerCards = document.querySelectorAll('.ticker-card-container');
    const tickers = Array.from(tickerCards).map(card => card.dataset.ticker).join(',');
    
    if (!tickers) {
        return; // No tickers to refresh
    }
    
    // Check if this is the initial load (first time refreshing)
    const isInitialLoad = !window.tickersRefreshed;
    
    // Fetch data for all tickers at once (more efficient)
    fetch(`/api/bulk_stock_data?tickers=${tickers}&initial_load=${isInitialLoad ? 'true' : 'false'}&_=${Date.now()}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Mark that we've refreshed tickers at least once
            window.tickersRefreshed = true;
            
            // Update each ticker card with the new data
            Object.keys(data).forEach(ticker => {
                if (ticker !== 'metadata') {
                    updateTickerCard(ticker, data[ticker]);
                }
            });
            
            // Optional: Log performance metrics if present
            if (data.metadata) {
                console.log(`Refreshed ${data.metadata.tickers_count} tickers in ${data.metadata.total_time.toFixed(2)}s`);
            }
        })
        .catch(error => {
            console.error('Error refreshing tickers:', error);
        });
}

// Set up automatic refresh every 30 seconds
document.addEventListener('DOMContentLoaded', function() {
    console.log('Setting up automatic refresh every 30 seconds');
    
    // Initial refresh of all tickers
    refreshAllTickers();
    
    // Set up automatic refresh with dynamic interval based on market hours
    function scheduleNextRefresh() {
        const now = new Date();
        const hours = now.getHours();
        const day = now.getDay();
        
        // Check if it's a weekday (1-5, Mon-Fri) and market hours (9:30 AM - 4:00 PM ET)
        // Simplified check that doesn't account for timezone, holidays, etc.
        const isWeekday = day >= 1 && day <= 5;
        const isMarketHours = hours >= 9 && hours < 16;
        const isExtendedHours = (hours >= 7 && hours < 9) || (hours >= 16 && hours < 20);
        
        let refreshInterval;
        
        if (isWeekday && isMarketHours) {
            // During market hours - refresh every 30 seconds
            refreshInterval = 30000;  // Reduced from 40 to 30 seconds
        } else if (isWeekday && isExtendedHours) {
            // During extended hours - refresh every minute
            refreshInterval = 60000;  // Reduced from 120 to 60 seconds
        } else {
            // Outside trading hours - refresh less frequently (every 3 minutes)
            refreshInterval = 180000;  // Reduced from 5 minutes to 3 minutes
        }
        
        console.log(`Next refresh in ${refreshInterval/1000} seconds`);
        setTimeout(() => {
            refreshAllTickers();
            scheduleNextRefresh();
        }, refreshInterval);
    }
    
    // Start the dynamic refresh scheduling
    scheduleNextRefresh();
    
    // Set up add ticker form
    const addTickerForm = document.getElementById('addTickerForm');
    if (addTickerForm) {
        addTickerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const tickerInput = this.querySelector('input[name="ticker"]');
            const submitBtn = this.querySelector('button[type="submit"]');
            
            // Validate input
            const ticker = tickerInput.value.trim().toUpperCase();
            if (!ticker) {
                showToast('Please enter a ticker symbol', 'error');
                return;
            }
            
            // Check if ticker already exists
            const existingCard = document.querySelector(`.ticker-card-container[data-ticker="${ticker}"]`);
            if (existingCard) {
                showToast(`${ticker} is already on your dashboard`, 'warning');
                tickerInput.value = '';
                return;
            }
            
            // Disable form and show spinner
            tickerInput.disabled = true;
            submitBtn.disabled = true;
            
            // Submit via AJAX
            fetch('/add_ticker', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: `ticker=${encodeURIComponent(ticker)}`
            })
            .then(response => {
                if (!response.ok) {
                    // Check Content-Type to see if it's JSON
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json().then(data => {
                            throw new Error(data.error || `Failed to add ticker (${response.status})`);
                        });
                    } else {
                        // Not JSON, handle as text
                        return response.text().then(text => {
                            throw new Error(text || `Failed to add ticker (${response.status})`);
                        });
                    }
                }
                
                // Check Content-Type to see if it's JSON
                const contentType = response.headers.get('content-type');
                if (contentType && contentType.includes('application/json')) {
                    return response.json();
                } else {
                    // Create a simple success object if not JSON
                    return { success: true };
                }
            })
            .then(data => {
                if (data.success) {
                    showToast(`Added ${ticker} to your dashboard`, 'success');
                    
                    // Reload the page to show the new ticker
                    window.location.reload();
                } else {
                    showToast(data.error || 'Failed to add ticker', 'error');
                }
            })
            .catch(error => {
                console.error("Error adding ticker:", error);
                showToast(error.message || 'Error adding ticker', 'error');
            })
            .finally(() => {
                // Re-enable form
                tickerInput.disabled = false;
                submitBtn.disabled = false;
                tickerInput.value = '';
                tickerInput.focus();
            });
        });
    }
    
    // Set up delete ticker buttons
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const card = this.closest('.ticker-card-container');
            const ticker = card.getAttribute('data-ticker');
            
            if (confirm(`Are you sure you want to remove ${ticker} from your dashboard?`)) {
                // Show loading state
                this.disabled = true;
                
                fetch(`/remove_ticker/${ticker}`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        // Check Content-Type to see if it's JSON
                        const contentType = response.headers.get('content-type');
                        if (contentType && contentType.includes('application/json')) {
                            return response.json().then(data => {
                                throw new Error(data.error || `Failed to remove ticker (${response.status})`);
                            });
                        } else {
                            // Not JSON, handle as text
                            return response.text().then(text => {
                                throw new Error(text || `Failed to remove ticker (${response.status})`);
                            });
                        }
                    }
                    
                    // Check Content-Type to see if it's JSON
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json();
                    } else {
                        // Create a simple success object if not JSON
                        return { success: true };
                    }
                })
                .then(data => {
                    if (data.success) {
                        // Animate card removal
                        card.style.transition = 'opacity 0.3s, transform 0.3s';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.8)';
                        
                        setTimeout(() => {
                            card.remove();
                            showToast(`Removed ${ticker} from your dashboard`, 'success');
                        }, 300);
                    } else {
                        showToast(data.error || 'Failed to remove ticker', 'error');
                        this.disabled = false;
                    }
                })
                .catch(error => {
                    console.error("Error removing ticker:", error);
                    showToast(error.message || 'Error removing ticker', 'error');
                    this.disabled = false;
                });
            }
        });
    });
    
    // Set up clear cache button if present
    const clearCacheBtn = document.getElementById('clearCacheBtn');
    if (clearCacheBtn) {
        clearCacheBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to clear the cache? This will force refreshing all data from source.')) {
                fetch('/api/clear_cache', {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        // Handle non-OK response
                        const contentType = response.headers.get('content-type');
                        if (contentType && contentType.includes('application/json')) {
                            return response.json().then(data => {
                                throw new Error(data.message || `Failed to clear cache (${response.status})`);
                            });
                        } else {
                            return response.text().then(text => {
                                throw new Error(text || `Failed to clear cache (${response.status})`);
                            });
                        }
                    }
                    
                    // Check Content-Type to see if it's JSON
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.includes('application/json')) {
                        return response.json();
                    } else {
                        // Create a simple success object if not JSON
                        return { status: 'success' };
                    }
                })
                .then(data => {
                    if (data.status === 'success') {
                        showToast('Cache cleared successfully', 'success');
                        // Trigger a refresh of all tickers
                        refreshAllTickers();
                    } else {
                        showToast(data.message || 'Failed to clear cache', 'error');
                    }
                })
                .catch(error => {
                    console.error("Error clearing cache:", error);
                    showToast(error.message || 'Error clearing cache', 'error');
                });
            }
        });
    }
}); 