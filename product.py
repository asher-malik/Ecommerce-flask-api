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
    brand = request.form['brand'].lower()

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

@product_bp.patch('/edit-product/<int:id>')
@jwt_required()
def edit_product(id):
    email = get_jwt_identity()
    user = User.query.filter_by(email=email).first()
    if not user.is_admin:
        return jsonify({'detail': 'You dont have permission to perform this command.'}), HTTP_403_FORBIDDEN
    product = Product.query.filter_by(id=id).first_or_404()
    data = request.form
    
    if 'name' in data:
        product.name = data['name']
    if 'description' in data:
        product.description = data['description']
    if 'quantity' in data:
        product.quantity = data['quantity']
    if 'price' in data:
        product.price = data['price']
    if 'category' in data:
        product.category = data['category']
    if 'brand' in data:
        product.brand = data['brand']
            
    
    db.session.commit()
    return jsonify({'detail': 'Product updated successfully'}), 200

@product_bp.get('/get-categories')
def get_categories():
    # Query to get all distinct categories
    categories_slug = db.session.query(Product.category_slug).distinct().all()
    # Convert the result into a list of strings
    category_slug_list = [category[0] for category in categories_slug]

    return jsonify({
        "categories": category_slug_list
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

@product_bp.get('/category/<string:category_slug>')
def get_products_by_category(category_slug):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Query the database for products in the given category and paginate the results
    products_pagination = Product.query.filter_by(category_slug=category_slug).paginate(page=page, per_page=per_page)

    # Serialize the paginated items
    product_list = [
        {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': float(product.price),
            "rating": product.avg_rating,
            'quantity': product.quantity,
            'category': product.category,
            'brand': product.brand,
            'image': [product_image.image_path for product_image in ProductImage.query.filter_by(product_id=product.id)][0]} 
            
            for product in products_pagination.items]

    

    # Return the paginated response
    return jsonify({
        'products': product_list,
        'total': products_pagination.total,
        'pages': products_pagination.pages,
        'current_page': products_pagination.page,
        'per_page': products_pagination.per_page,
        "has_next": products_pagination.has_next,
        "has_prev": products_pagination.has_prev
    }), HTTP_200_OK

@product_bp.get('/all-products')
def get_all_products():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    # Fetch distinct categories
    categories = db.session.query(Product.category).distinct().all()
    categories = [category[0] for category in categories]  # Extract category names from tuples

    # Create a dictionary to group products by category
    products_by_category = {}

    for category in categories:
        # Query products for each category with pagination
        products = Product.query.filter_by(category=category).paginate(page=page, per_page=per_page, error_out=False)
        products_by_category[category] = [
            {
                "id": product.id,
                "name": product.name,
                "description": product.description,
                "image": ProductImage.query.filter_by(product_id=product.id).first().image_path,
                "quantity": product.quantity,
                "price": float(product.price),
                "category": product.category,
                "brand": product.brand,
                "avg_rating": float(product.avg_rating) if product.avg_rating else 0,
            }
            for product in products.items
        ]

    # Return the products grouped by category
    return jsonify({
        "products": products_by_category,
    }), 200

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
                 "rating": product.avg_rating,
                 "price": product.price,
                 'image': [product_image.image_path for product_image in ProductImage.query.filter_by(product_id=product.id)][0]} for product in results.items]

    return jsonify({
        "products": products,
        "total": results.total,
        "pages": results.pages,
        "current_page": results.page,
        "has_next": results.has_next,
        "has_prev": results.has_prev
    })




