from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import re
import time

app = Flask(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.google.com/',
    'DNT': '1'
}

def scrape_amazon(query):
    url = f'https://www.amazon.in/s?k={query.replace(" ", "+")}'
    products = []
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        
        if response.status_code == 200:
            if "api services support@amazon.com" in response.text:
                print("⚠️ Amazon CAPTCHA Blocked! Try changing IP/User Agent")
                return []
            
            if "503 - Service Unavailable Error" in response.text:
                print("⚠️ Amazon Service Unavailable! Please try again later.")
                return []
            
            if "No results found for your search." in response.text:
                print("No results found on Amazon for this query.")
                return []
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Updated Selector
            items = soup.select('div.s-result-item')
            
            for item in items[:15]:
                try:
                    # Skip sponsored products
                    if item.select_one('span.s-sponsored-label-text'):
                        continue
                    
                    # Updated CSS Selectors
                    title = item.select_one('h2.a-size-mini a span.a-color-base')
                    price = item.select_one('span.a-price span.a-offscreen')
                    link = item.select_one('a.a-link-normal')['href']
                    
                    if all([title, price, link]):
                        products.append({
                            'title': title.get_text(strip=True),
                            'price': re.sub(r'\D', '', price.get_text()),
                            'link': f"https://amazon.in{link.split('?')[0]}"
                        })
                except Exception as e:
                    continue
                    
            # Debugging: Save HTML response
            with open('amazon debug.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
        else:
            print(f"Amazon HTTP Error: {response.status_code}")
            return []
    except Exception as e:
        print(f"Amazon Error: {str(e)}")
    
    return products[:5]
def scrape_flipkart(query):
    url = f'https://www.flipkart.com/search?q={query.replace(" ", "%20")}'
    response = requests.get(url, headers=HEADERS)
    products = []
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'lxml')
        
        # Updated 2024 Flipkart selectors
        items = soup.find_all('div', {'class': 'tUxRFH'})
        
        for item in items:
            try:
                title = item.find('div', class_='KzDlHZ')
                price = item.find('div', class_='Nx9bqj')
                link = item.find('a', href=True)

                if all([title, price, link]):
                    products.append({
                        'title': title.get_text(strip=True),
                        'price': re.sub(r'\D', '', price.get_text()),
                        'link': f"https://flipkart.com{link['href']}"
                    })
            except Exception as e:
                continue
    return products[:5]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form['query']
    
    print(f"\n🔍 Searching for: {query}")
    
    # Amazon with debug
    amazon_products = scrape_amazon(query)
    print(f"Amazon Results: {len(amazon_products)}")
    
    # Flipkart with delay and debug
    time.sleep(1.5)
    flipkart_products = scrape_flipkart(query)
    print(f"Flipkart Results: {len(flipkart_products)}\n")
    
    return render_template('results.html',
                         amazon_products=amazon_products,
                         flipkart_products=flipkart_products,
                         query=query)

if __name__ == '__main__':
    app.run(debug=True)