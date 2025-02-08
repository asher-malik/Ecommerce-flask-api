from flask import Blueprint, request, jsonify, session
from flask_jwt_extended import (create_access_token, 
                                get_jwt_identity, 
                                jwt_required, 
                                get_jwt,
                                create_refresh_token)
from flask_dance.contrib.google import google


from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import validators
from http_status_code import *
from models import User, db, Address
from blacklist import blacklist
from social_logins import google_bp
from utils import generate_token, send_email, confirm_token, ALLOWED_EXTENSIONS, allowed_file

import os
from dotenv import load_dotenv

from datetime import datetime

# Load environment variables from the .env file
load_dotenv()

account = Blueprint('account', __name__, url_prefix='/api/account')


@account.post('/register')
def register():
    username = request.json['username']
    email = request.json['email']
    password = request.json['password']

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), HTTP_400_BAD_REQUEST
    if password.isdigit():
        return jsonify({'error': 'Password is entirely numeric'}), HTTP_400_BAD_REQUEST
    if ' ' in password or ' ' in username:
        return jsonify({'error': 'No spaces'}), HTTP_400_BAD_REQUEST
    
    if not validators.email(email):
        return jsonify({'error': 'Email is not valid'}), HTTP_400_BAD_REQUEST
    
    if User.query.filter_by(email=email).first() is not None:
        return jsonify({'error': 'Email is taken'}), HTTP_409_CONFLICT
    
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({'error': 'username is taken'}), HTTP_409_CONFLICT
    
    hashed_password = generate_password_hash(password, salt_length=8)
    user = User(username=username, email=email, password=hashed_password)

    db.session.add(user)
    db.session.commit()

    token = generate_token(email)
    send_email(to=email, subject="Activate account", body=f'Click the link the activate your account: {request.host_url}api/account/activate/{token}')

    return jsonify({'message': 'Account created. A verification link has been sent to your email address to activate your account.', 'user': {'username': username, 'email': email}}), HTTP_201_CREATED



@account.patch('/activate/<string:token>')
def activate_account(token):
    email = confirm_token(token)
    if not email:
        return jsonify({'detail': 'invalid token'}), HTTP_400_BAD_REQUEST
    user = User.query.filter_by(email=email).first()
    if user.is_active:
        return jsonify({'detail': 'Account already activated'}), HTTP_400_BAD_REQUEST
    else:
        user.is_active = True
        if user.id == 1:
            user.is_admin = True
        db.session.commit()
        return jsonify({'detail': 'Account activated'}), HTTP_200_OK

@account.post('/send-password-reset')
def send_password_reset_link():
    email = request.json['email']
    token = generate_token(email)
    send_email(to=email, subject="Reset Password", body=f'Click the link to reset your password: {request.host_url}api/account/change-password/{token}')
    return jsonify({'detail': 'A link has been sent to your email address to reset your password.'})



@account.patch('/change-password/<string:token>')
def change_password(token):
    email = confirm_token(token)
    if not email:
        return jsonify({'detail': 'invalid token'}), HTTP_400_BAD_REQUEST
    password = request.json['password']
    confirm_password = request.json['confirm_password']

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), HTTP_400_BAD_REQUEST
    if password.isdigit():
        return jsonify({'error': 'Password is entirely numeric'}), HTTP_400_BAD_REQUEST
    if ' ' in password:
        return jsonify({'error': 'No spaces'}), HTTP_400_BAD_REQUEST
    if password != confirm_password:
        return jsonify({'error': 'Password must match'}), HTTP_400_BAD_REQUEST
    
    user = User.query.filter_by(email=email).first_or_404()
    user.password = generate_password_hash(password, salt_length=8)
    db.session.commit()
    return jsonify({'detail': 'password changed successfully'}), HTTP_200_OK


@account.post('/login')
def login():
    email = request.json['email']
    password = request.json['password']
    user = User.query.filter_by(email=email).first()
    if user is None:
        return jsonify({'detail': 'Invalid Credentials'})
    if user.password == 'google':
        return jsonify({'detail': 'Invalid Credentials try logging in with google.'})
    elif not check_password_hash(user.password, password):
        return jsonify({'detail': 'Invalid Credentials'})
    if not user.is_active:
        return jsonify({'detail': 'Account not activated'})
    else:
        user.last_login = datetime.utcnow()
        db.session.commit()
        access_token = create_access_token(identity=email)
        return jsonify(access_token=access_token), HTTP_200_OK
    
@account.get('/google-login-success')
def google_login_success():
    if not google.authorized:
        return jsonify({'error': 'Forbidden'})
    
    # Get the Google OAuth token
    token = google_bp.session.token["access_token"]
    
    # Optional: Retrieve user info
    resp = google.get("/oauth2/v2/userinfo")
    assert resp.ok, resp.text
    user_info = resp.json()

    user = User.query.filter_by(email=user_info['email']).first()

    if user is None:
        # Check for username uniqueness
        base_username = user_info['given_name']
        username = base_username
        count = 1
        while User.query.filter_by(username=username).first() is not None:
            username = f"{base_username}{count}"  # Append a number to make it unique
            count += 1
        
        # Create a new user
        user = User(username=username, 
                    email=user_info['email'], 
                    profile_pic=user_info['picture'],
                    password='google', 
                    is_active=1
                    )
        db.session.add(user)
        db.session.commit()

    # Generate a JWT token for the user
    access_token = create_access_token(identity=user.email)
    user.last_login = datetime.utcnow()
    db.session.commit()

    # Return the token along with user info
    return jsonify({
        "token": access_token,
        "user_info": user_info
    })

@account.post('/logout')
@jwt_required()
def logout():
    jti = get_jwt()["jti"]  # Get the unique identifier (JTI) of the token
    blacklist.add(jti)
    session.clear()
    return jsonify({"detail": "Successfully logged out"}), 200


@account.post('/add-address')
@jwt_required()
def add_address():
    email = get_jwt_identity()
    user_id = User.query.filter_by(email=email).first().id
    # Get all the columns of Address dynamically
    address_data = request.json

    # Ensure all required fields are present
    required_fields = ['full_name', 'street', 'city', 'state', 'zip_code', 'country', 'phone_number']
    for field in required_fields:
        if field not in address_data:
            return {"message": f"{field} is required"}, 400
        
    address_data['user_id'] = user_id

    # Create a new Address instance with the data
    new_address = Address(**address_data)

    # Add to the session and commit to save
    db.session.add(new_address)
    db.session.commit()

    return {"message": "Address added successfully", "address": address_data}, 201

@account.patch('/edit-address/<int:id>')
@jwt_required()
def edit_address(id):
    email = get_jwt_identity()
    current_user = User.query.filter_by(email=email).first()

    # Find the address by ID and check ownership
    address = Address.query.filter_by(id=id, user_id=current_user.id).first()
    if not address:
        return jsonify({'error': 'Address not found or unauthorized'}), 404

    # Parse and update only the provided fields
    data = request.json
    if 'full_name' in data:
        address.full_name = data['full_name']
    if 'street' in data:
        address.street = data['street']
    if 'city' in data:
        address.city = data['city']
    if 'state' in data:
        address.state = data['state']
    if 'zip_code' in data:
        address.zip_code = data['zip_code']
    if 'country' in data:
        address.country = data['country']
    if 'phone_number' in data:
        address.phone_number = data['phone_number']

    db.session.commit()
    return jsonify({'detail': 'Address updated successfully'}), 200


@account.delete('/delete-address/<int:id>')
@jwt_required()
def delete_address(id):
    email = get_jwt_identity()
    current_user = User.query.filter_by(email=email).first()
    # Find the address by ID and check ownership
    address = Address.query.filter_by(id=id, user_id=current_user.id).first()
    if not address:
        return jsonify({'error': 'Address not found or unauthorized'}), 404
    db.session.delete(address)
    db.session.commit()
    return jsonify({'detail': 'Address removed.'})


@account.delete('/delete-account')
@jwt_required()
def delete_account():
    user_identity = get_jwt_identity()  # Get the identity (e.g., email or username) from the JWT

    # Query the user based on the identity
    user = User.query.filter_by(email=user_identity).first()  # Replace with how you identify users in your app

    if not user:
        return jsonify({'detail': 'User not found'}), 404

    db.session.delete(user)  # Mark the user for deletion
    db.session.commit()  # Commit the transaction

    jti = get_jwt()["jti"]  # Get the unique identifier (JTI) of the token
    blacklist.add(jti)

    return jsonify({'detail': 'Account deleted successfully'}), 200

@account.get('/user-detail')
@jwt_required()
def get_user_detail(): 
    user_email = get_jwt_identity()
    current_user = User.query.filter_by(email=user_email).first()

    addresses = Address.query.filter_by(user_id=user_email).all()

    # Serialize addresses into a list of dictionaries
    serialized_addresses = [
        {
            'id': address.id,
            'full_name': address.full_name,
            'street': address.street,
            'city': address.city,
            'state': address.state,
            'zip_code': address.zip_code,
            'country': address.country,
            'phone_number': address.phone_number,
        }
        for address in addresses
    ]

    return jsonify({'username': current_user.username, 'profile picture': current_user.profile_pic, 'Addresses': serialized_addresses}), 200
    

@account.patch('/edit-account')
@jwt_required()
def edit_account():
    email = get_jwt_identity()
    current_user = User.query.filter_by(email=email).first()
    data = request.form
    file = request.files

    if 'username' in data:
        current_user.username = data['username']
        db.session.commit()

    if 'profile_picture' in file:
        file = file['profile_picture']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)  # Secure the filename
            file_path = os.path.join(os.getenv('UPLOAD_FOLDER') + '/profile-pictures', filename)
            file.save(file_path)  # Save the file to the upload folder
            file_path = file_path.replace("\\", "/")

            current_user.profile_pic = request.host_url + file_path
            db.session.commit()
        else:
            return jsonify({'error': 'Invalid file type'}), 400
    return jsonify({'detail': 'Account updated'}), 200
    