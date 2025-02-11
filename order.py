import paypalrestsdk
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from http_status_code import *

from utils import get_user_and_session_id, send_email, check_if_user_is_admin

import os

from models import Cart, CartItem, db, Order, OrderItem, PaymentStatus

# PayPal SDK configuration
paypalrestsdk.configure({
    "mode": os.getenv('PAYMENT_MODE'),  # Use "live" for production
    "client_id": os.getenv('PAYPAL_CLIENT_ID'),
    "client_secret": os.getenv('PAYPAL_SECRET_KEY')
})

order_bp = Blueprint('order', __name__, url_prefix='/api/order')

@order_bp.post('/create-payment')
@jwt_required(optional=True)
def create_payment():
    data = request.json

    email = get_jwt_identity()
    user, session_id = get_user_and_session_id(email)

    cart = Cart.query.filter_by(user_id=user.id).first() if email else Cart.query.filter_by(session_id=session_id).first()

    cart_items = CartItem(cart_id=cart.id)

    if not cart:
        return jsonify({'detail': 'Your cart is empty!'}), HTTP_400_BAD_REQUEST
    
    amount = cart.total_price if user else cart.total_price
    currency = 'USD'

    order = Order(full_name=data['full_name'], street=data['street'],
                  city=data['city'], state=data['state'], zip_code=data['zip_code'],
                  country=data['country'], phone_number=data['phone_number'], 
                  email=data['email'] if data['email'] else user.email,
                  user_id=user.id if email else None,
                  session_id=session_id if not email else None,  
                  total_price=cart.total_price, 
                  order_number=None)
    
    db.session.add(order)
    db.session.commit()


    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "transactions": [{
            "amount": {
                "total": str(amount),
                "currency": currency
            },
            "description": "Payment for products in your cart."
        }],
        "redirect_urls": {
            "return_url": "http://localhost:5000/api/order/execute-payment/" + order.order_number,  # Replace with your frontend URL
            "cancel_url": "http://localhost:5000/api/order/cancel-payment/" + order.order_number  # Replace with your frontend URL
        }
    })

    if payment.create():
        # Redirect the user to PayPal for payment approval
        for link in payment.links:
            if link.method == "REDIRECT":
                redirect_url = link.href
                return jsonify({"redirect_url": redirect_url})
    else:
        return jsonify({"error": payment.error}), 400
    

@order_bp.get('/execute-payment/<string:order_number>')
@jwt_required(optional=True)
def execute_payment(order_number):
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')

    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        return jsonify({"message": "Payment successful!", "payment_id": payment.id, "order_number": order_number})
    else:
        return jsonify({"error": payment.error}), 400
    

@order_bp.get('/after-payment/<string:order_number>')
@jwt_required(optional=True)
def after_payment(order_number):
    email = get_jwt_identity()

    user, session_id = get_user_and_session_id(email)

    order = Order.query.filter_by(order_number=order_number).first_or_404()
    if order.payment_status == PaymentStatus.PAID:
        return jsonify({'detail': 'order already paid'})
    cart = Cart.query.filter_by(user_id=user.id).first() if email else Cart.query.filter_by(session_id=session_id).first()
    cart_items = CartItem.query.filter_by(cart_id=cart.id)
    for item in cart_items:
        order_item = OrderItem(
            name=item.product.name,
            order_id=order.id,
            product_id=item.product.id,
            quantity=item.quantity,
            price=item.product.price * item.quantity 
        )
        item.product.quantity -= item.quantity 
        cart.total_price -= item.product.price * item.quantity 
        db.session.add(order_item)
        db.session.delete(item)
    order.payment_status = PaymentStatus.PAID
    send_email(to=order.email, subject="Order", body=f'Your order is being processed we will update you on it. your order number is {order_number}')
    db.session.commit()
    return jsonify({'detail': 'payment successfull'})


@order_bp.get('/cancel-payment/<string:order_number>')
@jwt_required(optional=True)
def cancel_payment(order_number):
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    db.session.delete(order)
    db.session.commit()
    return jsonify({"message": "Payment cancelled by user."}), 200

@order_bp.patch('/update-order/<string:order_number>')
@jwt_required()
def update_order(order_number):
    email = get_jwt_identity()
    data = request.json
    order = Order.query.filter_by(order_number=order_number).first_or_404()
    is_admin = check_if_user_is_admin(email)
    if is_admin:
        if 'order_status' in data:
            order.order_status = data['order_status']
            send_email(to=order.email, subject='Update on order', body=f'Your order is being {order.order_status}.\norder number: {order.order_number}')
            return jsonify({'detail': 'Order updated'})

    return jsonify({'detail': 'You dont have permission to perform this command.'}), HTTP_403_FORBIDDEN


@order_bp.get('/all-orders')
@jwt_required()
def get_all_orders():
    email = get_jwt_identity()
    is_admin = check_if_user_is_admin(email)
    if is_admin:
        orders = Order.query.all()
        orders_list = [
    {
        "id": order.id,
        "full_name": order.full_name,
        "street": order.street,
        "city": order.city,
        "state": order.state,
        "zip_code": order.zip_code,
        "country": order.country,
        "phone_number": order.phone_number,
        "payment_status": order.payment_status.value,
        "order_status": order.order_status.value,
        "total_price": float(order.total_price),  # Convert Decimal to float for JSON serialization
        "order_number": order.order_number,
        "email": order.email,
        "purchaes": [
            {
                "name": order_item.name,
                "quantity": order_item.quantity,
                "price": float(order_item.price), 
                "product_id": order_item.product_id
        } for order_item in OrderItem.query.filter_by(order_id=order.id)
        ]
    }
    for order in orders
        ]
        return jsonify({'orders_list': orders_list}), 200
    
    return jsonify({'detail': 'You dont have permission to perform this command.'}), HTTP_403_FORBIDDEN