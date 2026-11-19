"""Adaptadores de infraestructura (Patrón Adapter y Observer GoF)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from ..application.ports import (
    EstadoValvulaDTO,
    IObservadorEvento,
    IPuertoAPIMeteo,
    IPuertoServidorValvulas,
)
from ..domain.entities import AlertaTemprana, PronosticoMeteo
from ..domain.exceptions import FalloComunicacionValvulaError

logger = logging.getLogger("agritech.auditoria")


class AdaptadorAPIMeteo(IPuertoAPIMeteo):
    """Adaptador para APIMeteo (Open-Meteo HTTPS) con caché local de 3 horas (IE-04)."""

    CACHE_TTL_HORAS: int = 3
    TIMEOUT_SEGUNDOS: float = 5.0
    BASE_URL: str = "https://api.open-meteo.com/v1/forecast"

    def __init__(
        self,
        httpGetter: Optional[Callable[[str, float], Dict[str, Any]]] = None,
        respaldoOffline: Optional[PronosticoMeteo] = None,
    ) -> None:
        self._httpGetter = httpGetter or self._defaultHttpGet
        self._respaldoOffline = respaldoOffline
        self._cache: Dict[Tuple[float, float], PronosticoMeteo] = {}
        self._overrideSimulado: Dict[Tuple[float, float], PronosticoMeteo] = {}

    @staticmethod
    def _defaultHttpGet(url: str, timeout: float) -> Dict[str, Any]:
        respuesta = requests.get(url, timeout=timeout)
        respuesta.raise_for_status()
        return respuesta.json()

    @staticmethod
    def _claveCoord(latitud: float, longitud: float) -> Tuple[float, float]:
        return (round(float(latitud), 4), round(float(longitud), 4))

    def fijarPronosticoSimulado(
        self,
        latitud: float,
        longitud: float,
        probabilidadLluvia: float,
        tempMinimaEsperada: float,
        humedadAmbientePronosticada: float,
        instanteActual: Optional[datetime] = None,
    ) -> None:
        """Permite inyectar condiciones climáticas determinísticas para demostración y pruebas."""
        ahora = instanteActual or datetime.now(timezone.utc)
        clave = self._claveCoord(latitud, longitud)
        self._overrideSimulado[clave] = PronosticoMeteo(
            probabilidadLluvia=float(probabilidadLluvia),
            tempMinimaEsperada=float(tempMinimaEsperada),
            humedadAmbientePronosticada=float(humedadAmbientePronosticada),
            obtenidoDesdeCache=False,
            consultadoEn=ahora,
        )

    def limpiarSimulacion(self, latitud: Optional[float] = None, longitud: Optional[float] = None) -> None:
        """Limpia el pronóstico simulado para volver a usar Open-Meteo real o caché."""
        if latitud is not None and longitud is not None:
            self._overrideSimulado.pop(self._claveCoord(latitud, longitud), None)
        else:
            self._overrideSimulado.clear()

    def sembrarCache(
        self,
        latitud: float,
        longitud: float,
        pronostico: PronosticoMeteo,
    ) -> None:
        """Precarga una entrada de caché local (útil en pruebas de TTL y modo offline)."""
        self._cache[self._claveCoord(latitud, longitud)] = pronostico

    def _parsearOpenMeteo(self, data: Dict[str, Any], ahora: datetime) -> PronosticoMeteo:
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        probs = hourly.get("precipitation_probability") or [15.0]
        humidades = hourly.get("relative_humidity_2m") or [68.0]
        tempsMin = daily.get("temperature_2m_min") or [9.5]

        probMax = float(max(probs[:6])) if probs else 15.0
        humProm = float(sum(humidades[:3]) / max(1, len(humidades[:3])))
        tMin = float(min(tempsMin)) if tempsMin else 9.5

        return PronosticoMeteo(
            probabilidadLluvia=round(probMax, 2),
            tempMinimaEsperada=round(tMin, 2),
            humedadAmbientePronosticada=round(humProm, 2),
            obtenidoDesdeCache=False,
            consultadoEn=ahora,
        )

    def consultarPronostico(
        self,
        latitud: float,
        longitud: float,
        instanteActual: Optional[datetime] = None,
    ) -> PronosticoMeteo:
        """Consulta Open-Meteo (timeout 5 s); ante fallo usa caché válido <= 3 h."""
        ahora = instanteActual or datetime.now(timezone.utc)
        clave = self._claveCoord(latitud, longitud)

        if clave in self._overrideSimulado:
            base = self._overrideSimulado[clave]
            return PronosticoMeteo(
                probabilidadLluvia=base.probabilidadLluvia,
                tempMinimaEsperada=base.tempMinimaEsperada,
                humedadAmbientePronosticada=base.humedadAmbientePronosticada,
                obtenidoDesdeCache=False,
                consultadoEn=ahora,
            )

        url = (
            f"{self.BASE_URL}?latitude={latitud}&longitude={longitud}"
            "&hourly=temperature_2m,relative_humidity_2m,precipitation_probability"
            "&daily=temperature_2m_min&timezone=America/Bogota&forecast_days=2"
        )
        try:
            payload = self._httpGetter(url, self.TIMEOUT_SEGUNDOS)
            pronostico = self._parsearOpenMeteo(payload, ahora)
            self._cache[clave] = pronostico
            return pronostico
        except Exception as exc:
            enCache = self._cache.get(clave)
            if enCache is not None:
                antiguedad = ahora - enCache.consultadoEn
                if antiguedad <= timedelta(hours=self.CACHE_TTL_HORAS):
                    return PronosticoMeteo(
                        probabilidadLluvia=enCache.probabilidadLluvia,
                        tempMinimaEsperada=enCache.tempMinimaEsperada,
                        humedadAmbientePronosticada=enCache.humedadAmbientePronosticada,
                        obtenidoDesdeCache=True,
                        consultadoEn=enCache.consultadoEn,
                    )
            if self._respaldoOffline is not None:
                return PronosticoMeteo(
                    probabilidadLluvia=self._respaldoOffline.probabilidadLluvia,
                    tempMinimaEsperada=self._respaldoOffline.tempMinimaEsperada,
                    humedadAmbientePronosticada=self._respaldoOffline.humedadAmbientePronosticada,
                    obtenidoDesdeCache=True,
                    consultadoEn=ahora,
                )
            raise ConnectionError(
                f"APIMeteo inalcanzable y sin caché válido (<=3 h) para ({latitud}, {longitud}): {exc}"
            ) from exc


class AdaptadorServidorValvulas(IPuertoServidorValvulas):
    """Adaptador PUT /valvulas/{id} con timeout 3 s y política de 3 reintentos (IE-03)."""

    TIMEOUT_SEGUNDOS: float = 3.0
    MAX_REINTENTOS: int = 3

    def __init__(
        self,
        transportCallable: Optional[Callable[[str, bool, int, float], bool]] = None,
    ) -> None:
        self._transportCallable = transportCallable
        self._estadoValvulas: Dict[str, bool] = {}
        self._sectoresConFallo: set[str] = set()
        self.historialComandos: List[Dict[str, Any]] = []

    def establecerFalloSimulado(self, sectorId: str, fallando: bool) -> None:
        """Activa o desactiva fallo simulado de comunicación de electroválvula."""
        if fallando:
            self._sectoresConFallo.add(sectorId)
        else:
            self._sectoresConFallo.discard(sectorId)

    def valvulaEstaAbierta(self, sectorId: str) -> bool:
        """Consulta el estado actual de la válvula simulada."""
        return self._estadoValvulas.get(sectorId, False)

    def _ejecutarConReintentos(self, sectorId: str, abrir: bool) -> EstadoValvulaDTO:
        ultimoError: Optional[Exception] = None
        for intento in range(1, self.MAX_REINTENTOS + 1):
            try:
                if self._transportCallable is not None:
                    ok = self._transportCallable(
                        sectorId, abrir, intento, self.TIMEOUT_SEGUNDOS
                    )
                    if not ok:
                        raise TimeoutError(f"ServidorValvulas rechazó orden en intento {intento}")
                elif sectorId in self._sectoresConFallo:
                    raise TimeoutError(
                        f"Timeout ({self.TIMEOUT_SEGUNDOS}s) comunicando PUT /valvulas/{sectorId}"
                    )
                self._estadoValvulas[sectorId] = abrir
                dto = EstadoValvulaDTO(
                    sectorId=sectorId,
                    abierta=abrir,
                    latenciaMs=42 * intento,
                    intentos=intento,
                    timestamp=datetime.now(timezone.utc),
                )
                self.historialComandos.append(
                    {
                        "sectorId": sectorId,
                        "abierta": abrir,
                        "intentos": intento,
                        "exito": True,
                        "timestamp": dto.timestamp.isoformat(),
                    }
                )
                return dto
            except Exception as exc:
                ultimoError = exc

        self.historialComandos.append(
            {
                "sectorId": sectorId,
                "abierta": abrir,
                "intentos": self.MAX_REINTENTOS,
                "exito": False,
                "error": str(ultimoError),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        raise FalloComunicacionValvulaError(
            f"Fallo en ServidorValvulas para {sectorId} tras {self.MAX_REINTENTOS} reintentos: {ultimoError}"
        ) from ultimoError

    def activarValvula(self, sectorId: str, duracionSegundos: int) -> EstadoValvulaDTO:
        """Abre la electroválvula ejecutando hasta 3 reintentos."""
        _ = duracionSegundos
        return self._ejecutarConReintentos(sectorId, True)

    def desactivarValvula(self, sectorId: str) -> EstadoValvulaDTO:
        """Cierra la electroválvula ejecutando hasta 3 reintentos."""
        return self._ejecutarConReintentos(sectorId, False)


class BitacoraAuditoriaObserver(IObservadorEvento):
    """Observador GoF para registro estructurado JSON de alertas y trazabilidad (RNF-07)."""

    def __init__(self) -> None:
        self._alertasEmitidas: List[AlertaTemprana] = []
        self._eventosAuditoria: List[Dict[str, Any]] = []

    @property
    def alertasEmitidas(self) -> List[AlertaTemprana]:
        """Retorna una copia de solo lectura de las alertas capturadas."""
        return list(self._alertasEmitidas)

    @property
    def eventosAuditoria(self) -> List[Dict[str, Any]]:
        """Retorna una copia de solo lectura de los eventos de auditoría capturados."""
        return list(self._eventosAuditoria)

    def actualizarAlerta(self, alerta: AlertaTemprana) -> None:
        """Captura alertas emitidas y registra evento JSON."""
        self._alertasEmitidas.append(alerta)
        registro = {
            "evento": "ALERTA_TEMPRANA",
            "idAlerta": alerta.idAlerta,
            "idSector": alerta.idSector,
            "tipoAlerta": alerta.tipoAlerta.value,
            "nivelSeveridad": alerta.nivelSeveridad.value,
            "mensaje": alerta.mensaje,
            "timestamp": alerta.timestampGeneracion.isoformat(),
        }
        logger.info(json.dumps(registro, ensure_ascii=False))

    def registrarEventoAuditoria(
        self,
        usuario: str,
        operacion: str,
        detalle: str,
        timestamp: datetime,
    ) -> None:
        """Captura eventos de auditoría en memoria y logger JSON."""
        registro = {
            "usuario": usuario,
            "operacion": operacion,
            "detalle": detalle,
            "timestamp": timestamp.isoformat(),
        }
        self._eventosAuditoria.append(registro)
        logger.info(json.dumps(registro, ensure_ascii=False))
