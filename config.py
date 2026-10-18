"""
config.py — Configuración central de Nutri-IA.

Lee las variables desde .env (local) o desde las Variables de Railway y las
valida AL ARRANCAR. Si falta una obligatoria o tiene formato inválido, la app
no inicia: es mejor fallar al encender que fallar frente a un usuario.
"""
import re
from functools import lru_cache

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# RFC persona moral: 3 letras + fecha AAMMDD + homoclave de 3 caracteres
_RFC_MORAL = re.compile(r"^[A-ZÑ&]{3}\d{6}[A-Z\d]{3}$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # Variable vacía = "no definida" → usa su valor por defecto
    )

    # ----- Empresa -----
    company_legal_name: str
    company_rfc: str
    company_tax_regime: str
    company_zip_code: str
    privacy_notice_url: str
    support_email: str

    # ----- Aplicación -----
    app_env: str = "production"
    pseudonym_pepper: SecretStr        # SecretStr evita que se imprima en logs
    field_encryption_key: SecretStr
    admin_api_token: SecretStr
    disclaimer_version: str
    database_url: SecretStr

    # ----- WhatsApp -----
    wa_phone_number_id: str
    wa_access_token: SecretStr
    wa_verify_token: SecretStr
    wa_app_secret: SecretStr
    wa_api_version: str
    wa_template_checkin_es: str
    wa_template_checkin_en: str
    wa_template_lang_es: str = "es_MX"
    wa_template_lang_en: str = "en_US"

    # ----- Stripe -----
    stripe_secret_key: SecretStr
    stripe_webhook_secret: SecretStr
    stripe_price_guide_mxn: str
    stripe_price_guide_usd: str
    stripe_price_pro_mxn: str = ""     # Solo se exigen si el Canal 2 puede encenderse
    stripe_price_pro_usd: str = ""
    stripe_success_url: str
    stripe_cancel_url: str
    guide_price_label_es: str
    guide_price_label_en: str
    pro_price_label_es: str = ""
    pro_price_label_en: str = ""

    # ----- PAC (CFDI 4.0) — opcional en fase 1 -----
    pac_provider: str = ""
    pac_api_key: SecretStr = SecretStr("")
    pac_sandbox: bool = True

    # ----- Feature flags -----
    ff_b2b_channel_enabled: bool = False
    ff_b2b_auto_enable_at_sales: int | None = None
    ff_cedula_auto_validation: bool = False

    # ----- Reglas de negocio y seguridad -----
    min_user_age: int
    max_user_age: int
    min_daily_kcal_female: int
    min_daily_kcal_male: int
    followup_weeks: int

    # ---------- Validaciones ----------
    @field_validator("company_rfc")
    @classmethod
    def _validar_rfc(cls, v: str) -> str:
        v = v.strip().upper()
        if not _RFC_MORAL.match(v):
            raise ValueError("COMPANY_RFC no tiene formato de RFC de persona moral")
        return v

    @field_validator("company_zip_code")
    @classmethod
    def _validar_cp(cls, v: str) -> str:
        if not re.fullmatch(r"\d{5}", v.strip()):
            raise ValueError("COMPANY_ZIP_CODE debe tener 5 dígitos")
        return v.strip()

    @field_validator("min_user_age")
    @classmethod
    def _edad_minima_segura(cls, v: int) -> int:
        if v < 18:
            raise ValueError("MIN_USER_AGE no puede ser menor a 18")
        return v

    @model_validator(mode="after")
    def _exigir_b2b_solo_si_puede_activarse(self) -> "Settings":
        """Fase 1: con el Canal 2 apagado, sus precios pueden ir vacíos.
        Si se enciende (manual o por conteo de ventas), pasan a ser obligatorios."""
        b2b_posible = self.ff_b2b_channel_enabled or self.ff_b2b_auto_enable_at_sales
        if b2b_posible and not (self.stripe_price_pro_mxn and self.stripe_price_pro_usd
                                and self.pro_price_label_es and self.pro_price_label_en):
            raise ValueError(
                "Canal 2 activable: faltan STRIPE_PRICE_PRO_MXN/USD o PRO_PRICE_LABEL_ES/EN"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Carga única de la configuración (se reutiliza en toda la app)."""
    return Settings()
