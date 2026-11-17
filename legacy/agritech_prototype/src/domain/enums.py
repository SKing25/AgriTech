"""Enumeraciones canónicas del dominio AgriTech Precision."""
from enum import Enum


class EstadoSector(str, Enum):
    """Estado operativo de un SectorAgricola en el dashboard."""
    NORMAL = "NORMAL"
    EN_RIEGO = "EN_RIEGO"
    POSPUESTO_POR_LLUVIA = "POSPUESTO_POR_LLUVIA"
    ALERTA_ACTIVA = "ALERTA_ACTIVA"
    ERROR_VALVULA = "ERROR_VALVULA"


class EstadoCicloRiego(str, Enum):
    """Estados formales de la máquina de estados UML para CicloRiego."""
    INACTIVO = "INACTIVO"
    EVALUANDO_UMBRAL = "EVALUANDO_UMBRAL"
    CONSULTANDO_METEO = "CONSULTANDO_METEO"
    POSPUESTO_POR_LLUVIA = "POSPUESTO_POR_LLUVIA"
    # Estado compuesto REGANDO y sus subestados anidados
    REGANDO = "REGANDO"
    ABRIENDO_VALVULA = "REGANDO.ABRIENDO_VALVULA"
    IRRIGANDO_FLUJO_ACTIVO = "REGANDO.IRRIGANDO_FLUJO_ACTIVO"
    VERIFICANDO_HUMEDAD_OBJETIVO = "REGANDO.VERIFICANDO_HUMEDAD_OBJETIVO"
    CERRANDO_VALVULA = "CERRANDO_VALVULA"
    COMPLETADO = "COMPLETADO"
    ABORTADO_TIMEOUT = "ABORTADO_TIMEOUT"
    FALLO_VALVULA = "FALLO_VALVULA"


class MotivoCierreRiego(str, Enum):
    """Motivos de finalización o suspensión de un CicloRiego (RF-04, RF-05)."""
    HUMEDAD_OBJETIVO_ALCANZADA = "HUMEDAD_OBJETIVO_ALCANZADA"
    TIEMPO_MAXIMO_CUMPLIDO = "TIEMPO_MAXIMO_CUMPLIDO"
    POSPUESTO_POR_LLUVIA = "POSPUESTO_POR_LLUVIA"
    ERROR_COMUNICACION_VALVULA = "ERROR_COMUNICACION_VALVULA"


class TipoAlerta(str, Enum):
    """Categorías de alerta temprana (RF-06, IE-03)."""
    RIESGO_FITOSANITARIO = "RIESGO_FITOSANITARIO"
    ESTRES_TERMICO = "ESTRES_TERMICO"
    RIESGO_HELADA = "RIESGO_HELADA"
    FALLO_VALVULA = "FALLO_VALVULA"


class RolUsuario(str, Enum):
    """Roles de usuario del sistema según Tabla 1 y Tabla 5 del SRS (RF-07)."""
    GESTOR_SENSORES = "GESTOR_SENSORES"
    TECNICO_AGRICOLA = "TECNICO_AGRICOLA"
    ADMINISTRADOR = "ADMINISTRADOR"
