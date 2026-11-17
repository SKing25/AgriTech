"""Puertos e interfaces públicas (Seams) para desacoplar infraestructura y pruebas (RNF-06)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.domain.entities import (
    AlertaTemprana,
    CicloRiego,
    PronosticoMeteo,
    SectorAgricola,
    SensorSuelo,
)


@dataclass(frozen=True)
class EstadoValvulaDTO:
    """Estructura de datos reportada por ServidorValvulas (F12, IE-03)."""
    idValvula: str
    estado: str  # "abierta" | "cerrada"
    timestamp: datetime


class IPuertoAPIMeteo(ABC):
    """Seam externa para consulta meteorológica (IE-04, F13, F14)."""

    @abstractmethod
    def consultarPronostico(self, latitud: float, longitud: float) -> PronosticoMeteo:
        """Consulta las condiciones y el pronóstico de las próximas 6 horas."""


class IPuertoServidorValvulas(ABC):
    """Seam externa para actuación sobre electroválvulas (IE-03, F11, F12)."""

    @abstractmethod
    def activarValvula(self, sectorId: str, duracionSegundos: int) -> EstadoValvulaDTO:
        """Envía el estado objetivo 'abierta' al ServidorValvulas."""

    @abstractmethod
    def desactivarValvula(self, sectorId: str) -> EstadoValvulaDTO:
        """Envía el estado objetivo 'cerrada' al ServidorValvulas."""


class IObservadorAlerta(ABC):
    """Interfaz del patrón GoF Observer para notificar alertas y auditoría."""

    @abstractmethod
    def actualizarAlerta(self, alerta: AlertaTemprana) -> None:
        """Recibe notificación cuando se emite una AlertaTemprana."""

    @abstractmethod
    def registrarEventoAuditoria(
        self, usuario: str, operacion: str, detalle: str, timestamp: datetime
    ) -> None:
        """Registra un evento en la bitácora de auditoría (RNF-07, SEG-04)."""


class IRepositorioSectores(ABC):
    """Seam de persistencia para sectores agrícolas y sensores."""

    @abstractmethod
    def obtenerSector(self, idSector: str) -> Optional[SectorAgricola]:
        """Busca un SectorAgricola por su identificador."""

    @abstractmethod
    def obtenerSectorPorNodo(self, idNodo: str) -> Optional[SectorAgricola]:
        """Obtiene el SectorAgricola al que pertenece un NodoSensorIoT."""

    @abstractmethod
    def obtenerSensor(self, idNodo: str) -> Optional[SensorSuelo]:
        """Obtiene un SensorSuelo registrado por su idNodo."""

    @abstractmethod
    def guardarSector(self, sector: SectorAgricola) -> None:
        """Persiste los cambios de un SectorAgricola."""

    @abstractmethod
    def listarSectores(self) -> list[SectorAgricola]:
        """Retorna todos los sectores agrícolas registrados."""


@dataclass(frozen=True)
class ResultadoProcesamiento:
    """Resultado devuelto por el módulo profundo ServicioMonitoreoRiego.procesarTelemetria."""
    codigoHttp: int
    lecturaValida: bool
    estadoSector: str
    estadoValvula: str
    laminaAguaMm: float
    cicloRiego: Optional[CicloRiego]
    alertaGenerada: Optional[AlertaTemprana]
    mensaje: str
