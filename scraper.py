import os
import requests
import re
import json
import time
from bs4 import BeautifulSoup
from datetime import datetime

def scrape_stock_data(ticker):
    """Scrape stock data from Robinhood for a given ticker"""
    url = f"https://robinhood.com/us/en/stocks/{ticker}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://robinhood.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }

    try:
        print(f"Scraping data for {ticker} from {url}")

        # Try a more direct API approach first
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

                    # Extract price - prioritize extended hours price over last trade price
                    price = 'N/A'
                    using_extended_hours = False
                    
                    # Use extended hours price if available, otherwise use last trade price
                    if 'last_extended_hours_trade_price' in quote_data and quote_data['last_extended_hours_trade_price'] != 'null':
                        price = f"${float(quote_data['last_extended_hours_trade_price']):.2f}"
                        print(f"Using extended hours price: {price}")
                        using_extended_hours = True
                    elif 'last_trade_price' in quote_data:
                        price = f"${float(quote_data['last_trade_price']):.2f}"
                        print(f"Using last trade price: {price}")
                    
                    # If no prices are available, try to use ask/bid as estimate
                    if price == 'N/A' and 'ask_price' in quote_data and 'bid_price' in quote_data:
                        ask = float(quote_data['ask_price'])
                        bid = float(quote_data['bid_price'])
                        # Use midpoint between bid and ask
                        price = f"${((ask + bid) / 2):.2f}"
                        print(f"Using bid-ask midpoint: {price}")

                    # IMPORTANT: Calculate change relative to last_trade_price (regular market close)
                    # This matches how Robinhood calculates change for pre-market/after-hours
                    if price != 'N/A' and 'last_trade_price' in quote_data:
                        last_trade_price = float(quote_data['last_trade_price'])
                        current_price = float(price.replace('$', ''))
                        change_amount = current_price - last_trade_price
                        change_percent = (change_amount / last_trade_price) * 100
                        change = f"{'+' if change_amount >= 0 else ''}{change_amount:.2f} ({'+' if change_amount >= 0 else ''}{change_percent:.2f}%)"
                    else:
                        change = "N/A"

                    # Check if market is open, or pre/after hours
                    market_status = "Market Closed"
                    
                    # If we're using extended hours price, it's either pre-market or after-hours
                    if using_extended_hours:
                        # Check current time to determine if it's pre-market or after-hours
                        now = datetime.now()
                        market_hour = now.hour
                        if market_hour < 9 or (market_hour == 9 and now.minute < 30):
                            market_status = "Pre-market"
                        else:
                            market_status = "After Hours"
                    # Otherwise, if trading is not halted during market hours, market is open
                    elif quote_data.get('trading_halted') is False:
                        # Check if within normal market hours (9:30 AM - 4:00 PM EST)
                        now = datetime.now()
                        market_hour = now.hour
                        if (market_hour > 9 or (market_hour == 9 and now.minute >= 30)) and market_hour < 16:
                            market_status = "Market Open"

                    return {
                        'ticker': ticker,
                        'price': price,
                        'change': change,
                        'market_status': market_status,
                        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

        # Fallback to the website scraping approach
        response = requests.get(url, headers=headers, timeout=15)
        print(f"Response status code: {response.status_code}")

        if response.status_code == 200:
            # Try to extract data from the HTML using regex
            html_content = response.text

            # Look for price data in JSON embedded in the page
            json_matches = re.findall(r'{"symbol":"' + ticker + r'".+?"last_trade_price":"([^"]+)"', html_content)
            if json_matches:
                price = f"${float(json_matches[0]):.2f}"
                print(f"Found price in JSON: {price}")

                # Try to find change information
                change_matches = re.findall(r'"previous_close":"([^"]+)"', html_content)
                if change_matches:
                    previous_close = float(change_matches[0])
                    current_price = float(json_matches[0])
                    change_amount = current_price - previous_close
                    change_percent = (change_amount / previous_close) * 100
                    change = f"{'+' if change_amount >= 0 else ''}{change_amount:.2f} ({'+' if change_amount >= 0 else ''}{change_percent:.2f}%)"
                    print(f"Calculated change: {change}")
                else:
                    change = "N/A"

                # Try to find market status
                if "Market Open" in html_content:
                    market_status = "Market Open"
                elif "After Hours" in html_content:
                    market_status = "After Hours"
                elif "Pre-market" in html_content:
                    market_status = "Pre-market"
                else:
                    market_status = "Market Closed"

                return {
                    'ticker': ticker,
                    'price': price,
                    'change': change,
                    'market_status': market_status,
                    'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

            # As a last resort, try to scrape the values from fixed positions in the markup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract any text that might contain a price ($ followed by numbers)
            all_text = soup.get_text()
            price_pattern = r'\$\d+\.\d+'
            price_matches = re.findall(price_pattern, all_text)

            if price_matches:
                price = price_matches[0]
                # Try to find text near the price that might be change information
                change = "N/A"
                market_status = "Unknown"

                return {
                    'ticker': ticker,
                    'price': price,
                    'change': change,
                    'market_status': market_status,
                    'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

    except Exception as e:
        print(f"Error scraping data for {ticker}: {str(e)}")

    return {
        'ticker': ticker,
        'price': 'N/A',
        'change': 'N/A',
        'market_status': 'Error',
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def test_scraper(ticker):
    """Test the scraper with direct API approach for a given ticker"""
    url = f"https://robinhood.com/stocks/{ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://robinhood.com/',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
    }

    print(f"Scraping data for {ticker} from API...")

    # Try a more direct API approach first
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
                print(f"API quote data: {quote_data}")

                # Extract price - prioritize extended hours price if available
                price = 'N/A'
                
                # Check for extended hours price
                if quote_data.get('last_extended_hours_trade_price') and quote_data['last_extended_hours_trade_price'] != 'null':
                    price = f"${float(quote_data['last_extended_hours_trade_price']):.2f}"
                    price_source = "extended hours"
                # Fall back to last trade price if no extended hours price
                elif quote_data.get('last_trade_price'):
                    price = f"${float(quote_data['last_trade_price']):.2f}"
                    price_source = "last trade (previous close)"
                
                # If neither is available, try to use ask/bid as estimate
                if price == 'N/A' and quote_data.get('ask_price') and quote_data.get('bid_price'):
                    ask = float(quote_data['ask_price'])
                    bid = float(quote_data['bid_price'])
                    price = f"${((ask + bid) / 2):.2f}"
                    price_source = "bid-ask midpoint"
                
                print(f"Using {price_source} price: {price}")

                # IMPORTANT CHANGE: Calculate change between current price and last_trade_price (yesterday's close)
                # This matches what Robinhood displays in the UI
                if price != 'N/A' and quote_data.get('last_trade_price'):
                    last_trade_price = float(quote_data['last_trade_price'])
                    current_price = float(price.replace('$', ''))
                    change_amount = current_price - last_trade_price
                    change_percent = (change_amount / last_trade_price) * 100
                    change = f"{'+' if change_amount >= 0 else ''}{change_amount:.2f} ({'+' if change_amount >= 0 else ''}{change_percent:.2f}%)"
                else:
                    change = "N/A"

                print(f"Final result: {ticker}: {price} {change}")
                
                # Also show what we were calculating before for comparison
                if price != 'N/A' and quote_data.get('previous_close'):
                    previous_close = float(quote_data['previous_close'])
                    current_price = float(price.replace('$', ''))
                    old_change_amount = current_price - previous_close
                    old_change_percent = (old_change_amount / previous_close) * 100
                    old_change = f"{'+' if old_change_amount >= 0 else ''}{old_change_amount:.2f} ({'+' if old_change_amount >= 0 else ''}{old_change_percent:.2f}%)"
                    print(f"Change vs previous_close: {old_change}")
                
                return

    print("API approach failed, trying scraping approach...")

    # Fallback to the website scraping approach
    response = requests.get(url, headers=headers, timeout=15)
    print(f"Website response status code: {response.status_code}")

    if response.status_code == 200:
        # Try to extract data from the HTML using regex
        html_content = response.text

        # Look for price data in JSON embedded in the page
        json_matches = re.findall(r'{"symbol":"' + ticker + r'".+?"last_trade_price":"([^"]+)"', html_content)
        if json_matches:
            price = f"${float(json_matches[0]):.2f}"
            print(f"Found price from JSON: {price}")

            # Try to find change information
            change_matches = re.findall(r'"previous_close":"([^"]+)"', html_content)
            if change_matches:
                previous_close = float(change_matches[0])
                current_price = float(json_matches[0])
                change_amount = current_price - previous_close
                change_percent = (change_amount / previous_close) * 100
                change = f"{'+' if change_amount >= 0 else ''}{change_amount:.2f} ({'+' if change_amount >= 0 else ''}{change_percent:.2f}%)"
                print(f"Calculated change: {change}")
            else:
                change = "N/A"
                print("Could not find previous close data")

            print(f"Final result: {ticker}: {price} {change}")
            return

        # As a last resort, try to scrape the values from fixed positions in the markup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Extract any text that might contain a price ($ followed by numbers)
        all_text = soup.get_text()
        price_pattern = r'\$\d+\.\d+'
        price_matches = re.findall(price_pattern, all_text)

        if price_matches:
            price = price_matches[0]
            print(f"Found price from text: {price}")
            print(f"Final result: {ticker}: {price} Change: N/A")
            return

    print(f"Could not scrape data for {ticker}")

if __name__ == "__main__":
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "SPY"]
    for ticker in tickers:
        test_scraper(ticker)
        print("-" * 50) 