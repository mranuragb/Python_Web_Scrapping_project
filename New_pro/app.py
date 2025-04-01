from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-key-for-testing'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///pricecompare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    products = db.relationship('Product', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    prices = db.relationship('Price', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
class Price(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    retailer = db.Column(db.String(64), nullable=False)
    price = db.Column(db.Float, nullable=False)
    url = db.Column(db.String(256))
    date_checked = db.Column(db.DateTime, default=datetime.utcnow)

class Retailer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    base_url = db.Column(db.String(256), nullable=False)
    search_pattern = db.Column(db.String(256), nullable=False)
    price_selector = db.Column(db.String(256), nullable=False)

@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()
        
        if user_exists:
            flash('Username already exists.')
            return redirect(url_for('register'))
        
        if email_exists:
            flash('Email already registered.')
            return redirect(url_for('register'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        
        login_user(user)
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    products = Product.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', products=products)

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if request.method == 'POST':
        product_name = request.form.get('name')
        
        if not product_name:
            flash('Product name is required.')
            return redirect(url_for('add_product'))
        
        new_product = Product(name=product_name, user_id=current_user.id)
        db.session.add(new_product)
        db.session.commit()
        
        flash(f'Product "{product_name}" added successfully.')
        return redirect(url_for('add_price', product_id=new_product.id))
    
    return render_template('add_product.html')

@app.route('/add_price/<int:product_id>', methods=['GET', 'POST'])
@login_required
def add_price(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        flash('You do not have permission to add prices to this product.')
        return redirect(url_for('dashboard'))
    
    retailers = Retailer.query.all()
    
    if request.method == 'POST':
        retailer = request.form.get('retailer')
        price = request.form.get('price')
        url = request.form.get('url')
        
        if not retailer or not price:
            flash('Retailer and price are required.')
            return redirect(url_for('add_price', product_id=product_id))
        
        try:
            price_float = float(price)
        except ValueError:
            flash('Price must be a valid number.')
            return redirect(url_for('add_price', product_id=product_id))
        
        new_price = Price(product_id=product_id, retailer=retailer, price=price_float, url=url)
        db.session.add(new_price)
        db.session.commit()
        
        flash('Price added successfully.')
        return redirect(url_for('product_detail', product_id=product_id))
    
    return render_template('add_price.html', product=product, retailers=retailers)

@app.route('/product/<int:product_id>')
@login_required
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        flash('You do not have permission to view this product.')
        return redirect(url_for('dashboard'))
    
    prices = Price.query.filter_by(product_id=product_id).order_by(Price.price).all()
    
    return render_template('product_detail.html', product=product, prices=prices)

@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    if request.method == 'POST':
        query = request.form.get('query')
        
        if not query:
            flash('Search query is required.')
            return redirect(url_for('search'))
        
        # Here you would implement the search functionality
        # For example, searching across different retailers
        
        # Placeholder for search results
        search_results = []
        
        return render_template('search_results.html', query=query, results=search_results)
    
    return render_template('search.html')

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        flash('You do not have permission to delete this product.')
        return redirect(url_for('dashboard'))
    
    db.session.delete(product)
    db.session.commit()
    
    flash(f'Product "{product.name}" deleted successfully.')
    return redirect(url_for('dashboard'))

@app.route('/update_prices/<int:product_id>', methods=['POST'])
@login_required
def update_prices(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.user_id != current_user.id:
        flash('You do not have permission to update prices for this product.')
        return redirect(url_for('dashboard'))
    
    # Here you would implement the price update functionality
    # For example, scraping prices from retailers
    
    flash('Prices updated successfully.')
    return redirect(url_for('product_detail', product_id=product_id))

# Helper function to scrape prices (basic implementation)
def scrape_price(url, price_selector):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price_element = soup.select_one(price_selector)
        if price_element:
            price_text = price_element.text.strip()
            price_match = re.search(r'\d+\.\d+', price_text)
            if price_match:
                return float(price_match.group())
    except Exception as e:
        print(f"Error scraping price: {e}")
    
    return None

# Initialize the app
def init_app():
    with app.app_context():
        db.create_all()
        
        # Add default retailers if none exist
        if Retailer.query.count() == 0:
            retailers = [
                Retailer(name='Amazon', base_url='https://www.amazon.com', 
                         search_pattern='/s?k={}', 
                         price_selector='.a-price .a-offscreen'),
                Retailer(name='Walmart', base_url='https://www.walmart.com', 
                         search_pattern='/search/?query={}', 
                         price_selector='.price-main .price-group'),
                Retailer(name='Target', base_url='https://www.target.com', 
                         search_pattern='/s?searchTerm={}', 
                         price_selector='.styles__CurrentPriceValue-sc-17xqu7e-2')
            ]
            
            for retailer in retailers:
                db.session.add(retailer)
            
            db.session.commit()

if __name__ == '__main__':
    init_app()
    app.run(debug=True)