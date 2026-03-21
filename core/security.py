import hashlib

from werkzeug.security import check_password_hash, generate_password_hash


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password_hash, password):
    if is_legacy_sha256_hash(password_hash):
        return password_hash == hashlib.sha256(password.encode()).hexdigest()
    return check_password_hash(password_hash, password)


def is_legacy_sha256_hash(password_hash):
    return len(password_hash) == 64 and all(
        char in "0123456789abcdef" for char in password_hash.lower()
    )
