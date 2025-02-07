from flask import Flask, send_from_directory, jsonify
from flask_migrate import Migrate

from dotenv import load_dotenv
from models import db
from account import account
from product import product_bp
from blacklist import jwt
from social_logins import google_bp
from http_status_code import *

from datetime import timedelta

from utils import mail
import os

# Load environment variables from the .env file
load_dotenv()

# Allow insecure transport for development (HTTP instead of HTTPS)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"



app = Flask(__name__)

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER')

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///eshop.db"

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

app.config["JWT_SECRET_KEY"] = "Hgdehebffddgns)(snsdndmnsmams)"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=3)

# Configuration for Flask-Mail
app.config['MAIL_SERVER'] = os.getenv('EMAIL_HOST')
app.config['MAIL_PORT'] = os.getenv('EMAIL_PORT')
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_HOST_USER') 
app.config['MAIL_USE_TLS'] = os.getenv('EMAIL_USE_TLS')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_HOST_PASSWORD')

# Ensure the folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)
mail.init_app(app)

migrate = Migrate(app, db)
jwt.init_app(app)


app.register_blueprint(account)
app.register_blueprint(product_bp)


app.register_blueprint(google_bp, url_prefix="/login")

with app.app_context():
    db.create_all()

# Route to serve profile pictures
@app.route('/media/profile-pictures/<filename>')
def serve_profile_pictures(filename):
    return send_from_directory('media/profile-pictures', filename)

# Route to serve product images
@app.route('/media/product-images/<filename>')
def serve_product_images(filename):
    return send_from_directory('media/product-images', filename)

@app.errorhandler(HTTP_404_NOT_FOUND)
def handle_404(e):
    return jsonify({'error': 'Not found'}), HTTP_404_NOT_FOUND


if __name__ == '__main__':
    app.run(debug=os.getenv('DEBUG'))
