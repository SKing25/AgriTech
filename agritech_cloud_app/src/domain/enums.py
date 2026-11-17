"""Enumeraciones canónicas del dominio AgriTech Precision."""

from enum import Enum


class RolUsuario(str, Enum):
    """Perfiles RBAC autorizados (Tabla 1 / SEG-01)."""

    GESTOR_SENSORES = "GESTOR_SENSORES"
    TECNICO_AGRICOLA = "TECNICO_AGRICOLA"
    ADMINISTRADOR = "ADMINISTRADOR"


class EstadoSector(str, Enum):
    """Estado operativo consolidado de un SectorAgricola."""

    OPTIMO = "OPTIMO"
    REQUIERE_RIEGO = "REQUIERE_RIEGO"
    REGANDO = "REGANDO"
    RIEGO_POSPUESTO = "RIEGO_POSPUESTO"
    ALERTA_FITOSANITARIA = "ALERTA_FITOSANITARIA"
    ERROR_VALVULA = "ERROR_VALVULA"


class EstadoSensor(str, Enum):
    """Estado de un NodoSensorIoT / SensorSuelo."""

    ACTIVO = "ACTIVO"
    APAGADO = "APAGADO"
    FALLA_COMUNICACION = "FALLA_COMUNICACION"


class EstadoCicloRiego(str, Enum):
    """Estados de la Máquina de Estados de CicloRiego."""

    EVALUANDO = "EVALUANDO"
    POSPUESTO = "POSPUESTO"
    REGANDO = "REGANDO"
    FINALIZADO = "FINALIZADO"
    ABORTADO_TIMEOUT = "ABORTADO_TIMEOUT"
    ERROR_ACTUADOR = "ERROR_ACTUADOR"


class MotivoCierreRiego(str, Enum):
    """Causales formales de finalización de un CicloRiego."""

    OBJETIVO_ALCANZADO = "OBJETIVO_ALCANZADO"
    TIMEOUT_MAXIMO_45MIN = "TIMEOUT_MAXIMO_45MIN"
    CIERRE_MANUAL = "CIERRE_MANUAL"
    LLUVIA_INMINENTE = "LLUVIA_INMINENTE"
    FALLO_VALVULA = "FALLO_VALVULA"


class TipoAlerta(str, Enum):
    """Clasificación de alertas tempranas (fitosanitarias y operativas)."""

    HELADA = "HELADA"
    ESTRES_TERMICO = "ESTRES_TERMICO"
    RIESGO_FUNGICO = "RIESGO_FUNGICO"
    FALLO_VALVULA = "FALLO_VALVULA"
    BATERIA_CRITICA = "BATERIA_CRITICA"


class NivelSeveridad(str, Enum):
    """Niveles de severidad de AlertaTemprana."""

    INFORMATIVA = "INFORMATIVA"
    ADVERTENCIA = "ADVERTENCIA"
    CRITICA = "CRITICA"
