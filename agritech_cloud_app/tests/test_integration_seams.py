"""Pruebas de integración sobre seams reales, adaptadores, SQLite, Excel y endpoints Flask."""

from __future__ import annotations

import io
import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

from openpyxl import load_workbook

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from src.application.services import ServicioMonitoreoRiego
from src.domain.entities import PronosticoMeteo
from src.domain.enums import (
    EstadoCicloRiego,
    EstadoSector,
    EstadoSensor,
    MotivoCierreRiego,
    TipoAlerta,
)
from src.infrastructure.adapters import (
    AdaptadorAPIMeteo,
    AdaptadorServidorValvulas,
    BitacoraAuditoriaObserver,
)
from src.infrastructure.controllers import ControladorTelemetriaREST
from src.infrastructure.simulator import MotorSimuladorFisico, RelojSimulacion
from src.infrastructure.sqlite_repository import RepositorioSQLite


class TestIntegracionSeamsYFlask(unittest.TestCase):
    """Pruebas de integración completas de CU-04, IE-02/03/04, SEG-01/02/03, RF-06 y simulador."""

    def setUp(self) -> None:
        self.repo = RepositorioSQLite(":memory:")
        self.repo.sembrarDatosIniciales()
        self.t0 = datetime(2026, 11, 14, 14, 0, tzinfo=timezone.utc)

        def fakeHttpSuccess(url: str, timeout: float):
            _ = (url, timeout)
            return {
                "hourly": {
                    "precipitation_probability": [10.0, 15.0],
                    "relative_humidity_2m": [65.0, 66.0],
                },
                "daily": {"temperature_2m_min": [11.0]},
            }

        self.meteo = AdaptadorAPIMeteo(httpGetter=fakeHttpSuccess)
        self.valvulas = AdaptadorServidorValvulas()
        self.observer = BitacoraAuditoriaObserver()
        self.servicio = ServicioMonitoreoRiego(
            repositorio=self.repo,
            puertoMeteo=self.meteo,
            puertoValvulas=self.valvulas,
            observadores=[self.observer],
        )
        self.controlador = ControladorTelemetriaREST(self.servicio)

    def tearDown(self) -> None:
        self.repo.cerrar()

    def test_flujo_completo_cu04_apertura_y_cierre_objetivo_en_sqlite(self) -> None:
        # 1) Humedad baja 24% -> inicia ciclo REGANDO y abre válvula
        res1 = self.controlador.postLecturaTelemetria(
            payload={"idNodo": "NODO-01", "humedadSuelo": 24.0, "temperaturaSuelo": 21.0},
            tokenHeader="tk-nodo-01-agritech",
            instanteActual=self.t0,
        )
        self.assertEqual(res1["httpStatus"], 201)
        self.assertEqual(res1["body"]["estadoSector"], EstadoSector.REGANDO.value)
        self.assertTrue(self.valvulas.valvulaEstaAbierta("SEC-01"))
        self.assertTrue(any(e["operacion"] == "RIEGO_INICIADO" for e in self.observer.eventosAuditoria))

        # 2) Telemetría posterior alcanza 60.0% exactos -> cierra válvula y pasa a OPTIMO
        res2 = self.controlador.postLecturaTelemetria(
            payload={"idNodo": "NODO-01", "humedadSuelo": 60.0, "temperaturaSuelo": 20.0},
            tokenHeader="tk-nodo-01-agritech",
            instanteActual=self.t0 + timedelta(minutes=15),
        )
        self.assertEqual(res2["httpStatus"], 201)
        self.assertEqual(res2["body"]["accionTomada"], "RIEGO_FINALIZADO_OBJETIVO")
        self.assertEqual(res2["body"]["estadoSector"], EstadoSector.OPTIMO.value)
        self.assertFalse(self.valvulas.valvulaEstaAbierta("SEC-01"))

        sectorPersistido = self.repo.obtenerSector("SEC-01")
        self.assertIsNotNone(sectorPersistido)
        self.assertEqual(len(sectorPersistido.ciclosRiego), 1)
        self.assertEqual(sectorPersistido.ciclosRiego[0].estado, EstadoCicloRiego.FINALIZADO)
        self.assertEqual(sectorPersistido.ciclosRiego[0].motivoCierre, MotivoCierreRiego.OBJETIVO_ALCANZADO)

    def test_timeout_seguridad_45_min_aborta_riego_y_cierra_valvula(self) -> None:
        self.controlador.postLecturaTelemetria(
            payload={"idNodo": "NODO-02", "humedadSuelo": 22.0, "temperaturaSuelo": 22.0},
            tokenHeader="tk-nodo-02-agritech",
            instanteActual=self.t0,
        )
        self.assertTrue(self.valvulas.valvulaEstaAbierta("SEC-02"))

        cerrado = self.servicio.verificarTimeoutRiego(
            "SEC-02", 2700, 48.0, self.t0 + timedelta(minutes=45)
        )
        self.assertIsNotNone(cerrado)
        self.assertEqual(cerrado.estado, EstadoCicloRiego.ABORTADO_TIMEOUT)
        self.assertEqual(cerrado.motivoCierre, MotivoCierreRiego.TIMEOUT_MAXIMO_45MIN)
        self.assertFalse(self.valvulas.valvulaEstaAbierta("SEC-02"))

    def test_seam_api_meteo_cache_3h_y_expiracion(self) -> None:
        estadoRed = {"caida": False}

        def httpFlaky(url: str, timeout: float):
            _ = (url, timeout)
            if estadoRed["caida"]:
                raise TimeoutError("Open-Meteo timeout 5s")
            return {
                "hourly": {"precipitation_probability": [82.0], "relative_humidity_2m": [75.0]},
                "daily": {"temperature_2m_min": [9.0]},
            }

        adaptador = AdaptadorAPIMeteo(httpGetter=httpFlaky)
        vivo = adaptador.consultarPronostico(4.748, -74.065, self.t0)
        self.assertFalse(vivo.obtenidoDesdeCache)
        self.assertEqual(vivo.probabilidadLluvia, 82.0)

        # Con falla de red dentro de 3 horas -> usa caché local válido
        estadoRed["caida"] = True
        cacheado = adaptador.consultarPronostico(4.748, -74.065, self.t0 + timedelta(hours=2, minutes=50))
        self.assertTrue(cacheado.obtenidoDesdeCache)
        self.assertEqual(cacheado.probabilidadLluvia, 82.0)

        # Excedidas 3 horas -> expira caché y falla explícitamente
        with self.assertRaises(ConnectionError):
            adaptador.consultarPronostico(4.748, -74.065, self.t0 + timedelta(hours=3, minutes=5))

    def test_seam_servidor_valvulas_reintentos_y_degradacion_error_valvula(self) -> None:
        # 1) 2 fallos transitorios y éxito en el 3er intento
        intentos = {"n": 0}

        def transporteRecuperable(sectorId: str, abrir: bool, intento: int, timeout: float) -> bool:
            _ = (sectorId, abrir, timeout)
            intentos["n"] = intento
            return intento >= 3

        valvRecuperable = AdaptadorServidorValvulas(transportCallable=transporteRecuperable)
        dto = valvRecuperable.activarValvula("SEC-01", 600)
        self.assertEqual(dto.intentos, 3)
        self.assertTrue(dto.abierta)

        # 2) Fallo total tras 3 reintentos -> alerta FALLO_VALVULA y estado persistente ERROR_VALVULA
        self.valvulas.establecerFalloSimulado("SEC-01", True)
        res = self.controlador.postLecturaTelemetria(
            payload={"idNodo": "NODO-01", "humedadSuelo": 20.0, "temperaturaSuelo": 21.0},
            tokenHeader="tk-nodo-01-agritech",
            instanteActual=self.t0,
        )
        self.assertEqual(res["httpStatus"], 201)
        self.assertEqual(res["body"]["estadoSector"], EstadoSector.ERROR_VALVULA.value)
        self.assertEqual(res["body"]["alerta"], TipoAlerta.FALLO_VALVULA.value)

        # Llega telemetría con helada después -> debe conservar ERROR_VALVULA
        self.meteo.fijarPronosticoSimulado(4.748, -74.065, 10.0, 0.5, 65.0, self.t0 + timedelta(minutes=5))
        resHelada = self.controlador.postLecturaTelemetria(
            payload={"idNodo": "NODO-01", "humedadSuelo": 20.0, "temperaturaSuelo": 15.0},
            tokenHeader="tk-nodo-01-agritech",
            instanteActual=self.t0 + timedelta(minutes=5),
        )
        self.assertEqual(resHelada["body"]["estadoSector"], EstadoSector.ERROR_VALVULA.value)

        # Gestor no puede restablecer falla hidráulica; Técnico Agrícola sí puede
        from src.domain.exceptions import AccesoNoAutorizadoError
        from src.domain.enums import RolUsuario
        with self.assertRaises(AccesoNoAutorizadoError):
            self.servicio.restablecerErrorValvula("SEC-01", RolUsuario.GESTOR_SENSORES, "gestor@agritech.co", self.t0)
        restablecido = self.servicio.restablecerErrorValvula("SEC-01", RolUsuario.TECNICO_AGRICOLA, "tecnico@agritech.co", self.t0)
        self.assertEqual(restablecido.estadoActual, EstadoSector.REQUIERE_RIEGO)

    def test_endpoints_flask_rbac_seguridad_y_exportacion_excel(self) -> None:
        app = create_app(
            dbPath=":memory:",
            iniciarSimulador=False,
            adaptadorMeteo=self.meteo,
            adaptadorValvulas=self.valvulas,
        )
        client = app.test_client()

        # Healthcheck Cloud
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.get_json()["status"], "UP")

        # IE-02 / SEG-02: token inválido -> 401; fuera de rango -> 400
        r401 = client.post(
            "/api/lecturas",
            json={"idNodo": "NODO-01", "humedadSuelo": 40.0, "temperaturaSuelo": 20.0},
            headers={"X-Device-Token": "token-falso"},
        )
        self.assertEqual(r401.status_code, 401)

        r400 = client.post(
            "/api/lecturas",
            json={"idNodo": "NODO-01", "humedadSuelo": 120.0, "temperaturaSuelo": 20.0},
            headers={"X-Device-Token": "tk-nodo-01-agritech"},
        )
        self.assertEqual(r400.status_code, 400)

        # Login como Gestor de Sensores: puede apagar nodo (200) y descargar Excel (200, HU-08), NO puede configurar umbrales (403) ni auditoría (403)
        loginGestor = client.post(
            "/api/auth/login",
            json={"email": "gestor@agritech.co", "password": "AgriGestor2026!"},
        )
        self.assertEqual(loginGestor.status_code, 200)

        rNodoOk = client.put("/api/nodos/NODO-01/estado", json={"encendido": False})
        self.assertEqual(rNodoOk.status_code, 200)
        self.assertEqual(rNodoOk.get_json()["estadoOperativo"], EstadoSensor.APAGADO.value)

        rUmbral403 = client.put(
            "/api/sectores/SEC-01/umbrales",
            json={"umbralCritico": 15.0, "umbralMinimo": 30.0, "umbralObjetivo": 60.0},
        )
        self.assertEqual(rUmbral403.status_code, 403)
        self.assertEqual(client.get("/api/auditoria").status_code, 403)
        excelGestorResp = client.get("/api/reportes/excel")
        self.assertEqual(excelGestorResp.status_code, 200)

        # Login como Técnico Agrícola: puede configurar umbrales (200) y descargar Excel (200), NO operar nodos (403)
        client.post(
            "/api/auth/login",
            json={"email": "tecnico@agritech.co", "password": "AgriTecnico2026!"},
        )
        self.assertEqual(client.put("/api/nodos/NODO-01/estado", json={"encendido": True}).status_code, 403)
        self.assertEqual(
            client.put(
                "/api/sectores/SEC-01/umbrales",
                json={"umbralCritico": 14.0, "umbralMinimo": 32.0, "umbralObjetivo": 62.0},
            ).status_code,
            200,
        )
        self.assertEqual(client.get("/api/auditoria").status_code, 403)

        excelResp = client.get("/api/reportes/excel")
        self.assertEqual(excelResp.status_code, 200)
        wb = load_workbook(io.BytesIO(excelResp.data))
        self.assertIn("Resumen Sectores", wb.sheetnames)
        self.assertIn("Registro Consolidado", wb.sheetnames)
        self.assertGreaterEqual(wb["Resumen Sectores"].max_row, 4)

        # Login como Administrador: acceso a bitácora (200)
        client.post(
            "/api/auth/login",
            json={"email": "admin@agritech.co", "password": "AgriAdmin2026!"},
        )
        audResp = client.get("/api/auditoria")
        self.assertEqual(audResp.status_code, 200)
        self.assertGreater(len(audResp.get_json()["eventos"]), 0)

    def test_motor_simulador_fisico_escenarios(self) -> None:
        reloj = RelojSimulacion(self.t0)
        sim = MotorSimuladorFisico(
            repositorio=self.repo,
            servicio=self.servicio,
            controlador=self.controlador,
            adaptadorMeteo=self.meteo,
            adaptadorValvulas=self.valvulas,
            reloj=reloj,
        )
        resSequia = sim.activarEscenario("SEC-03", "sequia_emergencia")
        self.assertEqual(resSequia["respuesta"]["body"]["estadoSector"], EstadoSector.REGANDO.value)

        resTimeout = sim.activarEscenario("SEC-03", "avanzar_timeout_45min")
        self.assertEqual(resTimeout["cicloCerrado"], EstadoCicloRiego.ABORTADO_TIMEOUT.value)

    def test_rutas_detalle_grafica_sector_y_historial_api(self) -> None:
        app = create_app(
            dbPath=":memory:",
            iniciarSimulador=False,
            adaptadorMeteo=self.meteo,
            adaptadorValvulas=self.valvulas,
        )
        client = app.test_client()

        for idSector in ("SEC-01", "SEC-02", "SEC-03"):
            resp = client.get(f"/sectores/{idSector}")
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode("utf-8")
            self.assertIn("@theme", html)
            self.assertIn("renderMainDetailChart", html)
            self.assertIn("THREE.Timer", html)
            self.assertIn("THREE.AnimationMixer", html)
            self.assertIn(idSector, html)

        resp404 = client.get("/sectores/SEC-INEXISTENTE")
        self.assertEqual(resp404.status_code, 404)

        histResp = client.get("/api/sectores/SEC-01/historial")
        self.assertEqual(histResp.status_code, 200)
        data = histResp.get_json()
        sector = data["sector"]
        self.assertEqual(sector["idSector"], "SEC-01")
        self.assertGreaterEqual(len(sector["historialHumedad"]), 6)
        self.assertEqual(len(sector["historialTempSuelo"]), len(sector["historialHumedad"]))
        self.assertEqual(len(sector["historialTempAmbiente"]), len(sector["historialHumedad"]))
        self.assertEqual(len(sector["historialHumedadRelativa"]), len(sector["historialHumedad"]))
        self.assertIn("lecturasDetalladas", sector)
        self.assertEqual(len(sector["lecturasDetalladas"]), len(sector["historialHumedad"]))


if __name__ == "__main__":
    unittest.main()
