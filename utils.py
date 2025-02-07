from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os

mail = Mail()
load_dotenv()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# Helper function to check allowed extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_token(email):
    serializer = URLSafeTimedSerializer(os.getenv('SECRET_KEY'))
    return serializer.dumps(email, salt='python-flask')

def confirm_token(token, expiration=3600):
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

