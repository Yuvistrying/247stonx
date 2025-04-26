import os
import requests
import re
import json
import time
import pytz
from bs4 import BeautifulSoup
from datetime import datetime
from lxml import html
import random

# List of realistic user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.63',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1'
]

# Random referers
REFERERS = [
    'https://www.google.com/',
    'https://www.bing.com/',
    'https://www.yahoo.com/',
    'https://finance.yahoo.com/',
    'https://www.cnbc.com/',
    'https://www.marketwatch.com/',
    'https://www.bloomberg.com/',
    'https://www.investing.com/'
]

def get_random_headers():
    """Generate random headers to make requests look more like regular browser traffic"""
    user_agent = random.choice(USER_AGENTS)
    referer = random.choice(REFERERS)
    
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': referer,
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'TE': 'Trailers',
        'DNT': '1',  # Do Not Track
    }
    
    return headers

def scrape_stock_data(ticker):
    """
    Scrape stock data from Robinhood for a given ticker
    Uses a multi-layer approach:
    1. JSON embedded data extraction (primary method)
    2. API fallback (if JSON fails)
    3. Direct HTML element extraction (if both JSON and API fail)
    """
    # URL for Robinhood stock page
    url = f"https://robinhood.com/us/en/stocks/{ticker}/"
    
    # Get random headers for this request
    headers = get_random_headers()
    
    # Add a random delay between 0.5 and 2 seconds to simulate human browsing
    time.sleep(random.uniform(0.5, 2.0))

    # Default return values
    stock_data = {
        'ticker': ticker,
        'price': 'N/A',
        'change': 'N/A',
        'market_status': 'Unknown',
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        print(f"Scraping data for {ticker} from {url}")
        
        # Get the webpage content
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # APPROACH 1: Extract data directly from HTML elements (most reliable)
            print("Approach 1: Extracting directly from HTML elements...")
            try:
                # Parse HTML using lxml for XPath support
                tree = html.fromstring(html_content)
                
                # Extract price using provided selectors
                # CSS: #sdp-market-price
                # XPath: //*[@id="sdp-market-price"]
                price_element = tree.xpath('//*[@id="sdp-market-price"]')
                if price_element:
                    price_text = price_element[0].text_content().strip()
                    price_match = re.search(r'\$?(\d+\.\d+)', price_text)
                    if price_match:
                        stock_data['price'] = f"${float(price_match.group(1)):.2f}"
                        print(f"Extracted price from HTML: {stock_data['price']}")
                
                # Extract price change using provided selectors
                # CSS: #sdp-price-chart-price-change
                # XPath: //*[@id="sdp-price-chart-price-change"]
                change_element = tree.xpath('//*[@id="sdp-price-chart-price-change"]')
                if change_element:
                    change_text = change_element[0].text_content().strip()
                    print(f"Raw change text: {change_text}")
                    
                    # Extract regular hours change
                    # Try to find patterns like "+$25.36 (+9.77%) Today"
                    reg_hours_match = re.search(r'([+-]?\$?\d+\.\d+)\s*\(([+-]?\d+\.\d+)%\)\s*Today', change_text)
                    
                    # Extract after hours change
                    # Try to find patterns like "+$0.22 (+0.08%) After-hours"
                    after_hours_match = re.search(r'([+-]?\$?\d+\.\d+)\s*\(([+-]?\d+\.\d+)%\)\s*After-?hours', change_text)
                    
                    # Process matches to get change text
                    if reg_hours_match and after_hours_match:
                        # We have both regular and after-hours changes
                        reg_change = reg_hours_match.group(1)
                        reg_percent = reg_hours_match.group(2)
                        reg_change_str = f"{reg_change} ({reg_percent}%) Today"
                        
                        aft_change = after_hours_match.group(1)
                        aft_percent = after_hours_match.group(2)
                        aft_change_str = f"{aft_change} ({aft_percent}%) After-hours"
                        
                        stock_data['change'] = f"{reg_change_str} | {aft_change_str}"
                        
                        # Also set market status to After Hours
                        stock_data['market_status'] = "After Hours"
                    elif reg_hours_match:
                        # Only regular hours change
                        reg_change = reg_hours_match.group(1)
                        reg_percent = reg_hours_match.group(2)
                        stock_data['change'] = f"{reg_change} ({reg_percent}%)"
                        
                        # Check if market is still open
                        if "closed" in change_text.lower():
                            stock_data['market_status'] = "Market Closed"
                        else:
                            stock_data['market_status'] = "Market Open"
                    elif "pre-market" in change_text.lower():
                        # Pre-market
                        pre_match = re.search(r'([+-]?\$?\d+\.\d+)\s*\(([+-]?\d+\.\d+)%\)', change_text)
                        if pre_match:
                            stock_data['change'] = f"{pre_match.group(1)} ({pre_match.group(2)}%) Pre-market"
                            stock_data['market_status'] = "Pre-market"
                    else:
                        # Try a more general pattern
                        general_match = re.search(r'([+-]?\$?\d+\.\d+)\s*\(([+-]?\d+\.\d+)%\)', change_text)
                        if general_match:
                            stock_data['change'] = f"{general_match.group(1)} ({general_match.group(2)}%)"
                            
                            # Try to determine market status from text
                            if "after" in change_text.lower() or "extended" in change_text.lower():
                                stock_data['market_status'] = "After Hours"
                            elif "pre" in change_text.lower():
                                stock_data['market_status'] = "Pre-market"
                            elif "open" in change_text.lower():
                                stock_data['market_status'] = "Market Open"
                            elif "closed" in change_text.lower():
                                stock_data['market_status'] = "Market Closed"
                    
                    print(f"Extracted change from HTML: {stock_data['change']}")
                    print(f"Determined market status from HTML: {stock_data['market_status']}")
                
                # If we got all the data we need from HTML, return it
                if stock_data['price'] != 'N/A' and stock_data['change'] != 'N/A' and stock_data['market_status'] != 'Unknown':
                    print("Successfully extracted all data from HTML")
                    stock_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    return stock_data
                
            except Exception as e:
                print(f"Error extracting data from HTML elements: {str(e)}")
            
            # APPROACH 2: Extract from embedded JSON (if HTML extraction failed)
            if stock_data['price'] == 'N/A' or stock_data['change'] == 'N/A' or stock_data['market_status'] == 'Unknown':
                print("Approach 2: Extracting from embedded JSON data...")
                
                # Look for the script tag containing the JSON data
                json_data = None
                script_elements = soup.find_all('script')
                for script in script_elements:
                    script_content = script.string if script.string else ""
                    if script_content and script_content.strip().startswith('{"props":'):
                        try:
                            json_data = json.loads(script_content)
                            print("Found embedded JSON data")
                            break
                        except json.JSONDecodeError:
                            continue
                
                if json_data and "props" in json_data and "pageProps" in json_data["props"]:
                    page_props = json_data["props"]["pageProps"]
                    
                    # Extract quote data (contains price info)
                    if "quote" in page_props:
                        quote = page_props["quote"]
                        print(f"Found quote data for {ticker}")
                        
                        # Extract price
                        # Prioritize extended hours price if available
                        if "last_extended_hours_trade_price" in quote and quote["last_extended_hours_trade_price"]:
                            current_price = float(quote["last_extended_hours_trade_price"])
                            price_source = "extended hours"
                            is_extended_hours = True
                        elif "last_trade_price" in quote:
                            current_price = float(quote["last_trade_price"])
                            price_source = "regular hours"
                            is_extended_hours = False
                        else:
                            # Fallback to ask/bid midpoint if available
                            if "ask_price" in quote and "bid_price" in quote:
                                ask = float(quote["ask_price"])
                                bid = float(quote["bid_price"])
                                current_price = (ask + bid) / 2
                                price_source = "bid-ask midpoint"
                                is_extended_hours = False
                            else:
                                current_price = None
                                price_source = None
                                is_extended_hours = False
                        
                        if current_price:
                            # Format price with $ and 2 decimal places
                            stock_data['price'] = f"${current_price:.2f}"
                            print(f"Extracted price from JSON ({price_source}): {stock_data['price']}")
                            
                            # Calculate price change - with special handling for extended hours
                            if "previous_close" in quote:
                                previous_close = float(quote["previous_close"])
                                regular_hours_change = 0
                                extended_hours_change = 0
                                
                                # If we have both regular and extended hours prices
                                if "last_trade_price" in quote and "last_extended_hours_trade_price" in quote and quote["last_extended_hours_trade_price"]:
                                    regular_price = float(quote["last_trade_price"])
                                    extended_price = float(quote["last_extended_hours_trade_price"])
                                    
                                    # Regular hours change (from previous close to regular hours price)
                                    regular_hours_change = regular_price - previous_close
                                    regular_hours_percent = (regular_hours_change / previous_close) * 100
                                    
                                    # Extended hours change (from regular close to extended hours price)
                                    extended_hours_change = extended_price - regular_price
                                    extended_hours_percent = (extended_hours_change / regular_price) * 100
                                    
                                    # For display, use the appropriate change based on current market status
                                    if is_extended_hours:
                                        # We're in extended hours, so show both changes
                                        regular_change_str = f"{'+' if regular_hours_change >= 0 else ''}{regular_hours_change:.2f} ({'+' if regular_hours_change >= 0 else ''}{regular_hours_percent:.2f}%) Today"
                                        extended_change_str = f"{'+' if extended_hours_change >= 0 else ''}{extended_hours_change:.2f} ({'+' if extended_hours_change >= 0 else ''}{extended_hours_percent:.2f}%) After-hours"
                                        stock_data['change'] = f"{regular_change_str} | {extended_change_str}"
                                        
                                        # Set market status to After Hours if we're using extended hours price
                                        stock_data['market_status'] = "After Hours"
                                    else:
                                        # Regular market hours, just show today's change
                                        stock_data['change'] = f"{'+' if regular_hours_change >= 0 else ''}{regular_hours_change:.2f} ({'+' if regular_hours_change >= 0 else ''}{regular_hours_percent:.2f}%)"
                                        stock_data['market_status'] = "Market Open"
                                else:
                                    # We only have one price, calculate simple change
                                    change_amount = current_price - previous_close
                                    change_percent = (change_amount / previous_close) * 100
                                    stock_data['change'] = f"{'+' if change_amount >= 0 else ''}{change_amount:.2f} ({'+' if change_amount >= 0 else ''}{change_percent:.2f}%)"
                                    
                                    # Set a default market status based on whether we have extended hours
                                    stock_data['market_status'] = "After Hours" if is_extended_hours else "Market Closed"
                                
                                print(f"Calculated price change from JSON: {stock_data['change']}")
                                print(f"Determined market status: {stock_data['market_status']}")
                        
                        # Check for trading halted
                        if "trading_halted" in quote and quote["trading_halted"]:
                            stock_data['market_status'] = "Trading Halted"
                            print("Trading is halted for this stock")
                        
                        # If we got everything we need, return the data
                        if stock_data['price'] != 'N/A' and stock_data['change'] != 'N/A' and stock_data['market_status'] != 'Unknown':
                            print("Successfully extracted all data from JSON")
                            stock_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            return stock_data
            
            # APPROACH 3: Use Robinhood API as fallback
            if stock_data['price'] == 'N/A' or stock_data['change'] == 'N/A' or stock_data['market_status'] == 'Unknown':
                print("Approach 3: Using Robinhood API as fallback...")
                
                api_url = f"https://api.robinhood.com/instruments/?symbol={ticker}"
                response = requests.get(api_url, headers=headers, timeout=10)
        
                if response.status_code == 200:
                    instrument_data = response.json()
                    if instrument_data.get('results') and len(instrument_data['results']) > 0:
                        instrument_id = instrument_data['results'][0]['id']
                        print(f"Found instrument ID: {instrument_id}")
        
                        # Get quote data
                        quote_url = f"https://api.robinhood.com/marketdata/quotes/{instrument_id}/"
                        quote_response = requests.get(quote_url, headers=headers, timeout=10)
        
                        if quote_response.status_code == 200:
                            quote_data = quote_response.json()
                            print(f"Quote data: {json.dumps(quote_data, indent=2)}")
        
                            # Extract price if still needed
                            if stock_data['price'] == 'N/A':
                                # Prioritize extended hours price over last trade price
                                if 'last_extended_hours_trade_price' in quote_data and quote_data['last_extended_hours_trade_price'] != 'null':
                                    price = f"${float(quote_data['last_extended_hours_trade_price']):.2f}"
                                    print(f"Using extended hours price from API: {price}")
                                    using_extended_hours = True
                                elif 'last_trade_price' in quote_data:
                                    price = f"${float(quote_data['last_trade_price']):.2f}"
                                    print(f"Using last trade price from API: {price}")
                                    using_extended_hours = False
                                else:
                                    # Fallback to ask/bid as estimate
                                    if 'ask_price' in quote_data and 'bid_price' in quote_data:
                                        ask = float(quote_data['ask_price'])
                                        bid = float(quote_data['bid_price'])
                                        price = f"${((ask + bid) / 2):.2f}"
                                        print(f"Using bid-ask midpoint from API: {price}")
                                        using_extended_hours = False
                                    else:
                                        price = 'N/A'
                                        using_extended_hours = False
                                
                                stock_data['price'] = price
        
                            # Calculate change if still needed
                            if stock_data['change'] == 'N/A' and stock_data['price'] != 'N/A' and 'previous_close' in quote_data:
                                # Try to get both regular and extended hours prices
                                has_extended = ('last_extended_hours_trade_price' in quote_data and 
                                               quote_data['last_extended_hours_trade_price'] != 'null')
                                has_regular = 'last_trade_price' in quote_data
                                
                                if has_extended and has_regular:
                                    # We have both prices, calculate both changes
                                    regular_price = float(quote_data['last_trade_price'])
                                    extended_price = float(quote_data['last_extended_hours_trade_price'])
                                    previous_close = float(quote_data['previous_close'])
                                    
                                    # Regular hours change
                                    reg_change = regular_price - previous_close
                                    reg_percent = (reg_change / previous_close) * 100
                                    reg_change_str = f"{'+' if reg_change >= 0 else ''}{reg_change:.2f} ({'+' if reg_change >= 0 else ''}{reg_percent:.2f}%) Today"
                                    
                                    # Extended hours change
                                    ext_change = extended_price - regular_price
                                    ext_percent = (ext_change / regular_price) * 100
                                    ext_change_str = f"{'+' if ext_change >= 0 else ''}{ext_change:.2f} ({'+' if ext_change >= 0 else ''}{ext_percent:.2f}%) After-hours"
                                    
                                    # Combine both changes if we're in extended hours
                                    if using_extended_hours:
                                        stock_data['change'] = f"{reg_change_str} | {ext_change_str}"
                                        stock_data['market_status'] = "After Hours"
                                    else:
                                        stock_data['change'] = reg_change_str
                                        stock_data['market_status'] = "Market Open"
                                else:
                                    # Simple change calculation
                                    current_price = float(stock_data['price'].replace('$', ''))
                                    previous_close = float(quote_data['previous_close'])
                                    change_amount = current_price - previous_close
                                    change_percent = (change_amount / previous_close) * 100
                                    stock_data['change'] = f"{'+' if change_amount >= 0 else ''}{change_amount:.2f} ({'+' if change_amount >= 0 else ''}{change_percent:.2f}%)"
                                    
                                    # Set market status based on time if not already set
                                    if stock_data['market_status'] == 'Unknown':
                                        stock_data['market_status'] = "After Hours" if using_extended_hours else "Market Closed"
                                
                                print(f"Calculated price change from API: {stock_data['change']}")
                                print(f"Determined market status from API: {stock_data['market_status']}")

    except Exception as e:
        print(f"Error scraping data for {ticker}: {str(e)}")

    # Update the last_updated timestamp
    stock_data['last_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return stock_data

def test_scraper(ticker):
    """Test the scraper for a given ticker"""
    print(f"Testing scraper for {ticker}...")
    result = scrape_stock_data(ticker)
    print(f"Final result for {ticker}:")
    print(f"  Price: {result['price']}")
    print(f"  Change: {result['change']}")
    print(f"  Market Status: {result['market_status']}")
    print(f"  Last Updated: {result['last_updated']}")
    return result

if __name__ == "__main__":
    # Test with multiple tickers
    tickers = ["TSLA", "AAPL", "MSFT", "AMZN", "GOOGL"]
    print(f"Testing scraper with {len(tickers)} tickers...")
    
    results = {}
    for ticker in tickers:
        print(f"\n{'-' * 50}")
        result = test_scraper(ticker)
        results[ticker] = result
        print(f"{'-' * 50}")
    
    # Summary of results
    print("\nSUMMARY OF RESULTS:")
    print(f"{'Ticker':<6} | {'Price':<10} | {'Change':<20} | {'Market Status':<15}")
    print("-" * 55)
    for ticker, data in results.items():
        print(f"{ticker:<6} | {data['price']:<10} | {data['change']:<20} | {data['market_status']:<15}")
    
    print("\nAll tests completed successfully!") 