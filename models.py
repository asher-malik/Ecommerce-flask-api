from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from slugify import slugify 
from sqlalchemy.orm import validates
from sqlalchemy import func

import enum

import random

db = SQLAlchemy()

class PaymentStatus(enum.Enum):
    PAID = 'PAID'
    UNPAID = 'UNPAID'

class OrderStatus(enum.Enum):
    PROCESSING = 'Processing'
    SHIPPED = 'Shipped'
    DELIVERED = 'Delivered'
    
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(300), nullable=False)
    profile_pic = db.Column(db.String, nullable=False, default='media/profile-pictures/Default-profile.png')  # File path to the image
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow) 
    last_login = db.Column(db.DateTime, nullable=True)
    product_review = db.relationship('ProductReview', backref='user', lazy=True)
    order = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    category_slug = db.Column(db.String(255), nullable=True, default='None')
    brand = db.Column(db.String(50), nullable=True, default='')
    avg_rating = db.Column(db.Numeric(3, 2), nullable=True, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow) 
    images = db.relationship('ProductImage', backref='product', lazy=True)
    product_review = db.relationship('ProductReview', backref='product', lazy=True)
    cart_items = db.relationship('CartItem', backref='product', lazy=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

    @validates('category')
    def generate_category_slug(self, key, value):
        """Automatically generate a slug when the category is updated or created."""
        self.category_slug = slugify(value)
        return value
    
    def calculate_avg_rating(self):
        # Fetch all reviews for this product
        reviews = ProductReview.query.filter_by(product_id=self.id).all()

        if not reviews:
            # If there are no reviews, set avg_rating to 0
            self.avg_rating = 0
        else:
            # Calculate the average rating
            total_ratings = sum(review.rating for review in reviews)
            avg_rating = total_ratings / len(reviews)
            self.avg_rating = round(avg_rating, 2)  # Round to 2 decimal places

        # Save the updated avg_rating to the database
        db.session.commit()

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String, nullable=False)  # Path to the image file
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProductReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    review = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Numeric(3, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)  # For non-authenticated users
    total_price = db.Column(db.Numeric(10, 2), default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to access the items in the cart
    items = db.relationship('CartItem', backref='cart', lazy=True)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('cart.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    street = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(255), nullable=False)
    state = db.Column(db.String(255), nullable=False)
    zip_code = db.Column(db.String(255), nullable=False)
    country = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.String(100), nullable=False)
    payment_status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)  # Payment status (PAID/UNPAID)
    order_status = db.Column(db.Enum(OrderStatus), default=OrderStatus.PROCESSING, nullable=False)  # Order status (Processing/Shipped/Delivered)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)  # Total price of the order
    order_number = db.Column(db.String(100), nullable=True, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=True)
    session_id = db.Column(db.String(255), nullable=True)  # For non-authenticated users

    email = db.Column(db.String(255), unique=False, nullable=False)# For non-authenticated users

    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # When the order was created
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)  # When the order was last updated
    
    items = db.relationship('OrderItem', backref='order', lazy=True)

    @validates('order_number')
    def validate_order_number(self, key, value):
        # If a value is already provided, use it (e.g., during updates)
        if value:
            return value

        # Generate a new order number if none is provided
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d%H%M%S")
        random_number = random.randint(1000, 9999)  # 4-digit random number
        return f"{timestamp}-{random_number}"


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id', ondelete='CASCADE'), nullable=False)  # Link to the Order model
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='SET NULL'), nullable=True)  # Link to the Product model
    quantity = db.Column(db.Integer, nullable=False)  # Quantity of the product
    price = db.Column(db.Numeric(10, 2), nullable=False)  # Price of the product at the time of purchase
