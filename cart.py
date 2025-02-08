from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import get_jwt_identity, jwt_required
from http_status_code import *
import os
 
from models import User, Product, Cart, CartItem
from models import db

import uuid

cart_bp = Blueprint('cart', __name__, url_prefix='/api/cart')

@cart_bp.post('/add')
@jwt_required(optional=True)
def add_to_cart():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    if not product_id:
        return jsonify({'error': 'Product ID is required'}), 400

    product = Product.query.get(product_id)
    if not product:
        return jsonify({'error': 'Product not found'}), 404

    if quantity > product.quantity:
        return jsonify({'error': 'Not enough stock'}), 400

    # Check if the user is authenticated using Flask-JWT
    current_user = get_jwt_identity()  # Returns None if the user is not authenticated
    current_user = User.query.filter_by(email=current_user).first()

    if current_user:
        # Authenticated user: use their user_id
        cart = Cart.query.filter_by(user_id=current_user.id).first()
    else:
        # Non-authenticated user: use session_id
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        session_id = session['session_id']
        cart = Cart.query.filter_by(session_id=session_id).first()

    # If no cart exists, create one
    if not cart:
        if current_user:
            cart = Cart(user_id=current_user.id, session_id=session.get('session_id'))
        else:
            cart = Cart(session_id=session.get('session_id'))
        db.session.add(cart)
        db.session.commit()

    # Check if the product is already in the cart
    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)

    # Update the total price of the cart
    cart.total_price += product.price * quantity

    db.session.commit()

    return jsonify({'detail': 'Product added to cart', 'cart_id': cart.id}), 200

@cart_bp.post('/merge-carts')
@jwt_required()  # Only authenticated users can access this endpoint
def merge_carts():
    current_user = get_jwt_identity()
    current_user = User.query.filter_by(email=current_user).first()

    # Get the session_id from the session (if it exists)
    session_id = session.get('session_id')

    if not session_id:
        return jsonify({'detail': 'No session cart to merge'}), 200

    # Get the session cart and user cart
    session_cart = Cart.query.filter_by(session_id=session_id).first()
    user_cart = Cart.query.filter_by(user_id=current_user.id).first()

    if not session_cart:
        return jsonify({'detail': 'No session cart to merge'}), 200

    if not user_cart:
        # If the user doesn't have a cart, assign the session cart to the user
        session_cart.user_id = current_user.id
        session_cart.session_id = None
        db.session.commit()
        return jsonify({'message': 'Cart merged successfully'}), 200

    # Merge items from session cart to user cart
    for session_item in session_cart.items:
        user_item = CartItem.query.filter_by(cart_id=user_cart.id, product_id=session_item.product_id).first()
        if user_item:
            user_item.quantity += session_item.quantity
        else:
            user_item = CartItem(cart_id=user_cart.id, product_id=session_item.product_id, quantity=session_item.quantity)
            db.session.add(user_item)

    # Update the total price of the user cart
    user_cart.total_price += session_cart.total_price

    # Delete the session cart
    db.session.delete(session_cart)
    db.session.commit()

    return jsonify({'message': 'Cart merged successfully'}), 200

@cart_bp.delete('/remove/<int:product_id>')
@jwt_required(optional=True)
def remove_from_cart(product_id):
    current_user = get_jwt_identity()
    current_user = User.query.filter_by(email=current_user).first()

    if current_user is None:
        session_id = session.get('session_id', '')
        cart = Cart.query.filter_by(session_id=session_id).first_or_404()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first_or_404()
        item_quantity = item.quantity
        if item_quantity - 1 == 0:
            cart.total_price -= item.product.price
            db.session.delete(item)
        else:
            item.quantity -= 1
            cart.total_price -= item.product.price
    else:
        cart = Cart.query.filter_by(user_id=current_user.id).first_or_404()
        item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first_or_404()
        item_quantity = item.quantity
        if item_quantity - 1 == 0:
            cart.total_price -= item.product.price
            db.session.delete(item)
        else:
            cart.total_price -= item.product.price
            item.quantity -= 1
    db.session.commit()
    return jsonify({'detail': 'Removed from cart'}), 200


@cart_bp.get('/view-cart')
@jwt_required(optional=True)
def view_cart():
    current_user = get_jwt_identity()
    user = User.query.filter_by(email=current_user).first()

    if current_user:
        cart = Cart.query.filter_by(user_id=user.id).first_or_404()
    else:
        # Non-authenticated user: use session_id
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        session_id = session['session_id']
        cart = Cart.query.filter_by(session_id=session_id).first_or_404()
    
    cart_items = CartItem.query.filter_by(cart_id=cart.id).all()
    cart_items_serializer = [
        {
            'product_id': item.product_id,
            'product_name': item.product.name,
            'quantity': item.product.quantity,
            'price': item.product.price,
            'avg_rating': item.product.avg_rating,
        } for item in cart_items
    ]

    return jsonify({
        'cart_id': cart.id,
        'total_price': cart.total_price,
        'cart_items': cart_items_serializer if cart_items_serializer else "Your cart is empty."
    })
