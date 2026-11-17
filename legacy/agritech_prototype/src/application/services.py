"""Módulo profundo ServicioMonitoreoRiego con orquestación de riego, telemetría y alertas."""
from datetime import datetime
from typing import List, Optional
import uuid

from src.application.ports import (
    IObservadorAlerta,
    IPuertoAPIMeteo,
    IPuertoServidorValvulas,
    IRepositorioSectores,
    ResultadoProcesamiento,
)
from src.application.strategies import EstrategiaRiegoAgronomico, IEstrategiaRiego
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
    EstadoSector,
    MotivoCierreRiego,
    RolUsuario,
    TipoAlerta,
)
from src.domain.exceptions import (
    AccesoNoAutorizadoError,
    DispositivoNoAutorizadoError,
    ErrorComunicacionAPIMeteo,
    ErrorComunicacionValvula,
)


class ServicioMonitoreoRiego:
    """
    Módulo Profundo (Deep Module) de AgriTech Precision.
    Expone una interfaz mínima sobre la Seam de aplicación y oculta la complejidad de:
    - Validación de telemetría y autenticación por token de dispositivo (SEG-02).
    - Evaluación concurrente de riesgo fitosanitario (RF-06) y ciclo de riego (RF-04, RF-05).
    - Máquina de estados de CicloRiego y temporizador after(45 min).
    - Resiliencia ante fallos de APIMeteo (RNF-03) y ServidorValvulas (IE-03).
    """

    def __init__(
        self,
        repositorio: IRepositorioSectores,
        puertoMeteo: IPuertoAPIMeteo,
        puertoValvulas: IPuertoServidorValvulas,
        estrategiaRiego: Optional[IEstrategiaRiego] = None,
        observadores: Optional[List[IObservadorAlerta]] = None,
    ) -> None:
        self._repositorio = repositorio
        self._puertoMeteo = puertoMeteo
        self._puertoValvulas = puertoValvulas
        self._estrategiaRiego = estrategiaRiego or EstrategiaRiegoAgronomico()
        self._observadores: List[IObservadorAlerta] = list(observadores or [])

    def suscribirObservador(self, observador: IObservadorAlerta) -> None:
        """Suscribe un nuevo observador de alertas/auditoría (Patrón GoF Observer)."""
        self._observadores.append(observador)

    def _notificarAlerta(self, alerta: AlertaTemprana) -> None:
        for obs in self._observadores:
            obs.actualizarAlerta(alerta)

    def _auditar(
        self, usuario: str, operacion: str, detalle: str, timestamp: datetime
    ) -> None:
        for obs in self._observadores:
            obs.registrarEventoAuditoria(usuario, operacion, detalle, timestamp)

    def calcularLaminaRiego(
        self,
        humedadActual: float,
        umbralMinimo: float,
        umbralCritico: float,
        umbralObjetivo: float,
        probLluvia: float,
        tempSuelo: float,
    ) -> float:
        """Delega el cálculo algorítmico de lámina de riego a la estrategia configurada."""
        return self._estrategiaRiego.calcularLaminaRiego(
            humedadActual=humedadActual,
            umbralMinimo=umbralMinimo,
            umbralCritico=umbralCritico,
            umbralObjetivo=umbralObjetivo,
            probLluvia=probLluvia,
            tempSuelo=tempSuelo,
        )

    def evaluarRiesgoFitosanitario(
        self,
        sector: SectorAgricola,
        lectura: LecturaTelemetria,
        pronostico: Optional[PronosticoMeteo],
        horasCondicionFungo: int = 0,
        horasCalorSuelo: int = 0,
    ) -> Optional[AlertaTemprana]:
        """
        Evalúa las reglas agroclimáticas de RF-06 para emitir alertas tempranas.
        Complejidad Ciclomática de McCabe: P = 8 nodos predicado -> v(G) = P + 1 = 9 <= 10 (RNF-06).
        """
        # P1: Descartar si la lectura no es válida
        if not lectura.esValida:
            return None

        tipoDetectado: Optional[TipoAlerta] = None
        severidad = "MEDIA"
        mensaje = ""

        # P2: Riesgo de helada si existe pronóstico y temp mínima <= 2.0 °C (RF-06c)
        if pronostico is not None and pronostico.temperaturaMinimaPronosticada <= 2.0:
            tipoDetectado = TipoAlerta.RIESGO_HELADA
            severidad = "ALTA"
            mensaje = (
                f"Riesgo de helada en {sector.nombre}: "
                f"mínima pronosticada {pronostico.temperaturaMinimaPronosticada} °C <= 2.0 °C."
            )
        # P3: Evaluación de temperatura del suelo >= 35.0 °C para estrés térmico (RF-06b)
        elif lectura.temperaturaSuelo >= 35.0:
            # P4: Persistente durante al menos 2 horas continuas
            if horasCalorSuelo >= 2:
                tipoDetectado = TipoAlerta.ESTRES_TERMICO
                severidad = "ALTA"
                mensaje = (
                    f"Estrés térmico en {sector.nombre}: "
                    f"temperatura del suelo {lectura.temperaturaSuelo} °C durante {horasCalorSuelo} h."
                )
        # P5: Evaluación de humedad relativa > 85% para riesgo fitosanitario (RF-06a)
        elif pronostico is not None and pronostico.humedadRelativaAire > 85.0:
            # P6: Temperatura ambiente entre 18 °C y 28 °C
            if 18.0 <= pronostico.temperaturaAmbiente <= 28.0:
                # P7: Condición sostenida durante al menos 6 horas continuas
                if horasCondicionFungo >= 6:
                    tipoDetectado = TipoAlerta.RIESGO_FITOSANITARIO
                    severidad = "ALTA"
                    mensaje = (
                        f"Riesgo fitosanitario fúngico en {sector.nombre}: "
                        f"HR {pronostico.humedadRelativaAire}% y T {pronostico.temperaturaAmbiente} °C "
                        f"por {horasCondicionFungo} h."
                    )

        # P8: Verificar si se detectó algún riesgo y no existe alerta duplicada en las últimas 12 h
        if tipoDetectado is None or sector.tieneAlertaReciente(
            tipoDetectado, lectura.timestamp, ventanaHoras=12
        ):
            return None

        alerta = AlertaTemprana(
            idAlerta=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            idSector=sector.idSector,
            tipoAlerta=tipoDetectado,
            severidad=severidad,
            mensaje=mensaje,
            timestamp=lectura.timestamp,
        )
        sector.registrarAlerta(alerta)
        self._notificarAlerta(alerta)
        return alerta

    def procesarTelemetria(
        self,
        idNodo: str,
        humedadSuelo: float,
        temperaturaSuelo: float,
        token: str,
        timestamp: datetime,
        horasCondicionFungo: int = 0,
        horasCalorSuelo: int = 0,
    ) -> ResultadoProcesamiento:
        """
        Caso de uso principal CU-04: procesa una trama de telemetría entrante (F9, IE-02),
        ejecuta la validación, evalúa alertas y acciona la máquina de estados de CicloRiego.
        """
        sensor = self._repositorio.obtenerSensor(idNodo)
        if sensor is None or sensor.tokenDispositivo != token:
            self._auditar(
                idNodo,
                "RECHAZO_AUTH_DISPOSITIVO",
                f"Intento no autorizado desde nodo {idNodo}",
                timestamp,
            )
            raise DispositivoNoAutorizadoError(
                f"Dispositivo {idNodo} no registrado o token inválido (SEG-02)."
            )

        sector = self._repositorio.obtenerSector(sensor.idSector)
        if sector is None:
            raise DispositivoNoAutorizadoError(
                f"Sector {sensor.idSector} no encontrado para el nodo {idNodo}."
            )

        # HU-01 CA2 / HU-02 CA3: Nodo apagado no procesa ni almacena lecturas
        if not sensor.encendido:
            return ResultadoProcesamiento(
                codigoHttp=200,
                lecturaValida=False,
                estadoSector=sector.estadoSector.value,
                estadoValvula=sector.estadoValvula,
                laminaAguaMm=0.0,
                cicloRiego=None,
                alertaGenerada=None,
                mensaje=f"Nodo {idNodo} apagado; lectura ignorada.",
            )

        esValida = SensorSuelo.validarTrama(humedadSuelo, temperaturaSuelo)
        lectura = LecturaTelemetria(
            idLectura=f"LEC-{uuid.uuid4().hex[:8].upper()}",
            idNodo=idNodo,
            idSector=sector.idSector,
            humedadSuelo=humedadSuelo if humedadSuelo is not None else -1.0,
            temperaturaSuelo=temperaturaSuelo if temperaturaSuelo is not None else -999.0,
            timestamp=timestamp,
            esValida=esValida,
        )

        # Flujo Alternativo A1: Lectura inválida (fuera de rango)
        if not esValida:
            self._auditar(
                idNodo,
                "LECTURA_INVALIDA_DESCARTADA",
                f"H={humedadSuelo}, T={temperaturaSuelo} fuera de rango en {sector.idSector}",
                timestamp,
            )
            return ResultadoProcesamiento(
                codigoHttp=400,
                lecturaValida=False,
                estadoSector=sector.estadoSector.value,
                estadoValvula=sector.estadoValvula,
                laminaAguaMm=0.0,
                cicloRiego=sector.obtenerCicloActivo(),
                alertaGenerada=None,
                mensaje="Lectura inválida descartada (fuera de rango físico).",
            )

        # Almacenar lectura válida (Paso 3 de CU-04)
        sector.registrarLectura(lectura)

        # Si ya hay un CicloRiego activo en el sector, verificar si alcanzó la humedad objetivo
        cicloActivo = sector.obtenerCicloActivo()
        if cicloActivo is not None:
            cicloActivo.transicionarA(EstadoCicloRiego.VERIFICANDO_HUMEDAD_OBJETIVO)
            if humedadSuelo >= sector.umbralObjetivo:
                duracion = max(
                    1, int((timestamp - cicloActivo.fechaInicio).total_seconds())
                )
                try:
                    self._puertoValvulas.desactivarValvula(sector.idSector)
                    cicloCerrado = sector.cerrarCicloActivo(
                        humedadFinal=humedadSuelo,
                        duracionSegundos=duracion,
                        motivo=MotivoCierreRiego.HUMEDAD_OBJETIVO_ALCANZADA,
                        timestamp=timestamp,
                    )
                    self._auditar(
                        "SISTEMA",
                        "CIERRE_RIEGO_OBJETIVO",
                        f"Ciclo {cicloCerrado.idCiclo} completado en {duracion}s",
                        timestamp,
                    )
                except ErrorComunicacionValvula as exc:
                    cicloCerrado = sector.cerrarCicloActivo(
                        humedadFinal=humedadSuelo,
                        duracionSegundos=duracion,
                        motivo=MotivoCierreRiego.ERROR_COMUNICACION_VALVULA,
                        timestamp=timestamp,
                    )
                    alertaFallo = AlertaTemprana(
                        idAlerta=f"ALT-{uuid.uuid4().hex[:8].upper()}",
                        idSector=sector.idSector,
                        tipoAlerta=TipoAlerta.FALLO_VALVULA,
                        severidad="CRITICA",
                        mensaje=str(exc),
                        timestamp=timestamp,
                    )
                    sector.registrarAlerta(alertaFallo)
                    self._notificarAlerta(alertaFallo)
                self._repositorio.guardarSector(sector)
                return ResultadoProcesamiento(
                    codigoHttp=201,
                    lecturaValida=True,
                    estadoSector=sector.estadoSector.value,
                    estadoValvula=sector.estadoValvula,
                    laminaAguaMm=cicloCerrado.laminaAguaMm,
                    cicloRiego=cicloCerrado,
                    alertaGenerada=None,
                    mensaje="Humedad objetivo alcanzada; electroválvula cerrada.",
                )
            else:
                cicloActivo.transicionarA(EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO)
                self._repositorio.guardarSector(sector)
                return ResultadoProcesamiento(
                    codigoHttp=201,
                    lecturaValida=True,
                    estadoSector=sector.estadoSector.value,
                    estadoValvula=sector.estadoValvula,
                    laminaAguaMm=cicloActivo.laminaAguaMm,
                    cicloRiego=cicloActivo,
                    alertaGenerada=None,
                    mensaje="Ciclo de riego continúa activo.",
                )

        # Consulta meteorológica para ramas concurrentes (Alertas RF-06 y Riego RF-04/RF-05)
        pronostico: Optional[PronosticoMeteo] = None
        try:
            pronostico = self._puertoMeteo.consultarPronostico(
                sector.latitud, sector.longitud
            )
        except ErrorComunicacionAPIMeteo:
            # Flujo A5 / RNF-03: Degradación elegante, decide con lectura local
            pronostico = None

        # Rama 1 del Fork: Evaluación de riesgo fitosanitario (RF-06)
        alerta = self.evaluarRiesgoFitosanitario(
            sector=sector,
            lectura=lectura,
            pronostico=pronostico,
            horasCondicionFungo=horasCondicionFungo,
            horasCalorSuelo=horasCalorSuelo,
        )

        # Rama 2 del Fork: Evaluación de umbral de riego y máquina de estados CicloRiego
        ciclo = CicloRiego(
            idCiclo=f"CR-{uuid.uuid4().hex[:8].upper()}",
            idSector=sector.idSector,
            idValvula=sector.idValvula,
            fechaInicio=timestamp,
            humedadInicial=humedadSuelo,
        )
        ciclo.transicionarA(EstadoCicloRiego.EVALUANDO_UMBRAL)

        # Flujo A3: Humedad >= umbralMinimo -> no requiere riego
        if humedadSuelo >= sector.umbralMinimo:
            ciclo.transicionarA(EstadoCicloRiego.INACTIVO)
            self._repositorio.guardarSector(sector)
            return ResultadoProcesamiento(
                codigoHttp=201,
                lecturaValida=True,
                estadoSector=sector.estadoSector.value,
                estadoValvula=sector.estadoValvula,
                laminaAguaMm=0.0,
                cicloRiego=None,
                alertaGenerada=alerta,
                mensaje="Humedad suficiente; no se requiere riego.",
            )

        # Humedad < umbralMinimo -> pasa a CONSULTANDO_METEO
        ciclo.transicionarA(EstadoCicloRiego.CONSULTANDO_METEO)
        probLluvia = pronostico.probabilidadLluvia if pronostico is not None else 0.0
        laminaMm = self.calcularLaminaRiego(
            humedadActual=humedadSuelo,
            umbralMinimo=sector.umbralMinimo,
            umbralCritico=sector.umbralCritico,
            umbralObjetivo=sector.umbralObjetivo,
            probLluvia=probLluvia,
            tempSuelo=temperaturaSuelo,
        )

        # Flujo A2: Lluvia prevista (> 70%) y humedad no crítica (>= 15%) -> posponer riego
        if laminaMm == 0.0:
            ciclo.transicionarA(
                EstadoCicloRiego.POSPUESTO_POR_LLUVIA,
                MotivoCierreRiego.POSPUESTO_POR_LLUVIA,
            )
            ciclo.fechaFin = timestamp
            sector.iniciarCicloRiego(ciclo)
            self._auditar(
                "SISTEMA",
                "RIEGO_POSPUESTO_LLUVIA",
                f"Riego pospuesto en {sector.idSector} (probLluvia={probLluvia}%)",
                timestamp,
            )
            self._repositorio.guardarSector(sector)
            return ResultadoProcesamiento(
                codigoHttp=201,
                lecturaValida=True,
                estadoSector=sector.estadoSector.value,
                estadoValvula=sector.estadoValvula,
                laminaAguaMm=0.0,
                cicloRiego=ciclo,
                alertaGenerada=alerta,
                mensaje="Riego pospuesto por pronóstico de lluvia > 70%.",
            )

        # Riego procede -> ABRIENDO_VALVULA
        ciclo.laminaAguaMm = laminaMm
        ciclo.transicionarA(EstadoCicloRiego.ABRIENDO_VALVULA)
        try:
            self._puertoValvulas.activarValvula(
                sectorId=sector.idSector,
                duracionSegundos=CicloRiego.MAX_DURACION_SEGUNDOS,
            )
            ciclo.transicionarA(EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO)
            sector.iniciarCicloRiego(ciclo)
            self._auditar(
                "SISTEMA",
                "APERTURA_VALVULA_RIEGO",
                f"Ciclo {ciclo.idCiclo} iniciado en {sector.idSector} (lámina {laminaMm} mm)",
                timestamp,
            )
        except ErrorComunicacionValvula as exc:
            ciclo.transicionarA(
                EstadoCicloRiego.FALLO_VALVULA,
                MotivoCierreRiego.ERROR_COMUNICACION_VALVULA,
            )
            ciclo.fechaFin = timestamp
            sector.ciclosRiego.append(ciclo)
            sector.estadoSector = EstadoSector.ERROR_VALVULA
            alertaValvula = AlertaTemprana(
                idAlerta=f"ALT-{uuid.uuid4().hex[:8].upper()}",
                idSector=sector.idSector,
                tipoAlerta=TipoAlerta.FALLO_VALVULA,
                severidad="CRITICA",
                mensaje=f"Fallo de ServidorValvulas en {sector.idSector}: {exc}",
                timestamp=timestamp,
            )
            sector.registrarAlerta(alertaValvula)
            self._notificarAlerta(alertaValvula)
            alerta = alertaValvula

        self._repositorio.guardarSector(sector)
        return ResultadoProcesamiento(
            codigoHttp=201,
            lecturaValida=True,
            estadoSector=sector.estadoSector.value,
            estadoValvula=sector.estadoValvula,
            laminaAguaMm=ciclo.laminaAguaMm,
            cicloRiego=ciclo,
            alertaGenerada=alerta,
            mensaje="Telemetría procesada y ciclo de riego evaluado.",
        )

    def verificarTimeoutRiego(
        self,
        idSector: str,
        segundosTranscurridos: int,
        humedadActual: float,
        timestamp: datetime,
    ) -> Optional[CicloRiego]:
        """
        Ejecuta la guarda del temporizador UML after(45 min) = 2700 segundos (Flujo A4, RF-04).
        Si segundosTranscurridos >= 2700, fuerza el cierre por seguridad y emite alerta.
        """
        sector = self._repositorio.obtenerSector(idSector)
        if sector is None:
            return None
        ciclo = sector.obtenerCicloActivo()
        if ciclo is None:
            return None
        if segundosTranscurridos < CicloRiego.MAX_DURACION_SEGUNDOS:
            return ciclo

        self._puertoValvulas.desactivarValvula(idSector)
        cicloCerrado = sector.cerrarCicloActivo(
            humedadFinal=humedadActual,
            duracionSegundos=segundosTranscurridos,
            motivo=MotivoCierreRiego.TIEMPO_MAXIMO_CUMPLIDO,
            timestamp=timestamp,
        )
        alertaTimeout = AlertaTemprana(
            idAlerta=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            idSector=sector.idSector,
            tipoAlerta=TipoAlerta.FALLO_VALVULA,
            severidad="ALTA",
            mensaje=(
                f"Cierre de seguridad after(45 min) en {sector.nombre}: "
                f"no se alcanzó humedad objetivo ({sector.umbralObjetivo}%)."
            ),
            timestamp=timestamp,
        )
        sector.registrarAlerta(alertaTimeout)
        self._notificarAlerta(alertaTimeout)
        self._auditar(
            "SISTEMA",
            "CIERRE_SEGURIDAD_TIMEOUT_45M",
            f"Ciclo {cicloCerrado.idCiclo} cerrado tras {segundosTranscurridos}s",
            timestamp,
        )
        self._repositorio.guardarSector(sector)
        return cicloCerrado

    def cambiarEstadoNodo(
        self,
        idNodo: str,
        encendido: bool,
        rolUsuario: RolUsuario,
        usuarioEmail: str,
        timestamp: datetime,
    ) -> SensorSuelo:
        """Cambia el estado encendido/apagado de un nodo validando rol GESTOR_SENSORES (SEG-01, RF-02)."""
        if rolUsuario != RolUsuario.GESTOR_SENSORES:
            self._auditar(
                usuarioEmail,
                "ACCESO_DENEGADO_403",
                f"Rol {rolUsuario.value} intentó cambiar estado de {idNodo}",
                timestamp,
            )
            raise AccesoNoAutorizadoError(
                f"Código 403: El rol {rolUsuario.value} no tiene permiso para controlar nodos (SEG-01)."
            )
        sensor = self._repositorio.obtenerSensor(idNodo)
        if sensor is None:
            raise DispositivoNoAutorizadoError(f"Nodo {idNodo} no existe.")
        sensor.cambiarEstadoOperativo(encendido)
        self._auditar(
            usuarioEmail,
            "CAMBIO_ESTADO_NODO",
            f"Nodo {idNodo} cambiado a encendido={encendido}",
            timestamp,
        )
        return sensor
