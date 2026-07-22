import secrets

def generate_csrf_token():
    return secrets.token_hex(32)
