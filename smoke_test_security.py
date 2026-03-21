import os
import sys

# Configurables para prueba rápida y repetible
os.environ.setdefault("LOGIN_RATE_LIMIT", "3 per minute")
os.environ.setdefault("DEFAULT_RATE_LIMIT", "100 per day")
os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

from app import app  # noqa: E402
from models.models import db  # noqa: E402
from models.usuario import Usuario  # noqa: E402


def print_result(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    msg = f"[{status}] {name}"
    if detail:
        msg += f" -> {detail}"
    print(msg)


def main() -> int:
    failures = 0

    with app.app_context():
        bcrypt_ext = app.extensions.get("bcrypt")
        limiter_ext = app.extensions.get("limiter")

        ok_bcrypt_ext = bcrypt_ext is not None
        print_result("bcrypt extension registrada", ok_bcrypt_ext)
        failures += 0 if ok_bcrypt_ext else 1

        ok_limiter_ext = limiter_ext is not None
        print_result("limiter extension registrada", ok_limiter_ext)
        failures += 0 if ok_limiter_ext else 1

        # Usuario de prueba para validar migracion SHA-256 -> bcrypt
        username = "smoke_security_user"
        plain_password = "SmokePass123!"
        user = Usuario.query.filter_by(username=username).first()
        legacy_hash = __import__("hashlib").sha256(plain_password.encode()).hexdigest()

        if not user:
            user = Usuario(username=username, password=legacy_hash, rol="empleado")
            db.session.add(user)
            db.session.commit()
        else:
            user.password = legacy_hash
            db.session.commit()

    client = app.test_client()

    # 1) Login GET
    resp_get = client.get("/login")
    ok_login_get = resp_get.status_code == 200
    print_result("GET /login", ok_login_get, f"status={resp_get.status_code}")
    failures += 0 if ok_login_get else 1

    # 2) Login correcto para disparar migracion a bcrypt
    resp_ok = client.post(
        "/login",
        data={"username": "smoke_security_user", "password": "SmokePass123!"},
        follow_redirects=False,
        environ_overrides={"REMOTE_ADDR": "10.0.0.10"},
    )
    ok_login_post = resp_ok.status_code in (302, 303)
    print_result("POST /login correcto", ok_login_post, f"status={resp_ok.status_code}")
    failures += 0 if ok_login_post else 1

    with app.app_context():
        user = Usuario.query.filter_by(username="smoke_security_user").first()
        migrated = bool(user and (user.password.startswith("$2a$") or user.password.startswith("$2b$")))
        print_result("migracion de hash a bcrypt", migrated)
        failures += 0 if migrated else 1

    # 3) Rate limiting en login con password incorrecta desde misma IP
    statuses = []
    for _ in range(4):
        r = client.post(
            "/login",
            data={"username": "smoke_security_user", "password": "incorrecta"},
            follow_redirects=False,
            environ_overrides={"REMOTE_ADDR": "10.0.0.99"},
        )
        statuses.append(r.status_code)

    got_429 = 429 in statuses
    print_result("rate limit en /login", got_429, f"statuses={statuses}")
    failures += 0 if got_429 else 1

    print("\nResumen:")
    if failures == 0:
        print("Todo OK. Seguridad basica validada.")
        return 0

    print(f"Hay {failures} validaciones fallidas.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
