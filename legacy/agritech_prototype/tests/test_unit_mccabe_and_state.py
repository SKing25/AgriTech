"""
Pruebas Unitarias en las Seams de Dominio y Algorítmicas (Caminos Básicos de McCabe).
Compatible tanto con PyTest como con python3 -m unittest.
"""
from datetime import datetime, timedelta
import unittest

from src.application.strategies import EstrategiaRiegoAgronomico
from src.domain.entities import (
    AlertaTemprana,
    CicloRiego,
    LecturaTelemetria,
    PronosticoMeteo,
    SectorAgricola,
    SensorSuelo,
)
from src.domain.enums import (
    EstadoCicloRiego,
    MotivoCierreRiego,
    TipoAlerta,
)
from src.domain.exceptions import (
    TransicionEstadoInvalidaError,
    UmbralInvalidoError,
)


class TestMcCabeCalcularLaminaRiego(unittest.TestCase):
    """
    Cobertura del 100% de los 6 caminos básicos independientes (v(G) = 5 + 1 = 6)
    del método EstrategiaRiegoAgronomico.calcularLaminaRiego().
    """

    def setUp(self) -> None:
        self.estrategia = EstrategiaRiegoAgronomico()

    def test_camino_1_humedad_igual_o_superior_al_umbral_minimo_no_riega(self) -> None:
        # P1=True (humedadActual=30.0 >= umbralMinimo=30.0) -> retorna 0.0
        lamina = self.estrategia.calcularLaminaRiego(
            humedadActual=30.0,
            umbralMinimo=30.0,
            umbralCritico=15.0,
            umbralObjetivo=60.0,
            probLluvia=10.0,
            tempSuelo=22.0,
        )
        self.assertEqual(lamina, 0.0)

    def test_camino_2_lluvia_alta_y_humedad_no_critica_pospone_riego(self) -> None:
        # P1=False (22 < 30), P2=True (80 > 70), P3=True (22 >= 15) -> retorna 0.0 (Flujo A2)
        lamina = self.estrategia.calcularLaminaRiego(
            humedadActual=22.0,
            umbralMinimo=30.0,
            umbralCritico=15.0,
            umbralObjetivo=60.0,
            probLluvia=80.0,
            tempSuelo=24.0,
        )
        self.assertEqual(lamina, 0.0)

    def test_camino_3_riego_nominal_sin_lluvia_humedad_no_critica_temp_normal(self) -> None:
        # P1=False (20 < 30), P2=False (40 <= 70), P4=False (20 >= 15), P5=False (25 < 35)
        # Déficit = 60 - 20 = 40 -> 40 * 0.45 = 18.0 mm
        lamina = self.estrategia.calcularLaminaRiego(
            humedadActual=20.0,
            umbralMinimo=30.0,
            umbralCritico=15.0,
            umbralObjetivo=60.0,
            probLluvia=40.0,
            tempSuelo=25.0,
        )
        self.assertEqual(lamina, 18.0)

    def test_camino_4_sequia_critica_con_lluvia_alta_riega_con_refuerzo(self) -> None:
        # P1=False (10 < 30), P2=True (85 > 70), P3=False (10 < 15), P4=True (10 < 15), P5=False
        # Déficit = 60 - 10 = 50 -> 50 * 0.45 * 1.20 = 27.0 mm
        lamina = self.estrategia.calcularLaminaRiego(
            humedadActual=10.0,
            umbralMinimo=30.0,
            umbralCritico=15.0,
            umbralObjetivo=60.0,
            probLluvia=85.0,
            tempSuelo=25.0,
        )
        self.assertEqual(lamina, 27.0)

    def test_camino_5_riego_con_compensacion_por_temperatura_alta(self) -> None:
        # P1=False (20 < 30), P2=False (20 <= 70), P4=False (20 >= 15), P5=True (36 >= 35)
        # Déficit = 60 - 20 = 40 -> 40 * 0.45 * 1.15 = 20.7 mm
        lamina = self.estrategia.calcularLaminaRiego(
            humedadActual=20.0,
            umbralMinimo=30.0,
            umbralCritico=15.0,
            umbralObjetivo=60.0,
            probLluvia=20.0,
            tempSuelo=36.0,
        )
        self.assertEqual(lamina, 20.7)

    def test_camino_6_sequia_critica_y_temperatura_alta_acumula_factores(self) -> None:
        # P1=False, P2=False, P4=True (10 < 15), P5=True (38 >= 35)
        # Déficit = 60 - 10 = 50 -> 50 * 0.45 * 1.20 * 1.15 = 31.05 mm
        lamina = self.estrategia.calcularLaminaRiego(
            humedadActual=10.0,
            umbralMinimo=30.0,
            umbralCritico=15.0,
            umbralObjetivo=60.0,
            probLluvia=10.0,
            tempSuelo=38.0,
        )
        self.assertEqual(lamina, 31.05)


class TestMaquinaEstadosYDominio(unittest.TestCase):
    """Pruebas unitarias de la Máquina de Estados de CicloRiego y reglas de SectorAgricola."""

    def test_transiciones_validas_ciclo_riego_hasta_completado(self) -> None:
        inicio = datetime(2026, 11, 13, 8, 0, 0)
        ciclo = CicloRiego(
            idCiclo="CR-001",
            idSector="SEC-01",
            idValvula="VALV-01",
            fechaInicio=inicio,
            humedadInicial=22.0,
            laminaAguaMm=17.1,
        )
        self.assertEqual(ciclo.estado, EstadoCicloRiego.INACTIVO)
        ciclo.transicionarA(EstadoCicloRiego.EVALUANDO_UMBRAL)
        ciclo.transicionarA(EstadoCicloRiego.CONSULTANDO_METEO)
        ciclo.transicionarA(EstadoCicloRiego.ABRIENDO_VALVULA)
        ciclo.transicionarA(EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO)
        self.assertTrue(ciclo.estaActivo())

        ciclo.transicionarA(EstadoCicloRiego.VERIFICANDO_HUMEDAD_OBJETIVO)
        fin = inicio + timedelta(minutes=18)
        ciclo.finalizar(
            humedadFinal=61.5,
            duracionSegundos=1080,
            motivo=MotivoCierreRiego.HUMEDAD_OBJETIVO_ALCANZADA,
            timestamp=fin,
        )
        self.assertEqual(ciclo.estado, EstadoCicloRiego.COMPLETADO)
        self.assertEqual(ciclo.duracionSegundos, 1080)
        self.assertFalse(ciclo.estaActivo())

    def test_transicion_prohibida_lanza_excepcion(self) -> None:
        ciclo = CicloRiego(
            idCiclo="CR-002",
            idSector="SEC-01",
            idValvula="VALV-01",
            fechaInicio=datetime.now(),
            humedadInicial=25.0,
        )
        with self.assertRaises(TransicionEstadoInvalidaError):
            # No puede pasar de INACTIVO directamente a COMPLETADO
            ciclo.transicionarA(EstadoCicloRiego.COMPLETADO)

    def test_validacion_umbrales_sector_rf08(self) -> None:
        sector = SectorAgricola(
            idSector="SEC-01",
            nombre="Sector Norte",
            idValvula="VALV-01",
            latitud=4.60,
            longitud=-74.08,
        )
        sector.configurarUmbrales(critico=12.0, minimo=28.0, objetivo=65.0)
        self.assertEqual(sector.umbralCritico, 12.0)
        self.assertEqual(sector.umbralMinimo, 28.0)
        self.assertEqual(sector.umbralObjetivo, 65.0)

        with self.assertRaises(UmbralInvalidoError):
            # Crítico >= mínimo viola 0 < crítico < mínimo < objetivo <= 100
            sector.configurarUmbrales(critico=35.0, minimo=30.0, objetivo=60.0)

    def test_validacion_rango_fisico_sensor_suelo(self) -> None:
        self.assertTrue(SensorSuelo.validarTrama(0.0, -10.0))
        self.assertTrue(SensorSuelo.validarTrama(100.0, 60.0))
        self.assertFalse(SensorSuelo.validarTrama(-0.1, 25.0))
        self.assertFalse(SensorSuelo.validarTrama(100.1, 25.0))
        self.assertFalse(SensorSuelo.validarTrama(50.0, -10.5))
        self.assertFalse(SensorSuelo.validarTrama(50.0, 60.5))


if __name__ == "__main__":
    unittest.main()
