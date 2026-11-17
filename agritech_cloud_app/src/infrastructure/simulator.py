"""Simulador físico IoT con reloj acelerable y escenarios de demostración en vivo."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from ..application.ports import IRepositorioAgricola
from ..application.services import ServicioMonitoreoRiego
from ..domain.enums import EstadoCicloRiego, EstadoSensor
from .adapters import AdaptadorAPIMeteo, AdaptadorServidorValvulas
from .controllers import ControladorTelemetriaREST

TZ_BOGOTA = ZoneInfo("America/Bogota")


class RelojSimulacion:
    """Reloj inyectable y determinístico para acelerar ciclos de riego y ventanas temporales."""

    def __init__(self, inicio: Optional[datetime] = None) -> None:
        self._actual = inicio or datetime.now(TZ_BOGOTA)
        self._lock = threading.Lock()

    def ahora(self) -> datetime:
        with self._lock:
            return self._actual

    def avanzarMinutos(self, minutos: float) -> datetime:
        with self._lock:
            self._actual = self._actual + timedelta(minutes=minutos)
            return self._actual

    def establecer(self, instante: datetime) -> None:
        with self._lock:
            self._actual = instante


@dataclass
class EstadoFisicoNodo:
    """Variables físicas simuladas por NodoSensorIoT."""

    idNodo: str
    idSector: str
    token: str
    humedadSuelo: float
    temperaturaSuelo: float
    temperaturaAmbiente: float
    humedadRelativa: float
    horasCondicionFungo: int = 0
    horasCalorSuelo: int = 0


class MotorSimuladorFisico:
    """Generador continuo de telemetría IoT acoplado al estado real de las válvulas."""

    def __init__(
        self,
        repositorio: IRepositorioAgricola,
        servicio: ServicioMonitoreoRiego,
        controlador: ControladorTelemetriaREST,
        adaptadorMeteo: AdaptadorAPIMeteo,
        adaptadorValvulas: AdaptadorServidorValvulas,
        reloj: Optional[RelojSimulacion] = None,
    ) -> None:
        self.repositorio = repositorio
        self.servicio = servicio
        self.controlador = controlador
        self.adaptadorMeteo = adaptadorMeteo
        self.adaptadorValvulas = adaptadorValvulas
        self.reloj = reloj or RelojSimulacion()
        self._lock = threading.RLock()
        self._tickCount: int = 0
        self._estadosFisicos: Dict[str, EstadoFisicoNodo] = {
            "NODO-01": EstadoFisicoNodo("NODO-01", "SEC-01", "tk-nodo-01-agritech", 44.0, 21.5, 19.0, 64.0),
            "NODO-02": EstadoFisicoNodo("NODO-02", "SEC-02", "tk-nodo-02-agritech", 36.0, 23.0, 20.5, 70.0),
            "NODO-03": EstadoFisicoNodo("NODO-03", "SEC-03", "tk-nodo-03-agritech", 27.5, 22.0, 19.5, 68.0),
        }

    def sincronizarDesdeRepositorio(self) -> None:
        """Sincroniza valores físicos iniciales con la última lectura persistida en BD."""
        with self._lock:
            for fisico in self._estadosFisicos.values():
                sector = self.repositorio.obtenerSector(fisico.idSector)
                if sector is not None:
                    ultima = sector.obtenerUltimaLecturaValida()
                    if ultima is not None:
                        fisico.humedadSuelo = ultima.humedadSuelo
                        fisico.temperaturaSuelo = ultima.temperaturaSuelo
                        fisico.temperaturaAmbiente = ultima.temperaturaAmbiente
                        fisico.humedadRelativa = ultima.humedadRelativa

    def obtenerEstadosFisicos(self) -> Dict[str, EstadoFisicoNodo]:
        with self._lock:
            return dict(self._estadosFisicos)

    def ejecutarCicloTick(self, idSectorObjetivo: Optional[str] = None) -> List[Dict[str, object]]:
        """Avanza 5 minutos la simulación, actualiza física del suelo y envía POST /api/lecturas."""
        with self._lock:
            self._tickCount += 1
            ahora = self.reloj.avanzarMinutos(5)
            resultados: List[Dict[str, object]] = []
            for idx, (idNodo, fisico) in enumerate(self._estadosFisicos.items()):
                if idSectorObjetivo and fisico.idSector != idSectorObjetivo:
                    continue
                sensor = self.repositorio.obtenerSensor(idNodo)
                sector = self.repositorio.obtenerSector(fisico.idSector)
                if sensor is None or sector is None or sensor.estadoOperativo == EstadoSensor.APAGADO:
                    continue

                cicloActivo = sector.obtenerCicloActivo()
                estaRegando = cicloActivo is not None and cicloActivo.estado == EstadoCicloRiego.REGANDO
                if estaRegando:
                    fisico.humedadSuelo = round(min(92.0, fisico.humedadSuelo + 8.5), 2)
                else:
                    fisico.humedadSuelo = round(max(8.0, fisico.humedadSuelo - 2.2), 2)

                # Oscilación térmica y ambiental suave cuando no hay escenario extremo activo
                onda = math.sin((self._tickCount + idx) * 0.7)
                if 15.0 <= fisico.temperaturaSuelo < 34.0:
                    fisico.temperaturaSuelo = round(21.5 + idx * 0.8 + onda * 1.4, 2)
                if 15.0 <= fisico.temperaturaAmbiente < 30.0:
                    fisico.temperaturaAmbiente = round(19.5 + idx * 0.6 + onda * 1.1, 2)
                if fisico.humedadRelativa <= 85.0:
                    fisico.humedadRelativa = round(66.0 + idx * 2.0 - onda * 4.5, 2)

                if fisico.temperaturaSuelo >= 35.0:
                    fisico.horasCalorSuelo += 1
                else:
                    fisico.horasCalorSuelo = 0

                if fisico.humedadRelativa > 85.0 and 18.0 <= fisico.temperaturaAmbiente <= 28.0:
                    fisico.horasCondicionFungo += 1
                else:
                    fisico.horasCondicionFungo = 0

                resp = self.controlador.postLecturaTelemetria(
                    payload={
                        "idNodo": fisico.idNodo,
                        "humedadSuelo": fisico.humedadSuelo,
                        "temperaturaSuelo": fisico.temperaturaSuelo,
                        "temperaturaAmbiente": fisico.temperaturaAmbiente,
                        "humedadRelativa": fisico.humedadRelativa,
                        "horasCondicionFungo": fisico.horasCondicionFungo,
                        "horasCalorSuelo": fisico.horasCalorSuelo,
                    },
                    tokenHeader=fisico.token,
                    instanteActual=ahora,
                )
                resultados.append({"idNodo": idNodo, "respuesta": resp})
            return resultados

    def activarEscenario(self, idSector: str, escenario: str) -> Dict[str, object]:
        """Inyecta escenarios críticos reproducibles para demostración en vivo."""
        with self._lock:
            sector = self.repositorio.obtenerSector(idSector)
            if sector is None:
                return {"error": f"Sector no encontrado: {idSector}"}
            fisico = next((f for f in self._estadosFisicos.values() if f.idSector == idSector), None)
            if fisico is None:
                return {"error": f"No existe nodo físico simulado en {idSector}"}

            ahora = self.reloj.avanzarMinutos(1)
            self.adaptadorValvulas.establecerFalloSimulado(idSector, False)

            if escenario == "sequia_emergencia":
                fisico.humedadSuelo = 12.0
                fisico.temperaturaSuelo = 32.0
                self.adaptadorMeteo.fijarPronosticoSimulado(
                    sector.latitud, sector.longitud, 85.0, 14.0, 65.0, ahora
                )
            elif escenario == "lluvia_posponer":
                fisico.humedadSuelo = 23.0
                fisico.temperaturaSuelo = 20.0
                self.adaptadorMeteo.fijarPronosticoSimulado(
                    sector.latitud, sector.longitud, 88.0, 12.0, 78.0, ahora
                )
            elif escenario == "helada":
                fisico.temperaturaAmbiente = 3.0
                self.adaptadorMeteo.fijarPronosticoSimulado(
                    sector.latitud, sector.longitud, 10.0, 1.0, 62.0, ahora
                )
            elif escenario == "riesgo_fungico":
                fisico.humedadRelativa = 92.0
                fisico.temperaturaAmbiente = 22.5
                fisico.horasCondicionFungo = 6
                self.adaptadorMeteo.fijarPronosticoSimulado(
                    sector.latitud, sector.longitud, 30.0, 13.0, 92.0, ahora
                )
            elif escenario == "estres_termico":
                fisico.temperaturaSuelo = 36.5
                fisico.temperaturaAmbiente = 34.0
                fisico.horasCalorSuelo = 2
                self.adaptadorMeteo.fijarPronosticoSimulado(
                    sector.latitud, sector.longitud, 5.0, 18.0, 42.0, ahora
                )
            elif escenario == "fallo_valvula":
                fisico.humedadSuelo = 22.0
                self.adaptadorMeteo.fijarPronosticoSimulado(
                    sector.latitud, sector.longitud, 10.0, 14.0, 60.0, ahora
                )
                self.adaptadorValvulas.establecerFalloSimulado(idSector, True)
            elif escenario == "avanzar_timeout_45min":
                ahoraTimeout = self.reloj.avanzarMinutos(45)
                ciclo = sector.obtenerCicloActivo()
                if ciclo is not None and ciclo.estado == EstadoCicloRiego.REGANDO:
                    segundos = int((ahoraTimeout - ciclo.fechaInicio).total_seconds())
                    cerrado = self.servicio.verificarTimeoutRiego(
                        idSector, max(2700, segundos), fisico.humedadSuelo, ahoraTimeout
                    )
                    return {
                        "escenario": escenario,
                        "cicloCerrado": cerrado.estado.value if cerrado else None,
                    }
            elif escenario == "normalizar":
                fisico.humedadSuelo = 45.0
                fisico.temperaturaSuelo = 21.0
                fisico.temperaturaAmbiente = 19.5
                fisico.humedadRelativa = 65.0
                fisico.horasCalorSuelo = 0
                fisico.horasCondicionFungo = 0
                self.adaptadorMeteo.limpiarSimulacion(sector.latitud, sector.longitud)

            resp = self.controlador.postLecturaTelemetria(
                payload={
                    "idNodo": fisico.idNodo,
                    "humedadSuelo": fisico.humedadSuelo,
                    "temperaturaSuelo": fisico.temperaturaSuelo,
                    "temperaturaAmbiente": fisico.temperaturaAmbiente,
                    "humedadRelativa": fisico.humedadRelativa,
                    "horasCondicionFungo": fisico.horasCondicionFungo,
                    "horasCalorSuelo": fisico.horasCalorSuelo,
                },
                tokenHeader=fisico.token,
                instanteActual=ahora,
            )
            return {"escenario": escenario, "respuesta": resp}
