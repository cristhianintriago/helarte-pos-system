"""
utils/tz_utils.py
-----------------
Funciones auxiliares de zona horaria centralizadas para el sistema Helarte POS.

Principio de diseño:
- La base de datos almacena SIEMPRE timestamps naive en UTC.
- Toda la logica de negocio que necesite "la fecha de hoy" usa la zona horaria
  configurada en APP_TIMEZONE (por defecto: America/Guayaquil).
- Nunca usar datetime.now() directamente en logica de negocio:
  usar ahora_local() o ahora_utc().
- Nunca usar fecha_utc.date() para logica de negocio:
  usar fecha_operativa_de(timestamp_utc) en su lugar.

Por que esto importa:
- Ecuador es UTC-5. Operaciones realizadas entre 19:00 y 23:59 Ecuador
  pertenecen al mismo dia de negocio, pero al dia SIGUIENTE en UTC.
- Sin esta separacion, reportes y cajas muestran fechas incorrectas.
"""

import os
from datetime import datetime, date, timezone, timedelta

import pytz

# Nombre de la zona horaria configurable desde variable de entorno.
# En Render: APP_TIMEZONE=America/Guayaquil
APP_TIMEZONE_NAME: str = os.environ.get('APP_TIMEZONE', 'America/Guayaquil')
APP_TZ = pytz.timezone(APP_TIMEZONE_NAME)


# ==============================================================================
# FUNCIONES PRINCIPALES
# ==============================================================================

def ahora_utc() -> datetime:
    """
    Retorna el momento actual en UTC como datetime naive.
    Es el equivalente correcto de datetime.utcnow() y debe usarse
    como valor para guardar timestamps en la base de datos.
    """
    return datetime.now(pytz.utc).replace(tzinfo=None)


def ahora_local() -> datetime:
    """
    Retorna el momento actual como datetime timezone-aware en la
    zona horaria del negocio (APP_TIMEZONE).
    Usar para mostrar fechas/horas al usuario, nunca para guardar en BD.
    """
    return datetime.now(APP_TZ)


def fecha_operativa_hoy() -> date:
    """
    Retorna la fecha de negocio de hoy segun la zona horaria local.
    Esta es la fecha que debe usarse para toda logica de 'el dia de hoy'.

    Ejemplo: a las 20:00 Ecuador (= 01:00 UTC del dia siguiente),
    esta funcion devuelve la fecha de Ecuador, no la de UTC.
    """
    return ahora_local().date()


def fecha_operativa_de(timestamp_utc_naive: datetime) -> date:
    """
    Convierte un timestamp UTC naive (tal como se almacena en la BD)
    a la fecha de negocio correspondiente en la zona horaria local.

    Usar para mostrar fechas de registros historicos correctamente.
    NUNCA usar timestamp.date() directamente para logica de negocio.

    Args:
        timestamp_utc_naive: datetime naive guardado en la BD (UTC).

    Returns:
        fecha date en la zona horaria del negocio.
    """
    if timestamp_utc_naive is None:
        return None
    # Marcamos el timestamp como UTC y convertimos a zona local.
    dt_utc = pytz.utc.localize(timestamp_utc_naive)
    return dt_utc.astimezone(APP_TZ).date()


def rango_utc_de_fecha(fecha_negocio: date):
    """
    Dado un dia de negocio (date en hora local), devuelve la tupla
    (inicio_utc, fin_utc) como datetimes naive para filtrar en la BD.

    Ejemplo: para el 2025-04-08 Ecuador (UTC-5):
        inicio_utc = 2025-04-08 05:00:00 UTC
        fin_utc    = 2025-04-09 04:59:59 UTC

    Args:
        fecha_negocio: date en la zona horaria del negocio.

    Returns:
        Tupla (inicio_utc, fin_utc) como datetime naive.
    """
    inicio_local = APP_TZ.localize(
        datetime(fecha_negocio.year, fecha_negocio.month, fecha_negocio.day, 0, 0, 0)
    )
    fin_local = APP_TZ.localize(
        datetime(fecha_negocio.year, fecha_negocio.month, fecha_negocio.day, 23, 59, 59)
    )
    inicio_utc = inicio_local.astimezone(pytz.utc).replace(tzinfo=None)
    fin_utc    = fin_local.astimezone(pytz.utc).replace(tzinfo=None)
    return inicio_utc, fin_utc


def formatear_local(timestamp_utc_naive: datetime, formato: str = '%d/%m/%Y %H:%M') -> str:
    """
    Formatea un timestamp UTC naive (de la BD) como string en hora local.
    Usar en todas las respuestas JSON que muestren fechas al usuario.

    Args:
        timestamp_utc_naive: datetime naive de la BD (UTC).
        formato: formato strftime. Default: 'dd/mm/yyyy HH:MM'.

    Returns:
        String con la fecha/hora en zona horaria del negocio.
    """
    if timestamp_utc_naive is None:
        return ''
    dt_utc = pytz.utc.localize(timestamp_utc_naive)
    return dt_utc.astimezone(APP_TZ).strftime(formato)


def fecha_operativa_str(fecha_negocio: date) -> str:
    """
    Formatea una fecha de negocio para mostrar al usuario.

    Args:
        fecha_negocio: date en zona horaria del negocio.

    Returns:
        String en formato 'dd/mm/yyyy'.
    """
    if fecha_negocio is None:
        return ''
    return fecha_negocio.strftime('%d/%m/%Y')
