from flask_jwt_extended import JWTManager

jwt = JWTManager()

# In-memory blacklist (for simplicity)
blacklist = set()

@jwt.token_in_blocklist_loader
def check_if_token_is_blacklisted(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return jti in blacklist