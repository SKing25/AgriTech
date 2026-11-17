"""Repositorio en memoria preconfigurado con los 3 sectores y nodos simulados (NODO-01, 02, 03)."""
from typing import Dict, List, Optional

from src.application.ports import IRepositorioSectores
from src.domain.entities import SectorAgricola, SensorSuelo, ZonaCultivo


class RepositorioSectoresEnMemoria(IRepositorioSectores):
    """Implementación de IRepositorioSectores para prototipo y pruebas de integración."""

    def __init__(self, inicializarSemilla: bool = True) -> None:
        self._sectores: Dict[str, SectorAgricola] = {}
        self._sensores: Dict[str, SensorSuelo] = {}
        if inicializarSemilla:
            self._cargarDatosIniciales()

    def _cargarDatosIniciales(self) -> None:
        configuraciones = [
            ("SEC-01", "Sector Norte - Café", "VALV-01", "NODO-01", "TOK-NODO-01", 4.6097, -74.0817),
            ("SEC-02", "Sector Centro - Aguacate", "VALV-02", "NODO-02", "TOK-NODO-02", 4.6102, -74.0822),
            ("SEC-03", "Sector Sur - Cítricos", "VALV-03", "NODO-03", "TOK-NODO-03", 4.6090, -74.0810),
        ]
        for idSec, nombre, idValv, idNodo, token, lat, lon in configuraciones:
            sector = SectorAgricola(
                idSector=idSec,
                nombre=nombre,
                idValvula=idValv,
                latitud=lat,
                longitud=lon,
            )
            sector.agregarZonaCultivo(
                ZonaCultivo(
                    idZona=f"ZONA-{idSec}",
                    tipoCultivo=nombre.split(" - ")[-1],
                    areaMetrosCuadrados=1000.0,
                    coeficienteCultivoKc=1.05,
                )
            )
            sensor = SensorSuelo(
                idNodo=idNodo,
                idSector=idSec,
                tokenDispositivo=token,
                encendido=True,
                intervaloSegundos=10,
            )
            sector.agregarSensorSuelo(sensor)
            self._sectores[idSec] = sector
            self._sensores[idNodo] = sensor

    def registrarNuevoSectorYNodo(
        self, sector: SectorAgricola, sensor: SensorSuelo
    ) -> None:
        """Permite incorporar dinámicamente nuevos nodos y sectores (RF-09, RNF-06)."""
        sector.agregarSensorSuelo(sensor)
        self._sectores[sector.idSector] = sector
        self._sensores[sensor.idNodo] = sensor

    def obtenerSector(self, idSector: str) -> Optional[SectorAgricola]:
        return self._sectores.get(idSector)

    def obtenerSectorPorNodo(self, idNodo: str) -> Optional[SectorAgricola]:
        sensor = self._sensores.get(idNodo)
        if sensor is None:
            return None
        return self._sectores.get(sensor.idSector)

    def obtenerSensor(self, idNodo: str) -> Optional[SensorSuelo]:
        return self._sensores.get(idNodo)

    def guardarSector(self, sector: SectorAgricola) -> None:
        self._sectores[sector.idSector] = sector
        for sensor in sector.sensoresSuelo:
            self._sensores[sensor.idNodo] = sensor

    def listarSectores(self) -> List[SectorAgricola]:
        return list(self._sectores.values())
