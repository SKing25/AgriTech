"""Pruebas unitarias de caminos base McCabe y reglas de dominio."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.application.ports import (
    EstadoValvulaDTO,
    IPuertoAPIMeteo,
    IPuertoServidorValvulas,
    IRepositorioAgricola,
)
from src.application.services import ServicioMonitoreoRiego
from src.application.strategies import EstrategiaRiegoAgronomico
from src.domain.entities import (
    AlertaTemprana,
    CicloRiego,
    LecturaTelemetria,
    PronosticoMeteo,
    SectorAgricola,
    SensorSuelo,
    ZonaCultivo,
)
from src.domain.enums import (
    EstadoCicloRiego,
    EstadoSector,
    EstadoSensor,
    MotivoCierreRiego,
    NivelSeveridad,
    RolUsuario,
    TipoAlerta,
)
from src.domain.exceptions import (
    TransicionEstadoInvalidaError,
    UmbralesInvalidosError,
)


class _DummyRepo(IRepositorioAgricola):
    def obtenerSector(self, idSector: str): return None
    def obtenerSectorPorNodo(self, idNodo: str): return None
    def obtenerSensor(self, idNodo: str): return None
    def guardarSector(self, sector: SectorAgricola): pass
    def listarSectores(self): return []
    def guardarCuenta(self, email: str, nombre: str, rol: RolUsuario, passwordHash: str): pass
    def obtenerUsuarioPorEmail(self, email: str): return None
    def registrarAuditoriaEnBD(self, usuario: str, operacion: str, detalle: str, timestamp: datetime): pass
    def obtenerAuditoria(self, limite: int = 100): return []


class _DummyMeteo(IPuertoAPIMeteo):
    def consultarPronostico(self, latitud: float, longitud: float, instanteActual=None):
        return PronosticoMeteo(10.0, 12.0, 65.0, False, datetime.now(timezone.utc))


class _DummyValvulas(IPuertoServidorValvulas):
    def activarValvula(self, sectorId: str, duracionSegundos: int):
        return EstadoValvulaDTO(sectorId, True, 20, 1, datetime.now(timezone.utc))

    def desactivarValvula(self, sectorId: str):
        return EstadoValvulaDTO(sectorId, False, 20, 1, datetime.now(timezone.utc))


class TestMcCabeEstrategiaYDominio(unittest.TestCase):
    """Cubre los 6 caminos independientes de calcularLaminaRiego y 9 de evaluarRiesgoFitosanitario."""

    def setUp(self) -> None:
        self.estrategia = EstrategiaRiegoAgronomico()
        self.servicio = ServicioMonitoreoRiego(
            repositorio=_DummyRepo(),
            puertoMeteo=_DummyMeteo(),
            puertoValvulas=_DummyValvulas(),
            estrategiaRiego=self.estrategia,
        )
        self.sector = SectorAgricola("SEC-01", "Sector Norte", 4.74, -74.06)
        self.sector.agregarZonaCultivo(ZonaCultivo("ZON-01", "Papa", 3.0, "Floración"))
        self.sector.agregarSensorSuelo(SensorSuelo("NODO-01", "tk-1"))
        self.t0 = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)

    # --- Caminos base calcularLaminaRiego (v(G) = 6, P = 5) ---
    def test_camino1_humedad_optima_en_umbral_minimo_no_riega(self) -> None:
        lamina = self.estrategia.calcularLaminaRiego(30.0, 30.0, 15.0, 60.0, 0.0, 22.0)
        self.assertEqual(lamina, 0.0)

    def test_camino2_humedad_baja_pospuesta_por_lluvia_mayor_70(self) -> None:
        lamina = self.estrategia.calcularLaminaRiego(22.0, 30.0, 15.0, 60.0, 70.1, 22.0)
        self.assertEqual(lamina, 0.0)

    def test_camino3_sequia_critica_ignora_lluvia_y_riega_temperatura_normal(self) -> None:
        # En frontera 15.0% aún pospone; <15.0% (14.9%) riega de emergencia pese a 95% lluvia
        pospuesta = self.estrategia.calcularLaminaRiego(15.0, 30.0, 15.0, 60.0, 95.0, 22.0)
        self.assertEqual(pospuesta, 0.0)
        emergencia = self.estrategia.calcularLaminaRiego(14.9, 30.0, 15.0, 60.0, 95.0, 22.0)
        self.assertEqual(emergencia, round((60.0 - 14.9) * 0.45, 2))

    def test_camino4_deficit_nulo_o_negativo_retorna_cero(self) -> None:
        # Ejercita explícitamente la guarda defensiva P4 con entrada aislada (H_obj < H_min)
        lamina = self.estrategia.calcularLaminaRiego(25.0, 30.0, 15.0, 20.0, 10.0, 20.0)
        self.assertEqual(lamina, 0.0)

    def test_camino5_riego_estandar_con_lluvia_en_limite_70_y_temp_menor_30(self) -> None:
        # probLluvia == 70.0 NO supera 70.0 -> debe regar sin recargo térmico
        lamina = self.estrategia.calcularLaminaRiego(25.0, 30.0, 15.0, 60.0, 70.0, 29.9)
        self.assertEqual(lamina, 15.75)

    def test_camino6_riego_con_compensacion_evapotranspiracion_temp_30_o_mas(self) -> None:
        lamina = self.estrategia.calcularLaminaRiego(25.0, 30.0, 15.0, 60.0, 20.0, 30.0)
        self.assertEqual(lamina, round(35.0 * 0.45 * 1.15, 2))

    # --- Caminos base evaluarRiesgoFitosanitario (v(G) = 9, P = 8) ---
    def _lectura(self, tSuelo=20.0, tAmb=20.0, hr=60.0, ts=None) -> LecturaTelemetria:
        return LecturaTelemetria(
            idLectura="LEC-1",
            idNodo="NODO-01",
            idSector="SEC-01",
            humedadSuelo=45.0,
            temperaturaSuelo=tSuelo,
            temperaturaAmbiente=tAmb,
            humedadRelativa=hr,
            timestamp=ts or self.t0,
        )

    def test_fitosanitario_camino_sin_pronostico_condicion_normal_retorna_none(self) -> None:
        alerta = self.servicio.evaluarRiesgoFitosanitario(
            self.sector, self._lectura(), None, horasCondicionFungo=0, horasCalorSuelo=0
        )
        self.assertIsNone(alerta)

    def test_fitosanitario_camino_helada_prioridad_maxima_y_frontera_2_grados(self) -> None:
        pronHelada = PronosticoMeteo(80.0, 2.0, 90.0, False, self.t0)
        # Aunque también cumpla estrés térmico y riesgo fúngico, HELADA tiene máxima precedencia
        alerta = self.servicio.evaluarRiesgoFitosanitario(
            self.sector,
            self._lectura(tSuelo=36.0, tAmb=22.0, hr=92.0),
            pronHelada,
            horasCondicionFungo=6,
            horasCalorSuelo=2,
        )
        self.assertIsNotNone(alerta)
        self.assertEqual(alerta.tipoAlerta, TipoAlerta.HELADA)
        self.assertEqual(alerta.nivelSeveridad, NivelSeveridad.CRITICA)

    def test_fitosanitario_camino_estres_termico_precede_fungico(self) -> None:
        pron = PronosticoMeteo(10.0, 2.1, 50.0, False, self.t0)
        # T_min = 2.1 no es helada; T_suelo = 35.0 durante 2h -> ESTRES_TERMICO vence a fungico
        alerta = self.servicio.evaluarRiesgoFitosanitario(
            self.sector,
            self._lectura(tSuelo=35.0, tAmb=22.0, hr=90.0),
            pron,
            horasCondicionFungo=6,
            horasCalorSuelo=2,
        )
        self.assertIsNotNone(alerta)
        self.assertEqual(alerta.tipoAlerta, TipoAlerta.ESTRES_TERMICO)
        self.assertEqual(alerta.nivelSeveridad, NivelSeveridad.ADVERTENCIA)

    def test_fitosanitario_estres_termico_menos_de_2h_no_alerta(self) -> None:
        pron = PronosticoMeteo(10.0, 12.0, 50.0, False, self.t0)
        alerta = self.servicio.evaluarRiesgoFitosanitario(
            self.sector,
            self._lectura(tSuelo=36.5, tAmb=32.0, hr=40.0),
            pron,
            horasCalorSuelo=1,
        )
        self.assertIsNone(alerta)

    def test_fitosanitario_camino_fungico_y_fronteras_exactas(self) -> None:
        pron = PronosticoMeteo(10.0, 12.0, 88.0, False, self.t0)
        # HR == 85.0 no es > 85.0 -> None
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(
                self.sector, self._lectura(tAmb=22.0, hr=85.0), pron, horasCondicionFungo=6
            )
        )
        # T_amb < 18.0 -> None
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(
                self.sector, self._lectura(tAmb=17.9, hr=90.0), pron, horasCondicionFungo=6
            )
        )
        # T_amb > 28.0 -> None
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(
                self.sector, self._lectura(tAmb=28.1, hr=90.0), pron, horasCondicionFungo=6
            )
        )
        # horas < 6 -> None
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(
                self.sector, self._lectura(tAmb=25.0, hr=90.0), pron, horasCondicionFungo=5
            )
        )
        # Exacto 18.0°C, HR 85.1%, 6h -> RIESGO_FUNGICO
        alerta = self.servicio.evaluarRiesgoFitosanitario(
            self.sector, self._lectura(tAmb=18.0, hr=85.1), pron, horasCondicionFungo=6
        )
        self.assertIsNotNone(alerta)
        self.assertEqual(alerta.tipoAlerta, TipoAlerta.RIESGO_FUNGICO)

    def test_antispam_12h_suprime_alerta_repetida_y_habilita_despues(self) -> None:
        pron = PronosticoMeteo(5.0, 0.5, 60.0, False, self.t0)
        a1 = self.servicio.evaluarRiesgoFitosanitario(self.sector, self._lectura(ts=self.t0), pron)
        self.assertIsNotNone(a1)
        self.sector.registrarAlerta(a1)

        a2 = self.servicio.evaluarRiesgoFitosanitario(
            self.sector, self._lectura(ts=self.t0 + timedelta(hours=11, minutes=59)), pron
        )
        self.assertIsNone(a2)

        a3 = self.servicio.evaluarRiesgoFitosanitario(
            self.sector, self._lectura(ts=self.t0 + timedelta(hours=12, minutes=1)), pron
        )
        self.assertIsNotNone(a3)

    # --- Reglas de dominio e invariantes FSM ---
    def test_invariantes_umbrales_y_sensor_y_maquina_estados(self) -> None:
        with self.assertRaises(UmbralesInvalidosError):
            self.sector.configurarUmbrales(35.0, 30.0, 60.0)
        with self.assertRaises(UmbralesInvalidosError):
            self.sector.configurarUmbrales(0.0, 30.0, 60.0)
        self.sector.configurarUmbrales(12.0, 28.0, 65.0)
        self.assertEqual(self.sector.umbralMinimo, 28.0)

        self.assertTrue(SensorSuelo.validarTrama(0.0, -10.0))
        self.assertTrue(SensorSuelo.validarTrama(100.0, 60.0))
        self.assertFalse(SensorSuelo.validarTrama(-0.1, 20.0))
        self.assertFalse(SensorSuelo.validarTrama(100.1, 20.0))
        self.assertFalse(SensorSuelo.validarTrama(50.0, 60.1))

        ciclo = CicloRiego("CIC-1", "SEC-01", EstadoCicloRiego.EVALUANDO, 12.0, 22.0, self.t0)
        ciclo.transicionarA(EstadoCicloRiego.REGANDO, subestado="FLUJO_ACTIVO")
        self.sector.iniciarCicloRiego(ciclo)
        with self.assertRaises(TransicionEstadoInvalidaError):
            self.sector.iniciarCicloRiego(
                CicloRiego("CIC-2", "SEC-01", EstadoCicloRiego.EVALUANDO, 10.0, 20.0, self.t0)
            )
        ciclo.finalizar(61.0, 900, MotivoCierreRiego.OBJETIVO_ALCANZADO, self.t0 + timedelta(minutes=15))
        with self.assertRaises(TransicionEstadoInvalidaError):
            ciclo.transicionarA(EstadoCicloRiego.REGANDO)

    def test_registrar_alerta_preserva_error_valvula(self) -> None:
        alertaValvula = AlertaTemprana(
            "ALT-V", "SEC-01", TipoAlerta.FALLO_VALVULA, NivelSeveridad.CRITICA, "Fallo", self.t0
        )
        self.sector.registrarAlerta(alertaValvula)
        self.assertEqual(self.sector.estadoActual, EstadoSector.ERROR_VALVULA)

        alertaHelada = AlertaTemprana(
            "ALT-H", "SEC-01", TipoAlerta.HELADA, NivelSeveridad.CRITICA, "Helada", self.t0
        )
        self.sector.registrarAlerta(alertaHelada)
        self.assertEqual(self.sector.estadoActual, EstadoSector.ERROR_VALVULA)


if __name__ == "__main__":
    unittest.main()
