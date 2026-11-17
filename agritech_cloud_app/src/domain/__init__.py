"""Capa de dominio de AgriTech Precision."""

from .enums import (
    EstadoCicloRiego,
    EstadoSector,
    EstadoSensor,
    MotivoCierreRiego,
    NivelSeveridad,
    RolUsuario,
    TipoAlerta,
)
from .exceptions import (
    AccesoNoAutorizadoError,
    DominioAgriTechError,
    EntidadNoEncontradaError,
    FalloComunicacionValvulaError,
    TelemetriaFueraDeRangoError,
    TokenDispositivoInvalidoError,
    TransicionEstadoInvalidaError,
    UmbralesInvalidosError,
)
from .entities import (
    AlertaTemprana,
    CicloRiego,
    LecturaTelemetria,
    PronosticoMeteo,
    SectorAgricola,
    SensorSuelo,
    ZonaCultivo,
)

__all__ = [
    "AccesoNoAutorizadoError",
    "AlertaTemprana",
    "CicloRiego",
    "DominioAgriTechError",
    "EntidadNoEncontradaError",
    "EstadoCicloRiego",
    "EstadoSector",
    "EstadoSensor",
    "FalloComunicacionValvulaError",
    "LecturaTelemetria",
    "MotivoCierreRiego",
    "NivelSeveridad",
    "PronosticoMeteo",
    "RolUsuario",
    "SectorAgricola",
    "SensorSuelo",
    "TelemetriaFueraDeRangoError",
    "TipoAlerta",
    "TokenDispositivoInvalidoError",
    "TransicionEstadoInvalidaError",
    "UmbralesInvalidosError",
    "ZonaCultivo",
]
