from itsdangerous import URLSafeTimedSerializer
from flask import session
from flask_mail import Mail, Message
from dotenv import load_dotenv
from models import User
import os
import uuid

mail = Mail()
load_dotenv()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# Helper function to check allowed extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_token(email):
    serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
    return serializer.dumps(email, salt='python-flask')

def confirm_token(token, expiration=600):
    serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
    try:
        email = serializer.loads(
            token, salt='python-flask', max_age=expiration
        )
        return email
    except Exception:
        return False
    

def send_email(to, subject, body):
    msg = Message(
        subject,
        recipients=[to],
        body=body,
        sender=os.getenv('EMAIL_HOST_USER'),
    )
    mail.send(msg)

def get_user_and_session_id(email):
    """
    Get the user and session ID based on JWT authentication or session.
    
    Returns:
        tuple: (user, session_id)
            - user: The authenticated user object or None if anonymous.
            - session_id: The session ID for anonymous users or None for authenticated users.
    """
    
    if email:
        # If the user is authenticated, fetch the user from the database
        user = User.query.filter_by(email=email).first_or_404()
        session_id = None  # Authenticated users don't need a session_id
    else:
        # If the user is anonymous, generate or retrieve a session_id
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())  # Generate a new session_id if it doesn't exist
        session_id = session['session_id']
        user = None  # Anonymous users don't have a user object
    
    return user, session_id

def check_if_user_is_admin(email):
    if email:
        # If the user is authenticated, fetch the user from the database
        user = User.query.filter_by(email=email).first_or_404()
        if user.is_admin:
            return True
        return False