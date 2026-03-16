"""
referral_utils.py
Lógica de validación de referidos y anti-fraude.

VERSIÓN CON DIAGNÓSTICO COMPLETO — todos los pasos usan print() forzado
para ser visibles en cualquier entorno (Railway, Heroku, VPS) independientemente
de la configuración del logger de Python.
"""
import os
import logging
import requests as _req

logger = logging.getLogger(__name__)

from database import (
    get_user, add_referral, validate_referral,
    update_user, get_config, are_accounts_related
)
from db import execute_query


def get_client_ip_safe():
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
    Llamar DESPUÉS de que la tarea fue completada exitosamente.
    """
    print(f"[REFERRAL] >>> START validate_referral_on_first_task user={user_id}", flush=True)
    try:
        user = get_user(user_id)
        if not user:
            print(f"[REFERRAL] STOP: user={user_id} no encontrado en DB", flush=True)
            return

        referral_validated = user.get('referral_validated')
        print(f"[REFERRAL] referral_validated={referral_validated}", flush=True)
        if referral_validated:
            print(f"[REFERRAL] STOP: ya procesado anteriormente", flush=True)
            return

        pending_referrer = user.get('pending_referrer')
        referred_by      = user.get('referred_by')
        referrer_id      = pending_referrer or referred_by
        print(f"[REFERRAL] pending_referrer={pending_referrer} referred_by={referred_by} -> referrer_id={referrer_id}", flush=True)

        if not referrer_id:
            print(f"[REFERRAL] STOP: sin referrer_id para user={user_id}", flush=True)
            return

        referrer_id   = str(referrer_id)
        referred_name = user.get('first_name') or user.get('username') or 'Usuario'
        print(f"[REFERRAL] referred_name={referred_name}", flush=True)

        # Anti-fraude
        try:
            related = are_accounts_related(referrer_id, str(user_id))
        except Exception as _ae:
            print(f"[REFERRAL] are_accounts_related ERROR: {_ae} -> asumiendo False", flush=True)
            related = False

        print(f"[REFERRAL] IP relacionada: {related}", flush=True)

        if related:
            print(f"[REFERRAL] FRAUDE: referrer={referrer_id} referred={user_id}", flush=True)
            try:
                execute_query("""
                    INSERT INTO referrals
                        (referrer_id, referred_id, referred_username,
                         referred_first_name, validated, validated_at)
                    VALUES (%s, %s, %s, %s, 1, NOW())
                    ON DUPLICATE KEY UPDATE validated=1, validated_at=NOW()
                """, (referrer_id, str(user_id), user.get('username', ''), referred_name))
                print(f"[REFERRAL] INSERT fraude OK", flush=True)
            except Exception as _ins:
                print(f"[REFERRAL] INSERT fraude ERROR: {_ins}", flush=True)
            try:
                execute_query(
                    "UPDATE referrals SET is_fraud=1 WHERE referrer_id=%s AND referred_id=%s",
                    (referrer_id, str(user_id))
                )
            except Exception as _isf:
                print(f"[REFERRAL] is_fraud SET ERROR (col ausente?): {_isf}", flush=True)

            update_user(user_id, pending_referrer=None, referral_validated=True)
            _notify_fraud(referrer_id, referred_name)
            print(f"[REFERRAL] <<< END (fraude)", flush=True)
            return

        # Referido legítimo
        print(f"[REFERRAL] Buscando fila en tabla referrals...", flush=True)
        try:
            from db import get_cursor
            with get_cursor() as _cur:
                _cur.execute(
                    "SELECT id, validated FROM referrals WHERE referrer_id=%s AND referred_id=%s LIMIT 1",
                    (referrer_id, str(user_id))
                )
                ref_row = _cur.fetchone()
        except Exception as _qe:
            print(f"[REFERRAL] SELECT referrals ERROR: {_qe}", flush=True)
            return

        print(f"[REFERRAL] ref_row={ref_row}", flush=True)

        did_validate = False

        if not ref_row:
            print(f"[REFERRAL] Fila NO existe -> add_referral...", flush=True)
            ok = add_referral(referrer_id, str(user_id), user.get('username'), referred_name)
            print(f"[REFERRAL] add_referral -> {ok}", flush=True)
            if not ok:
                print(f"[REFERRAL] STOP: add_referral falló", flush=True)
                return
            print(f"[REFERRAL] -> validate_referral...", flush=True)
            validated_ok = validate_referral(referrer_id, str(user_id))
            print(f"[REFERRAL] validate_referral -> {validated_ok}", flush=True)
            if not validated_ok:
                print(f"[REFERRAL] STOP: validate_referral falló", flush=True)
                return
            did_validate = True

        elif not ref_row.get('validated'):
            print(f"[REFERRAL] Fila existe validated=0 -> validate_referral...", flush=True)
            validated_ok = validate_referral(referrer_id, str(user_id))
            print(f"[REFERRAL] validate_referral -> {validated_ok}", flush=True)
            if not validated_ok:
                print(f"[REFERRAL] STOP: validate_referral falló", flush=True)
                return
            did_validate = True

        else:
            print(f"[REFERRAL] Fila existe validated=1 — ya estaba validado antes", flush=True)

        if did_validate:
            print(f"[REFERRAL] Enviando notificacion a referrer={referrer_id}", flush=True)
            _notify_validated(referrer_id, referred_name)

        print(f"[REFERRAL] <<< END did_validate={did_validate}", flush=True)

    except Exception as e:
        import traceback
        print(f"[REFERRAL] EXCEPCION INESPERADA: {e}", flush=True)
        traceback.print_exc()


def diagnose_referral(user_id):
    """
    Diagnóstico completo del estado de referido para un usuario.
    Retorna un dict con toda la información relevante.
    """
    result = {
        'user_id': str(user_id),
        'user_found': False,
        'pending_referrer': None,
        'referred_by': None,
        'referral_validated': None,
        'completed_tasks_count': 0,
        'referral_row': None,
        'referrer_exists': False,
        'is_fraud_check': None,
        'diagnosis': [],
        'action_needed': None,
    }
    diag = result['diagnosis']

    user = get_user(user_id)
    if not user:
        diag.append('ERROR: usuario no encontrado en DB')
        return result

    result['user_found'] = True
    result['pending_referrer']    = user.get('pending_referrer')
    result['referred_by']         = user.get('referred_by')
    result['referral_validated']  = bool(user.get('referral_validated'))
    result['completed_tasks_count'] = len(user.get('completed_tasks', []))

    referrer_id = user.get('pending_referrer') or user.get('referred_by')

    if not referrer_id:
        diag.append('Sin referrer: el usuario no tiene pending_referrer ni referred_by. '
                    'Nunca entró con link de referido, o el campo se perdió.')
        result['action_needed'] = ('Verificar que el usuario entró con el link correcto. '
                                   'Si es error, usar /api/emergency/add-referral para asignarlo manualmente.')
        return result

    referrer_id = str(referrer_id)

    if result['referral_validated']:
        diag.append('referral_validated=True: ya fue procesado. '
                    'Revisar tabla referrals y transacciones del referrer para confirmar bonus.')
        result['action_needed'] = ('Revisar referrals con validated=1 y bonus_paid. '
                                   'Si bonus_paid=0, usar validate-referral de emergencia.')

    referrer = get_user(referrer_id)
    result['referrer_exists'] = referrer is not None
    if not referrer:
        diag.append(f'ERROR: referrer_id={referrer_id} no existe en users. Referido huérfano.')

    try:
        from db import get_cursor
        with get_cursor() as _cur:
            _cur.execute(
                "SELECT id, validated, bonus_paid, is_fraud, validated_at "
                "FROM referrals WHERE referrer_id=%s AND referred_id=%s LIMIT 1",
                (referrer_id, str(user_id))
            )
            ref_row = _cur.fetchone()
        result['referral_row'] = dict(ref_row) if ref_row else None
    except Exception as e:
        diag.append(f'Error consultando tabla referrals: {e}')

    if not result['referral_row']:
        diag.append('PROBLEMA: No hay fila en tabla referrals. '
                    'create_user falló en add_referral al momento del registro.')
        result['action_needed'] = 'Usar /api/emergency/add-referral y luego validate-referral.'
    else:
        row = result['referral_row']
        if row.get('is_fraud'):
            diag.append('Marcado como FRAUDE (is_fraud=1). No se pagará bonus.')
        elif not row.get('validated'):
            diag.append('PROBLEMA: validated=0 — la validación nunca se completó.')
            result['action_needed'] = 'Usar /api/emergency/validate-referral para forzar validación.'
        elif not row.get('bonus_paid') or float(row.get('bonus_paid') or 0) == 0:
            diag.append('PROBLEMA: validated=1 pero bonus_paid=0. '
                        'La fila se marcó pero update_balance nunca se ejecutó.')
            result['action_needed'] = 'Usar /api/emergency/validate-referral — detectará bonus_paid=0 y lo pagará.'
        else:
            diag.append(f'OK: validated=1 bonus_paid={row.get("bonus_paid")} — todo correcto.')

    try:
        result['is_fraud_check'] = are_accounts_related(referrer_id, str(user_id))
        if result['is_fraud_check']:
            diag.append('ALERTA: IPs compartidas actualmente entre referrer y referred.')
    except Exception as e:
        diag.append(f'No se pudo verificar IPs: {e}')

    return result


def _notify_fraud(referrer_id, referred_name):
    try:
        token = os.environ.get('BOT_TOKEN', '')
        if not token:
            print(f"[REFERRAL] _notify_fraud: BOT_TOKEN no configurado", flush=True)
            return
        safe = str(referred_name).replace('<', '&lt;').replace('>', '&gt;')
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
            json={'chat_id': int(referrer_id), 'text': msg, 'parse_mode': 'HTML'},
            timeout=10
        )
        print(f"[REFERRAL] _notify_fraud enviado a {referrer_id}", flush=True)
    except Exception as e:
        print(f"[REFERRAL] _notify_fraud ERROR: {e}", flush=True)


def _notify_validated(referrer_id, referred_name):
    try:
        from notifications import notify_referral_validated
        referrer_obj = get_user(referrer_id)
        lang  = referrer_obj.get('language_code') if referrer_obj else None
        bonus = float(get_config('referral_bonus', 1.0))
        total = referrer_obj.get('referral_count', 0) if referrer_obj else 0
        notify_referral_validated(
            referrer_id=int(referrer_id),
            referred_name=referred_name,
            reward=f"{bonus:.2f}",
            total_refs=total,
            language_code=lang
        )
        print(f"[REFERRAL] _notify_validated enviado a {referrer_id}", flush=True)
    except Exception as e:
        print(f"[REFERRAL] _notify_validated ERROR: {e}", flush=True)
