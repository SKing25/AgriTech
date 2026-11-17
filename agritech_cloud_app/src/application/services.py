"""Servicio de aplicación principal (Deep Module <<control>>): ServicioMonitoreoRiego."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from ..domain.entities import (
    AlertaTemprana,
    CicloRiego,
    LecturaTelemetria,
    PronosticoMeteo,
    SectorAgricola,
    SensorSuelo,
)
from ..domain.enums import (
    EstadoCicloRiego,
    EstadoSector,
    EstadoSensor,
    MotivoCierreRiego,
    NivelSeveridad,
    RolUsuario,
    TipoAlerta,
)
from ..domain.exceptions import (
    AccesoNoAutorizadoError,
    EntidadNoEncontradaError,
    FalloComunicacionValvulaError,
    TelemetriaFueraDeRangoError,
    TokenDispositivoInvalidoError,
)
from .ports import (
    IObservadorEvento,
    IPuertoAPIMeteo,
    IPuertoServidorValvulas,
    IRepositorioAgricola,
    ResultadoProcesamiento,
)
from .strategies import EstrategiaRiegoAgronomico, IEstrategiaRiego


class ServicioMonitoreoRiego:
    """Orquestador central de telemetría, control de riego y alertas tempranas."""

    def __init__(
        self,
        repositorio: IRepositorioAgricola,
        puertoMeteo: IPuertoAPIMeteo,
        puertoValvulas: IPuertoServidorValvulas,
        estrategiaRiego: Optional[IEstrategiaRiego] = None,
        observadores: Optional[List[IObservadorEvento]] = None,
    ) -> None:
        """Inicializa el servicio conservando agregación sobre estrategia y observadores."""
        self.repositorio: IRepositorioAgricola = repositorio
        self.puertoMeteo: IPuertoAPIMeteo = puertoMeteo
        self.puertoValvulas: IPuertoServidorValvulas = puertoValvulas
        self.estrategiaRiego: IEstrategiaRiego = estrategiaRiego or EstrategiaRiegoAgronomico()
        self.observadores: List[IObservadorEvento] = list(observadores) if observadores else []

    def suscribirObservador(self, observador: IObservadorEvento) -> None:
        """Suscribe un observador GoF si aún no está registrado."""
        if observador not in self.observadores:
            self.observadores.append(observador)

    def _notificarAlerta(self, alerta: AlertaTemprana) -> None:
        for observador in self.observadores:
            observador.actualizarAlerta(alerta)

    def _notificarAuditoria(
        self,
        usuario: str,
        operacion: str,
        detalle: str,
        timestamp: datetime,
    ) -> None:
        self.repositorio.registrarAuditoriaEnBD(usuario, operacion, detalle, timestamp)
        for observador in self.observadores:
            observador.registrarEventoAuditoria(usuario, operacion, detalle, timestamp)

    def _construirAlertaSiAplica(
        self,
        sector: SectorAgricola,
        tipo: TipoAlerta,
        severidad: NivelSeveridad,
        mensaje: str,
        timestamp: datetime,
    ) -> Optional[AlertaTemprana]:
        """Aplica regla anti-spam de 12 h por (idSector, tipoAlerta) antes de instanciar alerta."""
        if sector.tieneAlertaReciente(tipo, timestamp, ventanaHoras=12):
            return None
        return AlertaTemprana(
            idAlerta=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            idSector=sector.idSector,
            tipoAlerta=tipo,
            nivelSeveridad=severidad,
            mensaje=mensaje,
            timestampGeneracion=timestamp,
        )

    def _registrarFalloValvula(
        self,
        sector: SectorAgricola,
        ciclo: Optional[CicloRiego],
        humedadActual: float,
        duracionSegundos: int,
        timestamp: datetime,
        errorDetalle: str,
    ) -> AlertaTemprana:
        """Maneja degradación segura ante fallo de ServidorValvulas tras 3 reintentos."""
        if ciclo is not None and ciclo.estaActivo():
            ciclo.finalizar(
                humedadFinal=humedadActual,
                duracionSegundos=duracionSegundos,
                motivo=MotivoCierreRiego.FALLO_VALVULA,
                timestamp=timestamp,
            )
        alerta = AlertaTemprana(
            idAlerta=f"ALT-{uuid.uuid4().hex[:8].upper()}",
            idSector=sector.idSector,
            tipoAlerta=TipoAlerta.FALLO_VALVULA,
            nivelSeveridad=NivelSeveridad.CRITICA,
            mensaje=f"Fallo crítico de comunicación con ServidorValvulas en {sector.nombre}: {errorDetalle}",
            timestampGeneracion=timestamp,
        )
        sector.registrarAlerta(alerta)
        self._notificarAlerta(alerta)
        self._notificarAuditoria(
            "SISTEMA",
            "FALLO_VALVULA",
            f"Sector {sector.idSector}: {errorDetalle}",
            timestamp,
        )
        return alerta

    def calcularLaminaRiego(
        self,
        humedadActual: float,
        umbralMinimo: float,
        umbralCritico: float,
        umbralObjetivo: float,
        probLluvia: float,
        tempSuelo: float,
    ) -> float:
        """Delega el cálculo a IEstrategiaRiego manteniendo cohesión del módulo profundo."""
        return self.estrategiaRiego.calcularLaminaRiego(
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
        """Evalúa riesgo fitosanitario por precedencia estricta (v(G) = 9 <= 10, P = 8)."""
        if pronostico is not None:  # P1
            if pronostico.tempMinimaEsperada <= 2.0:  # P2
                return self._construirAlertaSiAplica(
                    sector,
                    TipoAlerta.HELADA,
                    NivelSeveridad.CRITICA,
                    f"Riesgo de helada ({pronostico.tempMinimaEsperada:.1f} °C) en {sector.nombre}.",
                    lectura.timestamp,
                )
        if lectura.temperaturaSuelo >= 35.0:  # P3
            if horasCalorSuelo >= 2:  # P4
                return self._construirAlertaSiAplica(
                    sector,
                    TipoAlerta.ESTRES_TERMICO,
                    NivelSeveridad.ADVERTENCIA,
                    f"Estrés térmico sostenido ({lectura.temperaturaSuelo:.1f} °C durante {horasCalorSuelo}h) en {sector.nombre}.",
                    lectura.timestamp,
                )
        if lectura.humedadRelativa > 85.0:  # P5
            if lectura.temperaturaAmbiente >= 18.0:  # P6
                if lectura.temperaturaAmbiente <= 28.0:  # P7
                    if horasCondicionFungo >= 6:  # P8
                        return self._construirAlertaSiAplica(
                            sector,
                            TipoAlerta.RIESGO_FUNGICO,
                            NivelSeveridad.CRITICA,
                            f"Riesgo fúngico sostenido (HR {lectura.humedadRelativa:.1f}%, {horasCondicionFungo}h) en {sector.nombre}.",
                            lectura.timestamp,
                        )
        return None

    def _evaluarCicloEnCurso(
        self,
        sector: SectorAgricola,
        cicloActivo: CicloRiego,
        humedadSuelo: float,
        timestamp: datetime,
    ) -> tuple[str, Optional[AlertaTemprana]]:
        """Verifica cierre por objetivo alcanzado (>=60%) o timeout (45 min = 2700 s)."""
        duracionSeg = max(0, int((timestamp - cicloActivo.fechaInicio).total_seconds()))
        if duracionSeg >= CicloRiego.MAX_DURACION_SEGUNDOS:
            motivo = MotivoCierreRiego.TIMEOUT_MAXIMO_45MIN
            accion = "RIEGO_ABORTADO_TIMEOUT"
        elif humedadSuelo >= sector.umbralObjetivo:
            motivo = MotivoCierreRiego.OBJETIVO_ALCANZADO
            accion = "RIEGO_FINALIZADO_OBJETIVO"
        else:
            cicloActivo.duracionSegundos = duracionSeg
            return "RIEGO_EN_CURSO", None

        try:
            cicloActivo.transicionarA(
                EstadoCicloRiego.REGANDO,
                subestado="VALVULA_SOLICITANDO_CIERRE",
            )
            self.puertoValvulas.desactivarValvula(sector.idSector)
            sector.cerrarCicloActivo(humedadSuelo, duracionSeg, motivo, timestamp)
            self._notificarAuditoria(
                "SISTEMA",
                accion,
                f"Sector {sector.idSector}, Ciclo {cicloActivo.idCiclo}, humedad={humedadSuelo:.1f}%, duracion={duracionSeg}s",
                timestamp,
            )
            return accion, None
        except FalloComunicacionValvulaError as exc:
            alertaFallo = self._registrarFalloValvula(
                sector, cicloActivo, humedadSuelo, duracionSeg, timestamp, str(exc)
            )
            return "ERROR_VALVULA", alertaFallo

    def _decidirNuevoRiego(
        self,
        sector: SectorAgricola,
        humedadSuelo: float,
        temperaturaSuelo: float,
        pronostico: PronosticoMeteo,
        timestamp: datetime,
    ) -> tuple[str, Optional[AlertaTemprana]]:
        """Aplica IEstrategiaRiego y controla transición EVALUANDO -> POSPUESTO / REGANDO."""
        lamina = self.calcularLaminaRiego(
            humedadActual=humedadSuelo,
            umbralMinimo=sector.umbralMinimo,
            umbralCritico=sector.umbralCritico,
            umbralObjetivo=sector.umbralObjetivo,
            probLluvia=pronostico.probabilidadLluvia,
            tempSuelo=temperaturaSuelo,
        )
        cicloExistente = sector.obtenerCicloActivo()

        if sector.estadoActual == EstadoSector.ERROR_VALVULA:
            return "SECTOR_BLOQUEADO_ERROR_VALVULA", None

        if humedadSuelo >= sector.umbralMinimo:
            if cicloExistente is not None and cicloExistente.estado == EstadoCicloRiego.POSPUESTO:
                cicloExistente.finalizar(
                    humedadFinal=humedadSuelo,
                    duracionSegundos=0,
                    motivo=MotivoCierreRiego.OBJETIVO_ALCANZADO,
                    timestamp=timestamp,
                )
            if sector.estadoActual != EstadoSector.ERROR_VALVULA:
                sector.estadoActual = EstadoSector.OPTIMO
            return "MONITOREO_OPTIMO", None

        if lamina == 0.0:
            if cicloExistente is None:
                ciclo = CicloRiego(
                    idCiclo=f"CIC-{uuid.uuid4().hex[:8].upper()}",
                    idSector=sector.idSector,
                    estado=EstadoCicloRiego.EVALUANDO,
                    laminaAplicadaMm=0.0,
                    humedadInicial=humedadSuelo,
                    fechaInicio=timestamp,
                )
                ciclo.transicionarA(
                    EstadoCicloRiego.POSPUESTO,
                    motivo=MotivoCierreRiego.LLUVIA_INMINENTE,
                )
                sector.iniciarCicloRiego(ciclo)
            elif sector.estadoActual != EstadoSector.ERROR_VALVULA:
                sector.estadoActual = EstadoSector.RIEGO_POSPUESTO
            self._notificarAuditoria(
                "SISTEMA",
                "RIEGO_POSPUESTO_LLUVIA",
                f"Sector {sector.idSector}: H={humedadSuelo:.1f}%, probLluvia={pronostico.probabilidadLluvia:.1f}%",
                timestamp,
            )
            return "RIEGO_POSPUESTO_LLUVIA", None

        if cicloExistente is not None and cicloExistente.estado == EstadoCicloRiego.POSPUESTO:
            cicloExistente.transicionarA(EstadoCicloRiego.EVALUANDO)
            ciclo = cicloExistente
            ciclo.laminaAplicadaMm = lamina
            ciclo.fechaInicio = timestamp
        else:
            ciclo = CicloRiego(
                idCiclo=f"CIC-{uuid.uuid4().hex[:8].upper()}",
                idSector=sector.idSector,
                estado=EstadoCicloRiego.EVALUANDO,
                laminaAplicadaMm=lamina,
                humedadInicial=humedadSuelo,
                fechaInicio=timestamp,
            )
            sector.iniciarCicloRiego(ciclo)

        duracionObjetivoSeg = min(CicloRiego.MAX_DURACION_SEGUNDOS, max(300, int(lamina * 90)))
        try:
            ciclo.transicionarA(
                EstadoCicloRiego.REGANDO,
                subestado="VALVULA_SOLICITANDO_APERTURA",
            )
            self.puertoValvulas.activarValvula(sector.idSector, duracionObjetivoSeg)
            ciclo.transicionarA(
                EstadoCicloRiego.REGANDO,
                subestado="FLUJO_ACTIVO",
            )
            if sector.estadoActual != EstadoSector.ERROR_VALVULA:
                sector.estadoActual = EstadoSector.REGANDO
            self._notificarAuditoria(
                "SISTEMA",
                "RIEGO_INICIADO",
                f"Sector {sector.idSector}, Ciclo {ciclo.idCiclo}, lamina={lamina:.2f}mm, H={humedadSuelo:.1f}%",
                timestamp,
            )
            return "RIEGO_INICIADO", None
        except FalloComunicacionValvulaError as exc:
            alertaFallo = self._registrarFalloValvula(
                sector, ciclo, humedadSuelo, 0, timestamp, str(exc)
            )
            return "ERROR_VALVULA", alertaFallo

    def procesarTelemetria(
        self,
        idNodo: str,
        humedadSuelo: float,
        temperaturaSuelo: float,
        token: str,
        timestamp: datetime,
        horasCondicionFungo: int = 0,
        horasCalorSuelo: int = 0,
        temperaturaAmbiente: Optional[float] = None,
        humedadRelativa: Optional[float] = None,
    ) -> ResultadoProcesamiento:
        """Caso de uso CU-04: ingesta, validación, decisión de riego y detección fitosanitaria."""
        sector = self.repositorio.obtenerSectorPorNodo(idNodo)
        sensor = self.repositorio.obtenerSensor(idNodo)
        if sector is None or sensor is None:
            raise EntidadNoEncontradaError(f"NodoSensorIoT no registrado: {idNodo}")

        if token != sensor.tokenAutenticacion:
            self._notificarAuditoria(
                f"NODO:{idNodo}",
                "RECHAZO_TOKEN_401",
                f"Token inválido recibido para nodo {idNodo}",
                timestamp,
            )
            raise TokenDispositivoInvalidoError(f"Token inválido para dispositivo {idNodo}")

        if not SensorSuelo.validarTrama(humedadSuelo, temperaturaSuelo):
            raise TelemetriaFueraDeRangoError(
                f"Telemetría fuera de rango físico: humedad={humedadSuelo}%, temp={temperaturaSuelo}°C"
            )

        if sensor.estadoOperativo == EstadoSensor.APAGADO:
            return ResultadoProcesamiento(
                idSector=sector.idSector,
                estadoSector=sector.estadoActual,
                accionTomada="SENSOR_APAGADO",
                cicloActivo=sector.obtenerCicloActivo(),
            )

        tempAmb = temperaturaAmbiente if temperaturaAmbiente is not None else temperaturaSuelo
        hrAmb = humedadRelativa if humedadRelativa is not None else 68.0
        lectura = LecturaTelemetria(
            idLectura=f"LEC-{uuid.uuid4().hex[:8].upper()}",
            idNodo=idNodo,
            idSector=sector.idSector,
            humedadSuelo=round(float(humedadSuelo), 2),
            temperaturaSuelo=round(float(temperaturaSuelo), 2),
            temperaturaAmbiente=round(float(tempAmb), 2),
            humedadRelativa=round(float(hrAmb), 2),
            timestamp=timestamp,
            esValida=True,
        )
        sector.registrarLectura(lectura)

        pronostico = self.puertoMeteo.consultarPronostico(
            sector.latitud, sector.longitud, instanteActual=timestamp
        )

        cicloActivo = sector.obtenerCicloActivo()
        if cicloActivo is not None and cicloActivo.estado == EstadoCicloRiego.REGANDO:
            accion, alertaValvula = self._evaluarCicloEnCurso(
                sector, cicloActivo, lectura.humedadSuelo, timestamp
            )
        else:
            accion, alertaValvula = self._decidirNuevoRiego(
                sector, lectura.humedadSuelo, lectura.temperaturaSuelo, pronostico, timestamp
            )

        alertaFito = self.evaluarRiesgoFitosanitario(
            sector,
            lectura,
            pronostico,
            horasCondicionFungo=horasCondicionFungo,
            horasCalorSuelo=horasCalorSuelo,
        )
        if alertaFito is not None:
            sector.registrarAlerta(alertaFito)
            self._notificarAlerta(alertaFito)

        self.repositorio.guardarSector(sector)
        return ResultadoProcesamiento(
            idSector=sector.idSector,
            estadoSector=sector.estadoActual,
            accionTomada=accion,
            cicloActivo=sector.obtenerCicloActivo(),
            alertaGenerada=alertaValvula or alertaFito,
            pronosticoUtilizado=pronostico,
        )

    def verificarTimeoutRiego(
        self,
        idSector: str,
        segundosTranscurridos: int,
        humedadActual: float,
        timestamp: datetime,
    ) -> Optional[CicloRiego]:
        """Evalúa cierre por seguridad after(45 min = 2700 s) u objetivo alcanzado."""
        sector = self.repositorio.obtenerSector(idSector)
        if sector is None:
            raise EntidadNoEncontradaError(f"SectorAgricola no encontrado: {idSector}")
        ciclo = sector.obtenerCicloActivo()
        if ciclo is None or ciclo.estado != EstadoCicloRiego.REGANDO:
            return None

        if segundosTranscurridos >= CicloRiego.MAX_DURACION_SEGUNDOS:
            motivo = MotivoCierreRiego.TIMEOUT_MAXIMO_45MIN
            operacion = "RIEGO_ABORTADO_TIMEOUT"
        elif humedadActual >= sector.umbralObjetivo:
            motivo = MotivoCierreRiego.OBJETIVO_ALCANZADO
            operacion = "RIEGO_FINALIZADO_OBJETIVO"
        else:
            ciclo.duracionSegundos = max(0, segundosTranscurridos)
            self.repositorio.guardarSector(sector)
            return None

        try:
            ciclo.transicionarA(EstadoCicloRiego.REGANDO, subestado="VALVULA_SOLICITANDO_CIERRE")
            self.puertoValvulas.desactivarValvula(sector.idSector)
            cerrado = sector.cerrarCicloActivo(
                humedadFinal=humedadActual,
                duracionSegundos=segundosTranscurridos,
                motivo=motivo,
                timestamp=timestamp,
            )
            self._notificarAuditoria(
                "SISTEMA",
                operacion,
                f"Sector {sector.idSector}, Ciclo {cerrado.idCiclo}, t={segundosTranscurridos}s, H={humedadActual:.1f}%",
                timestamp,
            )
            self.repositorio.guardarSector(sector)
            return cerrado
        except FalloComunicacionValvulaError as exc:
            self._registrarFalloValvula(
                sector, ciclo, humedadActual, segundosTranscurridos, timestamp, str(exc)
            )
            self.repositorio.guardarSector(sector)
            return ciclo

    def cambiarEstadoNodo(
        self,
        idNodo: str,
        encendido: bool,
        rolUsuario: RolUsuario,
        usuarioEmail: str,
        timestamp: datetime,
    ) -> SensorSuelo:
        """Habilita o apaga un NodoSensorIoT bajo control RBAC (GESTOR_SENSORES o ADMINISTRADOR)."""
        if rolUsuario not in {RolUsuario.GESTOR_SENSORES, RolUsuario.ADMINISTRADOR}:
            raise AccesoNoAutorizadoError(
                f"El rol {rolUsuario.value} no tiene permiso para operar nodos IoT."
            )
        sector = self.repositorio.obtenerSectorPorNodo(idNodo)
        if sector is None:
            raise EntidadNoEncontradaError(f"NodoSensorIoT no encontrado: {idNodo}")
        sensor = next((s for s in sector.sensores if s.idNodo == idNodo), None)
        if sensor is None:
            raise EntidadNoEncontradaError(f"SensorSuelo no encontrado en sector: {idNodo}")
        sensor.cambiarEstadoOperativo(encendido)
        self.repositorio.guardarSector(sector)
        self._notificarAuditoria(
            usuarioEmail,
            "CAMBIO_ESTADO_NODO",
            f"Nodo {idNodo} -> {sensor.estadoOperativo.value}",
            timestamp,
        )
        return sensor

    def configurarUmbralesSector(
        self,
        idSector: str,
        critico: float,
        minimo: float,
        objetivo: float,
        rolUsuario: RolUsuario,
        usuarioEmail: str,
        timestamp: datetime,
    ) -> SectorAgricola:
        """Actualiza umbrales agronómicos bajo RBAC (TECNICO_AGRICOLA o ADMINISTRADOR)."""
        if rolUsuario not in {RolUsuario.TECNICO_AGRICOLA, RolUsuario.ADMINISTRADOR}:
            raise AccesoNoAutorizadoError(
                f"El rol {rolUsuario.value} no tiene permiso para configurar umbrales agronómicos."
            )
        sector = self.repositorio.obtenerSector(idSector)
        if sector is None:
            raise EntidadNoEncontradaError(f"SectorAgricola no encontrado: {idSector}")
        sector.configurarUmbrales(critico=critico, minimo=minimo, objetivo=objetivo)
        self.repositorio.guardarSector(sector)
        self._notificarAuditoria(
            usuarioEmail,
            "CONFIGURAR_UMBRALES",
            f"Sector {idSector}: critico={critico}%, minimo={minimo}%, objetivo={objetivo}%",
            timestamp,
        )
        return sector

    def restablecerErrorValvula(
        self,
        idSector: str,
        rolUsuario: RolUsuario,
        usuarioEmail: str,
        timestamp: datetime,
    ) -> SectorAgricola:
        """Restablece el estado ERROR_VALVULA tras intervención técnica (TECNICO_AGRICOLA o ADMINISTRADOR)."""
        if rolUsuario not in {RolUsuario.TECNICO_AGRICOLA, RolUsuario.ADMINISTRADOR}:
            raise AccesoNoAutorizadoError(
                f"El rol {rolUsuario.value} no tiene permiso para restablecer válvulas."
            )
        sector = self.repositorio.obtenerSector(idSector)
        if sector is None:
            raise EntidadNoEncontradaError(f"SectorAgricola no encontrado: {idSector}")
        ultima = sector.obtenerUltimaLecturaValida()
        if ultima is not None and ultima.humedadSuelo < sector.umbralMinimo:
            sector.estadoActual = EstadoSector.REQUIERE_RIEGO
        else:
            sector.estadoActual = EstadoSector.OPTIMO
        self.repositorio.guardarSector(sector)
        self._notificarAuditoria(
            usuarioEmail,
            "RESTABLECER_VALVULA",
            f"Sector {idSector} restablecido a {sector.estadoActual.value}",
            timestamp,
        )
        return sector
