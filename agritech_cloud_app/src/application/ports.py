"""Puertos (interfaces) y DTOs de la capa de aplicación."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..domain.entities import (
    AlertaTemprana,
    CicloRiego,
    PronosticoMeteo,
    SectorAgricola,
    SensorSuelo,
)
from ..domain.enums import EstadoSector, RolUsuario


@dataclass(frozen=True)
class EstadoValvulaDTO:
    """Respuesta estandarizada de ServidorValvulas (IE-03)."""

    sectorId: str
    abierta: bool
    latenciaMs: int
    intentos: int
    timestamp: datetime


@dataclass
class ResultadoProcesamiento:
    """Resultado consolidado tras procesar una trama de telemetría (CU-04)."""

    idSector: str
    estadoSector: EstadoSector
    accionTomada: str
    cicloActivo: Optional[CicloRiego] = None
    alertaGenerada: Optional[AlertaTemprana] = None
    pronosticoUtilizado: Optional[PronosticoMeteo] = None


class IPuertoAPIMeteo(ABC):
    """Puerto de salida hacia APIMeteo externa (IE-04)."""

    @abstractmethod
    def consultarPronostico(
        self,
        latitud: float,
        longitud: float,
        instanteActual: Optional[datetime] = None,
    ) -> PronosticoMeteo:
        """Consulta el pronóstico meteorológico con respaldo en caché local de 3 h."""


class IPuertoServidorValvulas(ABC):
    """Puerto de salida hacia ServidorValvulas (IE-03)."""

    @abstractmethod
    def activarValvula(self, sectorId: str, duracionSegundos: int) -> EstadoValvulaDTO:
        """Envía orden de apertura a la electroválvula del sector (timeout 3s, 3 reintentos)."""

    @abstractmethod
    def desactivarValvula(self, sectorId: str) -> EstadoValvulaDTO:
        """Envía orden de cierre a la electroválvula del sector (timeout 3s, 3 reintentos)."""


class IObservadorEvento(ABC):
    """Puerto Observer (GoF) para notificación de alertas y trazabilidad de auditoría (RNF-07)."""

    @abstractmethod
    def actualizarAlerta(self, alerta: AlertaTemprana) -> None:
        """Reacciona ante la emisión de una nueva AlertaTemprana."""

    @abstractmethod
    def registrarEventoAuditoria(
        self,
        usuario: str,
        operacion: str,
        detalle: str,
        timestamp: datetime,
    ) -> None:
        """Registra un evento trazable en la bitácora de auditoría."""


class IRepositorioAgricola(ABC):
    """Puerto de persistencia relacional del agregado SectorAgricola y seguridad."""

    @abstractmethod
    def obtenerSector(self, idSector: str) -> Optional[SectorAgricola]:
        """Recupera un SectorAgricola completo por su identificador."""

    @abstractmethod
    def obtenerSectorPorNodo(self, idNodo: str) -> Optional[SectorAgricola]:
        """Recupera el SectorAgricola propietario de un SensorSuelo dado."""

    @abstractmethod
    def obtenerSensor(self, idNodo: str) -> Optional[SensorSuelo]:
        """Recupera un SensorSuelo por idNodo."""

    @abstractmethod
    def guardarSector(self, sector: SectorAgricola) -> None:
        """Persiste el estado completo del agregado SectorAgricola."""

    @abstractmethod
    def listarSectores(self) -> List[SectorAgricola]:
        """Lista todos los sectores registrados en el sistema."""

    @abstractmethod
    def guardarCuenta(self, email: str, nombre: str, rol: RolUsuario, passwordHash: str) -> None:
        """Registra o actualiza una cuenta de usuario con hash seguro (SEG-03)."""

    @abstractmethod
    def obtenerUsuarioPorEmail(self, email: str) -> Optional[Dict[str, Any]]:
        """Consulta un usuario registrado por correo electrónico."""

    @abstractmethod
    def registrarAuditoriaEnBD(
        self,
        usuario: str,
        operacion: str,
        detalle: str,
        timestamp: datetime,
    ) -> None:
        """Almacena un registro inmutable en la tabla bitácora."""

    @abstractmethod
    def obtenerAuditoria(self, limite: int = 100) -> List[Dict[str, Any]]:
        """Obtiene los registros más recientes de la bitácora de auditoría."""
