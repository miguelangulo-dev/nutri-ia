"""
feature_flags.py — Interruptores de funcionalidades.

Canal 2 (B2B) se enciende si:
  a) FF_B2B_CHANNEL_ENABLED=true  (encendido manual), o
  b) FF_B2B_AUTO_ENABLE_AT_SALES tiene un número y las guías pagadas lo alcanzan.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Payment, PaymentKind, PaymentStatus


async def b2b_enabled(session: AsyncSession) -> bool:
    s = get_settings()
    if s.ff_b2b_channel_enabled:
        return True
    if s.ff_b2b_auto_enable_at_sales:
        paid = await session.scalar(
            select(func.count()).select_from(Payment).where(
                Payment.kind == PaymentKind.GUIDE, Payment.status == PaymentStatus.PAID
            )
        )
        return (paid or 0) >= s.ff_b2b_auto_enable_at_sales
    return False
