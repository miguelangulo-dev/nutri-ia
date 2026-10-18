"""
states.py — Nombres de los estados de conversación y utilidades compartidas.

Separado para evitar importaciones circulares entre módulos.
"""
import re


class S:
    """Estados del Canal 1 (usuarios), en el orden del flujo."""
    START = "START"
    LANG = "LANG"
    ROLE = "ROLE"                    # Solo si el Canal 2 está activo
    PRIVACY = "PRIVACY"              # Consentimiento ANTES de pedir datos sensibles
    ALIAS = "ALIAS"
    AGE = "AGE"
    SEX = "SEX"
    WEIGHT = "WEIGHT"
    HEIGHT = "HEIGHT"
    WAIST = "WAIST"
    ACTIVITY = "ACTIVITY"
    GOAL = "GOAL"
    DISCLAIMER = "DISCLAIMER"
    SWORN = "SWORN"
    REFERRAL_CITY = "REFERRAL_CITY"
    FOOD_PROTEIN = "FOOD_PROTEIN"
    FOOD_CARB = "FOOD_CARB"
    FOOD_VEG = "FOOD_VEG"
    FOOD_FLEX = "FOOD_FLEX"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    ACTIVE = "ACTIVE"
    CHECKIN_WEIGHT = "CHECKIN_WEIGHT"
    FINISHED = "FINISHED"
    BLOCKED = "BLOCKED"
    ROUTED_PRO = "ROUTED_PRO"        # El número se registró como profesionista


class P:
    """Estados del registro del Canal 2 (profesionistas)."""
    NAME = "PRO_NAME"
    EMAIL = "PRO_EMAIL"
    CITY = "PRO_CITY"
    CEDULA = "PRO_CEDULA"
    WAIT = "PRO_WAIT"                # A partir de aquí manda el campo status


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def parse_number(raw: str | None) -> float | None:
    """Extrae el primer número de un texto: '72,5 kg' → 72.5"""
    m = _NUM.search(raw or "")
    return float(m.group().replace(",", ".")) if m else None
