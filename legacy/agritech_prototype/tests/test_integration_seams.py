"""
Pruebas de Integración en las Seams de Aplicación e Infraestructura:
- ServicioMonitoreoRiego + evaluarRiesgoFitosanitario (9 caminos básicos de McCabe).
- Integración con Mocks/Dobles de NodoSensorIoT, APIMeteo (caché 3h) y ServidorValvulas (3 reintentos).
- Temporizador after(45 min) = 2700s y control de acceso por rol (SEG-01, SEG-02).
"""
from datetime import datetime, timedelta
import unittest

from src.application.services import ServicioMonitoreoRiego
from src.domain.entities import LecturaTelemetria, PronosticoMeteo
from src.domain.enums import (
    EstadoCicloRiego,
    EstadoSector,
    MotivoCierreRiego,
    RolUsuario,
    TipoAlerta,
)
from src.infrastructure.adapters import (
    AdaptadorAPIMeteo,
    AdaptadorServidorValvulas,
    BitacoraAuditoriaObserver,
)
from src.infrastructure.controllers import ControladorTelemetriaREST
from src.infrastructure.repositories import RepositorioSectoresEnMemoria


class TestIntegracionSeamsYMocks(unittest.TestCase):
    """Pruebas de integración extremo a extremo sobre las Seams públicas."""

    def setUp(self) -> None:
        self.repo = RepositorioSectoresEnMemoria(inicializarSemilla=True)
        self.bitacora = BitacoraAuditoriaObserver()
        self.apiMeteo = AdaptadorAPIMeteo()
        self.servidorValvulas = AdaptadorServidorValvulas()
        self.servicio = ServicioMonitoreoRiego(
            repositorio=self.repo,
            puertoMeteo=self.apiMeteo,
            puertoValvulas=self.servidorValvulas,
            observadores=[self.bitacora],
        )
        self.controlador = ControladorTelemetriaREST(self.servicio)
        self.ahora = datetime(2026, 11, 13, 10, 0, 0)

    def test_flujo_completo_apertura_y_cierre_riego_al_alcanzar_objetivo(self) -> None:
        # 1. Lectura baja (20% < 30%) dispara apertura de electroválvula
        resp1 = self.controlador.postLecturaTelemetria(
            payload={
                "id_nodo": "NODO-01",
                "humedad": 20.0,
                "temperatura": 24.0,
                "timestamp": self.ahora.isoformat(),
            },
            tokenHeader="TOK-NODO-01",
        )
        self.assertEqual(resp1["status_code"], 201)
        self.assertEqual(resp1["estado_valvula"], "abierta")
        self.assertEqual(resp1["estado_sector"], EstadoSector.EN_RIEGO.value)
        self.assertEqual(resp1["lamina_agua_mm"], 18.0)

        # 2. Lectura posterior alcanza humedad objetivo (62% >= 60%) y cierra electroválvula
        resp2 = self.controlador.postLecturaTelemetria(
            payload={
                "id_nodo": "NODO-01",
                "humedad": 62.0,
                "temperatura": 23.0,
                "timestamp": (self.ahora + timedelta(minutes=20)).isoformat(),
            },
            tokenHeader="TOK-NODO-01",
        )
        self.assertEqual(resp2["status_code"], 201)
        self.assertEqual(resp2["estado_valvula"], "cerrada")
        self.assertEqual(resp2["estado_sector"], EstadoSector.NORMAL.value)

    def test_cierre_seguridad_temporizador_after_45_min(self) -> None:
        # Inicia riego en SEC-01
        self.servicio.procesarTelemetria(
            idNodo="NODO-01",
            humedadSuelo=22.0,
            temperaturaSuelo=24.0,
            token="TOK-NODO-01",
            timestamp=self.ahora,
        )
        # Transcurren 2700 segundos (45 minutos) sin llegar a 60%
        ciclo = self.servicio.verificarTimeoutRiego(
            idSector="SEC-01",
            segundosTranscurridos=2700,
            humedadActual=48.0,
            timestamp=self.ahora + timedelta(minutes=45),
        )
        self.assertIsNotNone(ciclo)
        self.assertEqual(ciclo.estado, EstadoCicloRiego.ABORTADO_TIMEOUT)
        self.assertEqual(ciclo.motivoCierre, MotivoCierreRiego.TIEMPO_MAXIMO_CUMPLIDO)

    def test_mccabe_9_caminos_evaluar_riesgo_fitosanitario(self) -> None:
        sector = self.repo.obtenerSector("SEC-01")
        pronNormal = PronosticoMeteo(4.6, -74.0, 22.0, 70.0, 10.0, 12.0, self.ahora)

        # Camino 1: Lectura inválida (P1=True) -> None
        lecInvalida = LecturaTelemetria("L1", "NODO-01", "SEC-01", -5.0, 20.0, self.ahora, False)
        self.assertIsNone(self.servicio.evaluarRiesgoFitosanitario(sector, lecInvalida, pronNormal))

        # Camino 2: Riesgo de helada T_min <= 2.0 °C (P2=True)
        lecValida = LecturaTelemetria("L2", "NODO-01", "SEC-01", 40.0, 15.0, self.ahora, True)
        pronHelada = PronosticoMeteo(4.6, -74.0, 8.0, 70.0, 10.0, 1.5, self.ahora)
        alertaHelada = self.servicio.evaluarRiesgoFitosanitario(sector, lecValida, pronHelada)
        self.assertIsNotNone(alertaHelada)
        self.assertEqual(alertaHelada.tipoAlerta, TipoAlerta.RIESGO_HELADA)

        # Camino 3: Supresión anti-spam 12h para la misma alerta de helada (P8=True)
        alertaDuplicada = self.servicio.evaluarRiesgoFitosanitario(
            sector,
            LecturaTelemetria("L3", "NODO-01", "SEC-01", 40.0, 15.0, self.ahora + timedelta(hours=2), True),
            pronHelada,
        )
        self.assertIsNone(alertaDuplicada)

        # Camino 4: Temperatura suelo >= 35 °C pero horasCalorSuelo < 2 (P3=True, P4=False) -> None
        lecCalor = LecturaTelemetria("L4", "NODO-01", "SEC-01", 40.0, 36.0, self.ahora, True)
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(sector, lecCalor, pronNormal, horasCalorSuelo=1)
        )

        # Camino 5: Estrés térmico con temperatura suelo >= 35 °C durante >= 2h (P3=True, P4=True)
        alertaTermica = self.servicio.evaluarRiesgoFitosanitario(
            sector, lecCalor, pronNormal, horasCalorSuelo=2
        )
        self.assertIsNotNone(alertaTermica)
        self.assertEqual(alertaTermica.tipoAlerta, TipoAlerta.ESTRES_TERMICO)

        # Camino 6: Humedad relativa > 85% pero temperatura fuera de [18, 28] (P5=True, P6=False)
        pronHumedoFrio = PronosticoMeteo(4.6, -74.0, 14.0, 90.0, 30.0, 10.0, self.ahora)
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(
                sector, lecValida, pronHumedoFrio, horasCondicionFungo=6
            )
        )

        # Camino 7: HR > 85%, T en [18, 28], pero < 6 horas continuas (P5=True, P6=True, P7=False)
        pronFungo = PronosticoMeteo(4.6, -74.0, 23.0, 88.0, 30.0, 12.0, self.ahora)
        self.assertIsNone(
            self.servicio.evaluarRiesgoFitosanitario(
                sector, lecValida, pronFungo, horasCondicionFungo=4
            )
        )

        # Camino 8: Riesgo fitosanitario fúngico completo (P5=True, P6=True, P7=True)
        alertaFungo = self.servicio.evaluarRiesgoFitosanitario(
            sector, lecValida, pronFungo, horasCondicionFungo=6
        )
        self.assertIsNotNone(alertaFungo)
        self.assertEqual(alertaFungo.tipoAlerta, TipoAlerta.RIESGO_FITOSANITARIO)

        # Camino 9: Condiciones normales sin ningún riesgo activo -> None
        self.assertIsNone(self.servicio.evaluarRiesgoFitosanitario(sector, lecValida, pronNormal))

    def test_resiliencia_cache_apimeteo_y_decision_local_rnf03(self) -> None:
        # Primera llamada pobla el caché
        fallarApi = False

        def proveedorMock(lat: float, lon: float) -> PronosticoMeteo:
            if fallarApi:
                raise TimeoutError("Timeout de 5s en APIMeteo")
            return PronosticoMeteo(lat, lon, 21.0, 75.0, 80.0, 11.0, self.ahora)

        adaptadorConCache = AdaptadorAPIMeteo(proveedorExterno=proveedorMock)
        p1 = adaptadorConCache.consultarPronostico(4.6097, -74.0817, self.ahora)
        self.assertEqual(p1.probabilidadLluvia, 80.0)

        # Segunda llamada falla pero recupera de caché (< 3 horas)
        fallarApi = True
        p2 = adaptadorConCache.consultarPronostico(
            4.6097, -74.0817, self.ahora + timedelta(hours=2)
        )
        self.assertEqual(p2.probabilidadLluvia, 80.0)

    def test_fallo_servidor_valvulas_tras_3_reintentos_genera_alerta_critica(self) -> None:
        intentos = []

        def clienteValvulaFallido(sectorId: str, estadoObj: str) -> bool:
            intentos.append((sectorId, estadoObj))
            return False

        servicioConFallo = ServicioMonitoreoRiego(
            repositorio=self.repo,
            puertoMeteo=self.apiMeteo,
            puertoValvulas=AdaptadorServidorValvulas(clienteHttpSimulado=clienteValvulaFallido),
            observadores=[self.bitacora],
        )
        res = servicioConFallo.procesarTelemetria(
            idNodo="NODO-02",
            humedadSuelo=18.0,
            temperaturaSuelo=25.0,
            token="TOK-NODO-02",
            timestamp=self.ahora,
        )
        # Se verifican exactamente los 3 reintentos de IE-03
        self.assertEqual(len(intentos), 3)
        self.assertEqual(res.estadoSector, EstadoSector.ERROR_VALVULA.value)
        self.assertIsNotNone(res.alertaGenerada)
        self.assertEqual(res.alertaGenerada.tipoAlerta, TipoAlerta.FALLO_VALVULA)

    def test_seguridad_token_invalido_401_y_rol_no_autorizado_403(self) -> None:
        # SEG-02: Token inválido devuelve 401
        r401 = self.controlador.postLecturaTelemetria(
            payload={"id_nodo": "NODO-01", "humedad": 40.0, "temperatura": 20.0},
            tokenHeader="TOKEN-FALSO",
        )
        self.assertEqual(r401["status_code"], 401)

        # SEG-01: Técnico agrícola intentando apagar un nodo recibe 403
        r403 = self.controlador.putEstadoNodo(
            idNodo="NODO-01",
            encendido=False,
            rolHeader=RolUsuario.TECNICO_AGRICOLA.value,
            usuarioEmail="tecnico@agritech.co",
        )
        self.assertEqual(r403["status_code"], 403)


if __name__ == "__main__":
    unittest.main()
