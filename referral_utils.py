"""
referral_utils.py
Lógica de validación de referidos y anti-fraude.
Importado tanto por web.py como por user_tasks_routes.py sin crear ciclos.
"""
import os
import logging
import requests as _req

logger = logging.getLogger(__name__)

# ── Imports de database (nunca importar web aquí) ────────────
from database import (
    get_user, add_referral, validate_referral,
    update_user, get_config, are_accounts_related
)
from db import execute_query


def get_client_ip_safe():
    """Obtiene la IP del cliente de forma segura desde Flask request."""
    try:
        from flask import request
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            return forwarded.split(',')[0].strip()
        return request.remote_addr or ''
    except Exception:
        return ''


def validate_referral_on_first_task(user_id):
    """
    Valida el referido cuando el usuario completa su primera tarea.
    - Si las IPs coinciden: marca is_fraud=1 y notifica al invitador
    - Si es legítimo: valida y notifica al invitador
    Llamar DESPUÉS de que la tarea fue completada exitosamente.
    """
    try:
        user = get_user(user_id)
        if not user:
            return

        # Ya fue procesado antes
        if user.get('referral_validated'):
            return

        # Obtener referrer
        referrer_id = (user.get('pending_referrer') or
                       user.get('referred_by'))
        if not referrer_id:
            return

        referrer_id = str(referrer_id)
        referred_name = (user.get('first_name') or
                         user.get('username') or 'Usuario')

        logger.info(f"[referral] Primera tarea: user={user_id} referrer={referrer_id}")

        # ── Anti-fraude: IP compartida ────────────────────────
        if are_accounts_related(referrer_id, str(user_id)):
            logger.warning(
                f"[ANTI-FRAUD] IP compartida: referrer={referrer_id} referred={user_id}"
            )
            # INSERT/UPDATE base sin is_fraud para no fallar si la columna no existe aún.
            execute_query("""
                INSERT INTO referrals
                    (referrer_id, referred_id, referred_username,
                     referred_first_name, validated, validated_at)
                VALUES (%s, %s, %s, %s, 1, NOW())
                ON DUPLICATE KEY UPDATE
                    validated=1, validated_at=NOW()
            """, (referrer_id, str(user_id),
                  user.get('username', ''), referred_name))
            # is_fraud en sentencia separada; falla silenciosamente si columna no existe.
            try:
                execute_query("""
                    UPDATE referrals SET is_fraud = 1
                    WHERE referrer_id = %s AND referred_id = %s
                """, (referrer_id, str(user_id)))
            except Exception as _isf2:
                logger.warning(f"[ANTI-FRAUD] is_fraud update skipped: {_isf2}")

            # Limpiar para no reintentar
            update_user(user_id, pending_referrer=None, referral_validated=True)

            # Notificar al invitador
            _notify_fraud(referrer_id, referred_name)
            return

        # ── Referido legítimo ─────────────────────────────────
        ref_row = execute_query(
            "SELECT id, validated FROM referrals "
            "WHERE referrer_id=%s AND referred_id=%s LIMIT 1",
            (referrer_id, str(user_id)), fetch_one=True
        )

        did_validate = False
        if not ref_row:
            # El registro en referrals no existe — puede ocurrir si create_user
            # falló en add_referral (ej: DB no disponible en el momento del registro).
            # Recreamos y validamos directamente.
            logger.warning(
                f"[referral] Registro no encontrado en referrals para "
                f"referrer={referrer_id} referred={user_id}. Recreando."
            )
            ok = add_referral(referrer_id, str(user_id),
                              user.get('username'), referred_name)
            if not ok:
                logger.error(
                    f"[referral] add_referral falló para referrer={referrer_id} "
                    f"referred={user_id}. Referido NO validado."
                )
                return
            validated_ok = validate_referral(referrer_id, str(user_id))
            if not validated_ok:
                logger.error(
                    f"[referral] validate_referral falló tras add_referral. "
                    f"referrer={referrer_id} referred={user_id}"
                )
                return
            did_validate = True
        elif not ref_row.get('validated'):
            validated_ok = validate_referral(referrer_id, str(user_id))
            if not validated_ok:
                logger.error(
                    f"[referral] validate_referral falló (registro existente). "
                    f"referrer={referrer_id} referred={user_id}"
                )
                return
            did_validate = True
        else:
            logger.info(
                f"[referral] Ya validado previamente: referrer={referrer_id} referred={user_id}"
            )

        if did_validate:
            _notify_validated(referrer_id, referred_name)

    except Exception as e:
        logger.error(f"[validate_referral_on_first_task] ERROR: {e}")
        import traceback; traceback.print_exc()


def _notify_fraud(referrer_id, referred_name):
    """Envía notificación de fraude al invitador vía Bot API directo."""
    try:
        token = os.environ.get('BOT_TOKEN', '')
        if not token:
            logger.warning("[notify_fraud] BOT_TOKEN no configurado")
            return
        safe = str(referred_name).replace('<','&lt;').replace('>','&gt;')
        msg = (
            "\u26a0\ufe0f <b>Tu referido se ha unido \u2014 "
            "pero no recibiste recompensa</b>\n\n"
            "\U0001f464 <b>Referido:</b> " + safe + "\n\n"
            "Tu referido se registr\u00f3 correctamente bajo tu enlace, "
            "sin embargo <b>la recompensa no fue acreditada</b> porque se "
            "detect\u00f3 actividad anormal entre las cuentas.\n\n"
            "\u2705 <b>Tu cuenta no tiene ninguna restricci\u00f3n "
            "por ahora.</b>\n\n"
            "\u26d4 Por favor, deja de intentar ganar recompensas con "
            "cuentas propias o vinculadas. Si este comportamiento "
            "contin\u00faa, tu cuenta podr\u00eda ser restringida "
            "permanentemente."
        )
        _req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': int(referrer_id), 'text': msg,
                  'parse_mode': 'HTML'},
            timeout=10
        )
        logger.info(f"[notify_fraud] Enviado a {referrer_id}")
    except Exception as e:
        logger.warning(f"[notify_fraud] Error: {e}")


def _notify_validated(referrer_id, referred_name):
    """Notifica al invitador que su referido fue validado."""
    try:
        from notifications import notify_referral_validated
        referrer_obj = get_user(referrer_id)
        lang = referrer_obj.get('language_code') if referrer_obj else None
        bonus = float(get_config('referral_bonus', 1.0))
        total = referrer_obj.get('referral_count', 0) if referrer_obj else 0
        notify_referral_validated(
            referrer_id=int(referrer_id),
            referred_name=referred_name,
            reward=f"{bonus:.2f}",
            total_refs=total,
            language_code=lang
        )
        logger.info(f"[notify_validated] Enviado a {referrer_id}")
    except Exception as e:
        logger.warning(f"[notify_validated] Error: {e}")
