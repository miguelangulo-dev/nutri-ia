"""
crypto.py — Seudonimización y cifrado de datos sensibles.

- pseudonymize_phone(): convierte el número de WhatsApp en un identificador
  irreversible (HMAC-SHA256 + "pepper" secreto). Sirve para BUSCAR al usuario
  sin guardar su número en claro.
- encrypt()/decrypt(): cifrado simétrico (Fernet/AES) para datos que sí hay que
  recuperar: número (para el check-in semanal), alias, peso, estatura, cintura.
- text_fingerprint(): huella SHA-256 del texto EXACTO del aviso mostrado; prueba
  qué versión aceptó el usuario.

Para generar llaves nuevas:  python crypto.py
Dependencias:  pip install cryptography
"""
import hashlib
import hmac
import re
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


def _normalize_phone(phone: str) -> str:
    """Solo dígitos: '+52 1 461-123-4567' y '5214611234567' dan el mismo hash."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        raise ValueError("Número de teléfono vacío o inválido")
    return digits


def pseudonymize_phone(phone: str) -> str:
    """Identificador estable e irreversible (64 caracteres hex)."""
    from config import get_settings  # import tardío: permite correr este archivo sin .env

    pepper = get_settings().pseudonym_pepper.get_secret_value().encode()
    return hmac.new(pepper, _normalize_phone(phone).encode(), hashlib.sha256).hexdigest()


@lru_cache
def _fernet() -> Fernet:
    from config import get_settings

    return Fernet(get_settings().field_encryption_key.get_secret_value().encode())


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        # Llave incorrecta o dato alterado: nunca devolver basura en silencio
        raise ValueError("No se pudo descifrar el dato (llave o integridad)") from exc


def text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    # Imprime llaves listas para pegar en .env (genera nuevas cada vez)
    print(f"ADMIN_API_TOKEN={secrets.token_urlsafe(48)}")
    print(f"PSEUDONYM_PEPPER={secrets.token_urlsafe(48)}")
    print(f"FIELD_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
