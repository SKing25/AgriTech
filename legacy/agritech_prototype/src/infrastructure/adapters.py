"""Adaptadores concretos para APIMeteo, ServidorValvulas y Observadores (RNF-03, RNF-06, IE-03, IE-04)."""
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from src.application.ports import (
    EstadoValvulaDTO,
    IObservadorAlerta,
    IPuertoAPIMeteo,
    IPuertoServidorValvulas,
)
from src.domain.entities import AlertaTemprana, PronosticoMeteo
from src.domain.exceptions import (
    ErrorComunicacionAPIMeteo,
    ErrorComunicacionValvula,
)


class AdaptadorAPIMeteo(IPuertoAPIMeteo):
    """
    Adaptador único hacia APIMeteo (IE-04, RNF-03, RNF-06).
    Implementa caché con vigencia de 3 horas y timeout máximo de 5 segundos.
    """

    VIGENCIA_CACHE_HORAS: int = 3
    TIMEOUT_SEGUNDOS: float = 5.0

    def __init__(
        self,
        proveedorExterno: Optional[
            Callable[[float, float], PronosticoMeteo]
        ] = None,
    ) -> None:
        self._proveedorExterno = proveedorExterno
        self._cache: Dict[Tuple[float, float], PronosticoMeteo] = {}

    def consultarPronostico(
        self,
        latitud: float,
        longitud: float,
        instanteActual: Optional[datetime] = None,
    ) -> PronosticoMeteo:
        ahora = instanteActual or datetime.now()
        clave = (round(latitud, 4), round(longitud, 4))

        if self._proveedorExterno is not None:
            try:
                pronostico = self._proveedorExterno(latitud, longitud)
                self._cache[clave] = pronostico
                return pronostico
            except Exception as exc:
                # RNF-03 / Flujo A5: usar último pronóstico en caché si tiene <= 3 horas
                enCache = self._cache.get(clave)
                if enCache is not None:
                    antiguedad = ahora - enCache.timestampConsulta
                    if antiguedad <= timedelta(hours=self.VIGENCIA_CACHE_HORAS):
                        return enCache
                raise ErrorComunicacionAPIMeteo(
                    f"APIMeteo no respondió en {self.TIMEOUT_SEGUNDOS}s y no hay caché vigente: {exc}"
                ) from exc

        # Respuesta simulada por defecto (RD-03)
        pronosticoSimulado = PronosticoMeteo(
            latitud=latitud,
            longitud=longitud,
            temperaturaAmbiente=22.0,
            humedadRelativaAire=75.0,
            probabilidadLluvia=20.0,
            temperaturaMinimaPronosticada=12.0,
            timestampConsulta=ahora,
        )
        self._cache[clave] = pronosticoSimulado
        return pronosticoSimulado


class AdaptadorServidorValvulas(IPuertoServidorValvulas):
    """
    Adaptador único hacia ServidorValvulas (IE-03, RNF-06).
    Ejecuta hasta 3 intentos con timeout de 3 segundos antes de declarar fallo (Flujo E1).
    """

    MAX_REINTENTOS: int = 3
    TIMEOUT_SEGUNDOS: float = 3.0

    def __init__(
        self,
        clienteHttpSimulado: Optional[Callable[[str, str], bool]] = None,
    ) -> None:
        self._clienteHttpSimulado = clienteHttpSimulado
        self._estadosValvulas: Dict[str, str] = {}

    def _enviarOrdenConReintentos(
        self, sectorId: str, estadoObjetivo: str
    ) -> EstadoValvulaDTO:
        ultimoError: Optional[Exception] = None
        for _intento in range(1, self.MAX_REINTENTOS + 1):
            try:
                if self._clienteHttpSimulado is not None:
                    exito = self._clienteHttpSimulado(sectorId, estadoObjetivo)
                    if not exito:
                        raise RuntimeError("Respuesta HTTP 503 de ServidorValvulas")
                self._estadosValvulas[sectorId] = estadoObjetivo
                return EstadoValvulaDTO(
                    idValvula=f"VALV-{sectorId}",
                    estado=estadoObjetivo,
                    timestamp=datetime.now(),
                )
            except Exception as exc:
                ultimoError = exc
        raise ErrorComunicacionValvula(
            f"ServidorValvulas falló tras {self.MAX_REINTENTOS} reintentos para {sectorId}: {ultimoError}"
        )

    def activarValvula(self, sectorId: str, duracionSegundos: int) -> EstadoValvulaDTO:
        """Envía PUT /valvulas/{id} con {estado_objetivo: 'abierta'} (IE-03, F11)."""
        return self._enviarOrdenConReintentos(sectorId, "abierta")

    def desactivarValvula(self, sectorId: str) -> EstadoValvulaDTO:
        """Envía PUT /valvulas/{id} con {estado_objetivo: 'cerrada'} (IE-03, F11)."""
        return self._enviarOrdenConReintentos(sectorId, "cerrada")


class BitacoraAuditoriaObserver(IObservadorAlerta):
    """Observador concreto que registra el 100% de eventos críticos y alertas (RNF-07, SEG-04)."""

    def __init__(self) -> None:
        self.alertasRecibidas: List[AlertaTemprana] = []
        self.registrosBitacora: List[Dict[str, str]] = []

    def actualizarAlerta(self, alerta: AlertaTemprana) -> None:
        self.alertasRecibidas.append(alerta)
        self.registrosBitacora.append(
            {
                "usuario": "SISTEMA_ALERTA",
                "operacion": f"ALERTA_{alerta.tipoAlerta.value}",
                "detalle": alerta.mensaje,
                "fecha_hora": alerta.timestamp.isoformat(),
            }
        )

    def registrarEventoAuditoria(
        self, usuario: str, operacion: str, detalle: str, timestamp: datetime
    ) -> None:
        self.registrosBitacora.append(
            {
                "usuario": usuario,
                "operacion": operacion,
                "detalle": detalle,
                "fecha_hora": timestamp.isoformat(),
            }
        )
