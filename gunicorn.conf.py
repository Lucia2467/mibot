"""
gunicorn.conf.py — Configuración de Gunicorn para ARCADE PXC en Railway

Por qué 1 worker + 8 threads y no múltiples workers:
  - El bot de Telegram corre en un hilo del mismo proceso.
  - Con múltiples workers (fork), el bot se iniciaría en CADA proceso → conflicto.
  - 1 worker + 8 threads = paralelismo real sin conflicto con el bot.
  - Flask es thread-safe con threaded=True, Gunicorn con gthread también.

Resultado: ~4-8x más rápido que Flask dev server en producción.
"""

import os
import multiprocessing

# ── Binding ──────────────────────────────────────────────────
port    = int(os.environ.get("PORT", 5000))
bind    = f"0.0.0.0:{port}"

# ── Workers ──────────────────────────────────────────────────
# 1 solo worker para que el bot de Telegram no se duplique
workers     = 1
worker_class = "gthread"   # threads reales (requiere gunicorn[gthread] o solo gunicorn>=20)
threads      = 8            # 8 threads concurrentes → 8 requests en paralelo

# ── Timeouts ─────────────────────────────────────────────────
timeout          = 60    # matar worker si no responde en 60s
graceful_timeout = 30    # tiempo para terminar requests en curso al reiniciar
keepalive        = 5     # keep-alive HTTP en segundos

# ── Logging ──────────────────────────────────────────────────
accesslog  = "-"    # stdout
errorlog   = "-"    # stderr
loglevel   = "warning"   # solo errores en producción (info genera demasiado ruido)
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ── Performance ──────────────────────────────────────────────
preload_app   = True    # cargar la app UNA sola vez antes de hacer fork → más rápido
max_requests  = 1000    # reiniciar worker cada 1000 requests (evita memory leaks)
max_requests_jitter = 100
