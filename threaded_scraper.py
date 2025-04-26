import requests
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dateutil import parser
import threading
import concurrent.futures
from lxml import html
import time
from typing import Dict, List, Any, Optional
import scraper
import random

# Import the original scraper functionality to reuse
from scraper import scrape_stock_data

# Thread-local storage to keep track of thread-specific data
thread_local = threading.local()

class ThreadedScraper:
    """
    A threaded stock data scraper that fetches data for multiple tickers concurrently.
    Uses ThreadPoolExecutor to parallelize requests and improve performance.
    """
    
    def __init__(self, max_workers: Optional[int] = None, cache_ttl: int = 600):
        """
        Initialize the threaded scraper with a specified number of workers.
        
        Args:
            max_workers (int, optional): Maximum number of worker threads to use.
            cache_ttl (int, optional): Time to live for cached data in seconds.
        """
        # Increase default worker count for better parallelization
        self.max_workers = max_workers if max_workers else 6  # Increased from 4 to 6 workers by default
        self._lock = threading.Lock()
        self._stats = {
            'requests_made': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_time': 0,
            'last_batch_time': 0,
            'last_batch_size': 0,
            'last_request_time': 0
        }
        # Cache to store results with timestamps to avoid redundant requests
        self._cache = {}
        self._cache_ttl = cache_ttl  # Allow configurable TTL
        # Maximum delay between requests (seconds)
        self._max_delay = 0.3  # Reduced from 0.8 to 0.3 to speed up requests
        # Last time each ticker was scraped
        self._last_scrape_time = {}
    
    def get_stock_data(self, ticker: str, fast_mode: bool = False) -> Dict[str, Any]:
        """
        Fetch stock data for a single ticker using the base scraper.
        Increments stats counters for tracking performance.
        
        Args:
            ticker (str): The stock ticker symbol to fetch data for.
            fast_mode (bool, optional): If True, minimize delays between requests.
            
        Returns:
            Dict[str, Any]: Stock data dictionary with price, change, and market status.
        """
        # Check cache first
        current_time = time.time()
        if ticker in self._cache:
            cache_time = self._cache[ticker]['timestamp']
            if current_time - cache_time < self._cache_ttl:
                # Return cached data if still fresh
                print(f"Using cached data for {ticker} ({current_time - cache_time:.1f}s old)")
                return self._cache[ticker]['data']
        
        # Add a small, reasonable delay to avoid overwhelming the server
        with self._lock:
            # Check when this specific ticker was last scraped
            ticker_last_time = self._last_scrape_time.get(ticker, 0)
            
            # In fast mode, use minimal delays for page initial load
            if fast_mode:
                # Significantly reduce delays for fast mode
                ticker_delay = max(0, 0.1 - (current_time - ticker_last_time))
                global_delay = 0
                since_last_request = current_time - self._stats['last_request_time']
                if since_last_request < 0.05:  # Use much smaller delay in fast mode
                    global_delay = min(0.1, 0.05 - since_last_request + random.uniform(0.01, 0.02))
            else:
                # Regular mode with normal delays
                ticker_delay = max(0, 0.5 - (current_time - ticker_last_time))
                global_delay = 0
                since_last_request = current_time - self._stats['last_request_time']
                if since_last_request < 0.2:
                    global_delay = min(self._max_delay, 0.2 - since_last_request + random.uniform(0.01, 0.05))
            
            # Use the longer of the two delays
            delay = max(ticker_delay, global_delay)
            
            # Cap maximum delay
            delay = min(delay, 1.0 if not fast_mode else 0.3)
            
            if delay > 0.1 and not fast_mode:  # Only log substantial delays in non-fast mode
                print(f"Adding delay of {delay:.2f}s before scraping {ticker}")
                
            if delay > 0:
                time.sleep(delay)
            
            # Update timestamps
            self._stats['last_request_time'] = time.time()
            self._last_scrape_time[ticker] = time.time()
        
        try:
            # Use the existing scraper module to get stock data
            result = scrape_stock_data(ticker)
            
            # If we got valid price data, cache it
            if result['price'] != 'N/A':
                with self._lock:
                    self._cache[ticker] = {
                        'data': result,
                        'timestamp': time.time()
                    }
                    self._stats['requests_made'] += 1
                    self._stats['successful_requests'] += 1
            else:
                # Got N/A result, check if we have a valid cached version
                if ticker in self._cache:
                    # Use cached data but mark it as stale
                    print(f"Got N/A for {ticker}, using cached data but marking as stale")
                    cached_data = self._cache[ticker]['data'].copy()
                    cached_data['price'] += " (cached)"
                    cached_data['market_status'] = "Data may be stale"
                    with self._lock:
                        self._stats['requests_made'] += 1
                        self._stats['failed_requests'] += 1
                    return cached_data
                
                # No valid cache, increment failed counter
                with self._lock:
                    self._stats['requests_made'] += 1
                    self._stats['failed_requests'] += 1
            
            return result
        except Exception as e:
            with self._lock:
                self._stats['requests_made'] += 1
                self._stats['failed_requests'] += 1
            
            # Check if we have cached data we can use instead
            if ticker in self._cache:
                print(f"Error scraping {ticker}, using cached data: {str(e)}")
                cached_data = self._cache[ticker]['data'].copy()
                cached_data['price'] += " (cached)"
                cached_data['market_status'] = "Data may be stale"
                return cached_data
            
            # Return error data
            return {
                'ticker': ticker,
                'price': 'N/A',
                'change': 'N/A',
                'market_status': 'Error: Rate limited',
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'error': str(e)
            }
    
    def get_multiple_stock_data(self, tickers: List[str], fast_mode: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Fetch stock data for multiple tickers concurrently using ThreadPoolExecutor.
        
        Args:
            tickers (List[str]): List of ticker symbols to fetch data for.
            fast_mode (bool, optional): If True, minimize delays between requests for initial page loads.
            
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping ticker symbols to their stock data.
        """
        start_time = time.time()
        results = {}
        
        # Skip empty ticker list
        if not tickers:
            return results
        
        # Prioritize cached results first to improve responsiveness
        cached_tickers = []
        uncached_tickers = []
        
        current_time = time.time()
        for ticker in tickers:
            if ticker in self._cache:
                cache_time = self._cache[ticker]['timestamp']
                if current_time - cache_time < self._cache_ttl:
                    # Use cached data
                    results[ticker] = self._cache[ticker]['data']
                    cached_tickers.append(ticker)
                    continue
            uncached_tickers.append(ticker)
        
        # Process uncached tickers
        if uncached_tickers:
            # Adjust batch size based on mode
            max_tickers_per_batch = min(len(uncached_tickers), 20 if fast_mode else 12)
            batched_tickers = [uncached_tickers[i:i+max_tickers_per_batch] for i in range(0, len(uncached_tickers), max_tickers_per_batch)]
            
            for batch in batched_tickers:
                # Shuffle tickers to randomize the order of requests
                random_tickers = batch.copy()
                random.shuffle(random_tickers)
                
                # Process each batch with improved concurrency
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all ticker fetch tasks
                    future_to_ticker = {
                        executor.submit(self.get_stock_data, ticker, fast_mode): ticker 
                        for ticker in random_tickers
                    }
                    
                    # Process results as they complete
                    for future in concurrent.futures.as_completed(future_to_ticker):
                        ticker = future_to_ticker[future]
                        try:
                            data = future.result()
                            results[ticker] = data
                        except Exception as e:
                            # Handle unexpected exceptions and provide fallback data
                            results[ticker] = {
                                'ticker': ticker,
                                'price': 'N/A',
                                'change': 'N/A',
                                'market_status': 'Error',
                                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'error': f"Unexpected error: {str(e)}"
                            }
                
                # Reduce the delay between batches, especially in fast mode
                if len(batched_tickers) > 1 and batch != batched_tickers[-1]:
                    time.sleep(0.1 if fast_mode else 0.2)
        
        # Update stats for this batch
        elapsed_time = time.time() - start_time
        with self._lock:
            self._stats['total_time'] += elapsed_time
            self._stats['last_batch_time'] = elapsed_time
            self._stats['last_batch_size'] = len(tickers)
        
        # Add metadata for compatibility with previous implementation
        metadata = {
            'total_time': elapsed_time,
            'tickers_processed': len(tickers),
            'average_time_per_ticker': elapsed_time / len(tickers) if tickers else 0,
            'cached_tickers': len(cached_tickers),
            'uncached_tickers': len(uncached_tickers),
            'fast_mode': fast_mode
        }
        results['metadata'] = metadata
        
        return results
    
    def clear_cache(self):
        """Clear the data cache"""
        with self._lock:
            self._cache = {}
            print("Cache cleared")
    
    def get_stats(self):
        """Get performance statistics"""
        with self._lock:
            avg_time = 0
            if self._stats['successful_requests'] > 0:
                avg_time = self._stats['total_time'] / self._stats['successful_requests']
            
            stats = {
                'requests_made': self._stats['requests_made'],
                'successful_requests': self._stats['successful_requests'],
                'failed_requests': self._stats['failed_requests'],
                'cache_size': len(self._cache),
                'cache_ttl': self._cache_ttl,
                'average_time_per_request': avg_time
            }
            return stats
    
    def reset_stats(self):
        """Reset performance statistics"""
        with self._lock:
            self._stats = {
                'requests_made': 0,
                'successful_requests': 0,
                'failed_requests': 0,
                'total_time': 0,
                'last_batch_time': 0,
                'last_batch_size': 0,
                'last_request_time': time.time()
            }
            print("Stats reset")
    
    def get_cache_info(self):
        """Get information about the current cache state"""
        with self._lock:
            current_time = time.time()
            cache_info = {
                'cache_size': len(self._cache),
                'cache_ttl': self._cache_ttl,
                'tickers': {}
            }
            
            for ticker, cache_entry in self._cache.items():
                age = current_time - cache_entry['timestamp']
                time_left = max(0, self._cache_ttl - age)
                cache_info['tickers'][ticker] = {
                    'age': f"{age:.1f}s",
                    'time_left': f"{time_left:.1f}s",
                    'fresh': time_left > 0
                }
            
            return cache_info

# Create a default instance for easy imports - use 4 workers for better performance
default_scraper = ThreadedScraper(max_workers=4)

if __name__ == "__main__":
    # Run the test
    test_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "SPY", "QQQ", "NVDA"]
    
    # Create a threaded scraper with 4 workers
    scraper = ThreadedScraper(max_workers=4)
    
    # Test the bulk ticker data retrieval
    print(f"Testing with {len(test_tickers)} tickers: {', '.join(test_tickers)}")
    start_time = time.time()
    results = scraper.get_multiple_stock_data(test_tickers)
    elapsed = time.time() - start_time
    
    print(f"Total time: {elapsed:.2f} seconds")
    print(f"Results for each ticker:")
    
    for ticker, data in results.items():
        if ticker != 'metadata':
            print(f"{ticker}: {data.get('price', 'N/A')} | {data.get('change', 'N/A')}")
    
    print(f"\nCache statistics:")
    stats = scraper.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Show cache info
    print("\nCache info:")
    cache_info = scraper.get_cache_info()
    print(f"Cache size: {cache_info['cache_size']} tickers")
    for ticker, info in cache_info['tickers'].items():
        print(f"{ticker}: Age {info['age']}, TTL remaining: {info['time_left']}") 