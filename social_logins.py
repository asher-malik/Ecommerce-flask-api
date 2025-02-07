from flask_dance.contrib.google import make_google_blueprint, google
import os

google_bp = make_google_blueprint(client_id=os.getenv('GOOGLE_CLIENT_ID'), 
                                  client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                                  scope=[
                                        "https://www.googleapis.com/auth/userinfo.profile",
                                        "https://www.googleapis.com/auth/userinfo.email",
                                        "openid"
                                        ],
                                  redirect_to='account.google_login_success')