"""Excepciones tipadas de dominio para AgriTech Precision."""


class DominioAgriTechError(Exception):
    """Excepción base de reglas de negocio e invariantes de dominio."""

    httpStatus: int = 400


class TokenDispositivoInvalidoError(DominioAgriTechError):
    """Se lanza cuando X-Device-Token no corresponde al NodoSensorIoT (HTTP 401)."""

    httpStatus: int = 401


class TelemetriaFueraDeRangoError(DominioAgriTechError):
    """Se lanza cuando humedad o temperatura violan los rangos físicos válidos (HTTP 400)."""

    httpStatus: int = 400


class AccesoNoAutorizadoError(DominioAgriTechError):
    """Se lanza ante violación de política RBAC por rol insuficiente (HTTP 403)."""

    httpStatus: int = 403


class TransicionEstadoInvalidaError(DominioAgriTechError):
    """Se lanza cuando CicloRiego intenta una transición prohibida por la FSM (HTTP 409)."""

    httpStatus: int = 409


class FalloComunicacionValvulaError(DominioAgriTechError):
    """Se lanza cuando ServidorValvulas falla tras agotarse los 3 reintentos (HTTP 502)."""

    httpStatus: int = 502


class UmbralesInvalidosError(DominioAgriTechError):
    """Se lanza cuando no se cumple 0 < critico < minimo < objetivo <= 100 (HTTP 400)."""

    httpStatus: int = 400


class EntidadNoEncontradaError(DominioAgriTechError):
    """Se lanza cuando un SectorAgricola o SensorSuelo no existe (HTTP 404)."""

    httpStatus: int = 404
