from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from http_status_code import *
import os

from werkzeug.utils import secure_filename

from models import User, Product, ProductImage
from utils import allowed_file
from models import db


product_bp = Blueprint('product', __name__, url_prefix='/api/product')

@product_bp.post('/create-product')
@jwt_required()
def create_product():
    email = get_jwt_identity()
    user = User.query.filter_by(email=email).first()
    if not user.is_admin:
        return jsonify({'detail': 'You dont have permission to perform this command.'}), HTTP_403_FORBIDDEN
    
    name = request.form['name']
    description = request.form['description']
    images = request.files.getlist('images')
    quantity = request.form['quantity']
    price = request.form['price']
    category = request.form['category'].lower()
    brand = request.form['brand']

    product = Product(name=name, description=description,
                      quantity=quantity, price=price, category=category, brand=brand)
    
    db.session.add(product)
    db.session.flush()  # Flush to get product.id before committing

    for image in images:
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            file_path = os.path.join(os.getenv('UPLOAD_FOLDER') + '/product-images', filename)
            image.save(file_path)

            # Save the image path to the ProductImage table
            product_image = ProductImage(product_id=product.id, image_path=request.host_url + file_path.replace("\\", "/"))
            db.session.add(product_image)

    db.session.commit()
    return jsonify({'detail': 'Product created successfully.'}), HTTP_201_CREATED

@product_bp.delete('/delete-product/<int:id>')
@jwt_required()
def delete_product(id):
    email = get_jwt_identity()
    user = User.query.filter_by(email=email).first()
    if not user.is_admin:
        return jsonify({'detail': 'You dont have permission to perform this command.'}), HTTP_403_FORBIDDEN
    product = Product.query.filter_by(id=id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    return jsonify({'detail': 'product deleted'}), HTTP_200_OK

@product_bp.get('/get-categories')
def get_categories():
    # Query to get all distinct categories
    categories = db.session.query(Product.category).distinct().all()
    # Convert the result into a list of strings
    category_list = [category[0] for category in categories]

    return jsonify({
        "categories": category_list
    }), HTTP_200_OK

@product_bp.get('/get-product/<int:id>')
def get_product(id):
    product = Product.query.filter_by(id=id).first_or_404()
    product_images = ProductImage.query.filter_by(product_id=product.id)
    serialized_product = {
        'id': product.id,
        'name': product.name,
        'description': product.description,
        'quantity': product.quantity,
        'price': product.price,
        'category': product.category,
        'brand': product.brand,
        'rating': product.avg_rating,
        'images': [product_image.image_path for product_image in product_images]
    }
    return jsonify(product=serialized_product), HTTP_200_OK



@product_bp.get('/search-product')
def search_product():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    results = Product.query.filter(
        db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%')
        )
    ).paginate(page=page, per_page=per_page)

    products = [{"id": product.id, "name": product.name, 
                 "description": product.description, 
                 'image': [product_image.image_path for product_image in ProductImage.query.filter_by(product_id=product.id)][0]} for product in results.items]

    return jsonify({
        "products": products,
        "total": results.total,
        "pages": results.pages,
        "current_page": results.page,
        "has_next": results.has_next,
        "has_prev": results.has_prev
    })


