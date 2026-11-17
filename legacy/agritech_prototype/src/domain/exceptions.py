"""Excepciones de dominio y seguridad de AgriTech Precision."""


class ErrorDominioAgriTech(Exception):
    """Excepción base del dominio AgriTech Precision."""


class UmbralInvalidoError(ErrorDominioAgriTech):
    """Lanzada cuando no se cumple 0 < crítico < mínimo < objetivo <= 100 (RF-08)."""


class DispositivoNoAutorizadoError(ErrorDominioAgriTech):
    """Lanzada cuando un nodo sensor no está registrado o su token es inválido (SEG-02)."""


class AccesoNoAutorizadoError(ErrorDominioAgriTech):
    """Lanzada cuando un rol intenta ejecutar una operación prohibida (SEG-01, código 403)."""


class LecturaFueraDeRangoError(ErrorDominioAgriTech):
    """Lanzada cuando la lectura incumple los rangos físicos válidos (RF-01, HU-02)."""


class TransicionEstadoInvalidaError(ErrorDominioAgriTech):
    """Lanzada cuando CicloRiego intenta una transición prohibida en su máquina de estados."""


class ErrorComunicacionValvula(ErrorDominioAgriTech):
    """Lanzada tras agotar los 3 reintentos hacia ServidorValvulas (IE-03)."""


class ErrorComunicacionAPIMeteo(ErrorDominioAgriTech):
    """Lanzada cuando APIMeteo excede el timeout de 5 segundos o falla (IE-04, RNF-03)."""
