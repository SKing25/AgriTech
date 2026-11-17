"""Entidades de negocio y máquina de estados de AgriTech Precision."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from src.domain.enums import (
    EstadoCicloRiego,
    EstadoSector,
    MotivoCierreRiego,
    TipoAlerta,
)
from src.domain.exceptions import (
    TransicionEstadoInvalidaError,
    UmbralInvalidoError,
)


@dataclass
class ZonaCultivo:
    """Subdivisión agronómica en composición fuerte dentro de SectorAgricola."""
    idZona: str
    tipoCultivo: str
    areaMetrosCuadrados: float
    coeficienteCultivoKc: float = 1.0

    def calcularDemandaHidricaBase(self) -> float:
        """Retorna el factor de demanda hídrica base ponderado por Kc."""
        return round(self.areaMetrosCuadrados * self.coeficienteCultivoKc * 0.01, 2)


@dataclass
class SensorSuelo:
    """Representación de dominio de un NodoSensorIoT vinculado por composición a un SectorAgricola."""
    idNodo: str
    idSector: str
    tokenDispositivo: str
    encendido: bool = True
    intervaloSegundos: int = 10

    def cambiarEstadoOperativo(self, encendido: bool) -> None:
        """Cambia el estado de encendido/apagado del nodo sensor (RF-02)."""
        self.encendido = encendido

    @staticmethod
    def validarTrama(humedad: float, temperatura: float) -> bool:
        """Valida que la lectura esté en [0%, 100%] y [-10 °C, 60 °C] (RF-01, HU-02)."""
        if humedad is None or temperatura is None:
            return False
        if humedad < 0.0 or humedad > 100.0:
            return False
        if temperatura < -10.0 or temperatura > 60.0:
            return False
        return True


@dataclass(frozen=True)
class LecturaTelemetria:
    """Objeto de valor inmutable que encapsula una medición del suelo (F9, IE-02)."""
    idLectura: str
    idNodo: str
    idSector: str
    humedadSuelo: float
    temperaturaSuelo: float
    timestamp: datetime
    esValida: bool


@dataclass(frozen=True)
class PronosticoMeteo:
    """Objeto de valor con condiciones y pronóstico de las próximas 6 horas (F14, IE-04)."""
    latitud: float
    longitud: float
    temperaturaAmbiente: float
    humedadRelativaAire: float
    probabilidadLluvia: float
    temperaturaMinimaPronosticada: float
    timestampConsulta: datetime


@dataclass(frozen=True)
class AlertaTemprana:
    """Alerta temprana generada ante riesgo fitosanitario, térmico, helada o fallo (RF-06)."""
    idAlerta: str
    idSector: str
    tipoAlerta: TipoAlerta
    severidad: str
    mensaje: str
    timestamp: datetime


# Transiciones válidas de la Máquina de Estados UML de CicloRiego
_TRANSICIONES_VALIDAS: Dict[EstadoCicloRiego, Set[EstadoCicloRiego]] = {
    EstadoCicloRiego.INACTIVO: {EstadoCicloRiego.EVALUANDO_UMBRAL},
    EstadoCicloRiego.EVALUANDO_UMBRAL: {
        EstadoCicloRiego.INACTIVO,
        EstadoCicloRiego.CONSULTANDO_METEO,
    },
    EstadoCicloRiego.CONSULTANDO_METEO: {
        EstadoCicloRiego.POSPUESTO_POR_LLUVIA,
        EstadoCicloRiego.ABRIENDO_VALVULA,
    },
    EstadoCicloRiego.ABRIENDO_VALVULA: {
        EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO,
        EstadoCicloRiego.FALLO_VALVULA,
    },
    EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO: {
        EstadoCicloRiego.VERIFICANDO_HUMEDAD_OBJETIVO,
        EstadoCicloRiego.CERRANDO_VALVULA,
    },
    EstadoCicloRiego.VERIFICANDO_HUMEDAD_OBJETIVO: {
        EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO,
        EstadoCicloRiego.CERRANDO_VALVULA,
    },
    EstadoCicloRiego.CERRANDO_VALVULA: {
        EstadoCicloRiego.COMPLETADO,
        EstadoCicloRiego.ABORTADO_TIMEOUT,
        EstadoCicloRiego.FALLO_VALVULA,
    },
    EstadoCicloRiego.POSPUESTO_POR_LLUVIA: set(),
    EstadoCicloRiego.COMPLETADO: set(),
    EstadoCicloRiego.ABORTADO_TIMEOUT: set(),
    EstadoCicloRiego.FALLO_VALVULA: set(),
}


@dataclass
class CicloRiego:
    """Objeto de negocio principal que modela el ciclo de vida de un riego (RF-04, CU-04)."""
    idCiclo: str
    idSector: str
    idValvula: str
    fechaInicio: datetime
    humedadInicial: float
    laminaAguaMm: float = 0.0
    estado: EstadoCicloRiego = EstadoCicloRiego.INACTIVO
    fechaFin: Optional[datetime] = None
    humedadFinal: Optional[float] = None
    duracionSegundos: int = 0
    motivoCierre: Optional[MotivoCierreRiego] = None

    MAX_DURACION_SEGUNDOS: int = 2700  # 45 minutos (RF-04, HU-04 CA3)

    def transicionarA(
        self,
        nuevoEstado: EstadoCicloRiego,
        motivo: Optional[MotivoCierreRiego] = None,
    ) -> None:
        """Ejecuta una transición validada en la máquina de estados UML."""
        permitidos = _TRANSICIONES_VALIDAS.get(self.estado, set())
        if nuevoEstado not in permitidos:
            raise TransicionEstadoInvalidaError(
                f"Transición inválida en CicloRiego {self.idCiclo}: "
                f"{self.estado.value} -> {nuevoEstado.value}"
            )
        self.estado = nuevoEstado
        if motivo is not None:
            self.motivoCierre = motivo

    def estaActivo(self) -> bool:
        """Indica si el ciclo tiene la electroválvula abierta o en proceso de riego."""
        return self.estado in {
            EstadoCicloRiego.ABRIENDO_VALVULA,
            EstadoCicloRiego.IRRIGANDO_FLUJO_ACTIVO,
            EstadoCicloRiego.VERIFICANDO_HUMEDAD_OBJETIVO,
        }

    def finalizar(
        self,
        humedadFinal: float,
        duracionSegundos: int,
        motivo: MotivoCierreRiego,
        timestamp: datetime,
    ) -> None:
        """Cierra formalmente el ciclo registrando duración y motivo (RF-04)."""
        if self.estado != EstadoCicloRiego.CERRANDO_VALVULA:
            self.transicionarA(EstadoCicloRiego.CERRANDO_VALVULA, motivo)
        if motivo == MotivoCierreRiego.TIEMPO_MAXIMO_CUMPLIDO:
            self.transicionarA(EstadoCicloRiego.ABORTADO_TIMEOUT, motivo)
        elif motivo == MotivoCierreRiego.ERROR_COMUNICACION_VALVULA:
            self.transicionarA(EstadoCicloRiego.FALLO_VALVULA, motivo)
        else:
            self.transicionarA(EstadoCicloRiego.COMPLETADO, motivo)
        self.humedadFinal = humedadFinal
        self.duracionSegundos = duracionSegundos
        self.fechaFin = timestamp


@dataclass
class SectorAgricola:
    """Agregado raíz del dominio AgriTech Precision con composición fuerte sobre sus partes."""
    idSector: str
    nombre: str
    idValvula: str
    latitud: float
    longitud: float
    umbralCritico: float = 15.0
    umbralMinimo: float = 30.0
    umbralObjetivo: float = 60.0
    estadoSector: EstadoSector = EstadoSector.NORMAL
    estadoValvula: str = "cerrada"
    # Composición Fuerte (*--): el ciclo de vida de estas colecciones pertenece a SectorAgricola
    zonasCultivo: List[ZonaCultivo] = field(default_factory=list)
    sensoresSuelo: List[SensorSuelo] = field(default_factory=list)
    ciclosRiego: List[CicloRiego] = field(default_factory=list)
    lecturas: List[LecturaTelemetria] = field(default_factory=list)
    alertas: List[AlertaTemprana] = field(default_factory=list)

    def configurarUmbrales(
        self, critico: float, minimo: float, objetivo: float
    ) -> None:
        """Configura los umbrales validando 0 < crítico < mínimo < objetivo <= 100 (RF-08)."""
        if not (0.0 < critico < minimo < objetivo <= 100.0):
            raise UmbralInvalidoError(
                f"Umbrales inválidos ({critico}, {minimo}, {objetivo}): "
                "debe cumplirse 0 < crítico < mínimo < objetivo <= 100%."
            )
        self.umbralCritico = critico
        self.umbralMinimo = minimo
        self.umbralObjetivo = objetivo

    def agregarZonaCultivo(self, zona: ZonaCultivo) -> None:
        """Agrega una ZonaCultivo por composición fuerte."""
        self.zonasCultivo.append(zona)

    def agregarSensorSuelo(self, sensor: SensorSuelo) -> None:
        """Vincula un SensorSuelo al sector agrícola (RF-09)."""
        self.sensoresSuelo.append(sensor)

    def registrarLectura(self, lectura: LecturaTelemetria) -> None:
        """Almacena la lectura de telemetría en el historial del sector (RF-01)."""
        self.lecturas.append(lectura)

    def obtenerUltimaLecturaValida(self) -> Optional[LecturaTelemetria]:
        """Retorna la lectura válida más reciente del sector."""
        for lectura in reversed(self.lecturas):
            if lectura.esValida:
                return lectura
        return None

    def obtenerCicloActivo(self) -> Optional[CicloRiego]:
        """Retorna el CicloRiego actualmente en ejecución, si existe."""
        for ciclo in reversed(self.ciclosRiego):
            if ciclo.estaActivo():
                return ciclo
        return None

    def iniciarCicloRiego(self, ciclo: CicloRiego) -> None:
        """Registra un nuevo CicloRiego en el sector."""
        self.ciclosRiego.append(ciclo)
        if ciclo.estaActivo():
            self.estadoSector = EstadoSector.EN_RIEGO
            self.estadoValvula = "abierta"
        elif ciclo.estado == EstadoCicloRiego.POSPUESTO_POR_LLUVIA:
            self.estadoSector = EstadoSector.POSPUESTO_POR_LLUVIA
            self.estadoValvula = "cerrada"

    def cerrarCicloActivo(
        self,
        humedadFinal: float,
        duracionSegundos: int,
        motivo: MotivoCierreRiego,
        timestamp: datetime,
    ) -> CicloRiego:
        """Finaliza el ciclo activo y actualiza el estado de la electroválvula."""
        ciclo = self.obtenerCicloActivo()
        if ciclo is None:
            raise TransicionEstadoInvalidaError(
                f"No existe ciclo de riego activo en el sector {self.idSector}"
            )
        ciclo.finalizar(humedadFinal, duracionSegundos, motivo, timestamp)
        self.estadoValvula = "cerrada"
        if motivo == MotivoCierreRiego.ERROR_COMUNICACION_VALVULA:
            self.estadoSector = EstadoSector.ERROR_VALVULA
        else:
            self.estadoSector = EstadoSector.NORMAL
        return ciclo

    def tieneAlertaReciente(
        self,
        tipo: Optional[TipoAlerta],
        instanteActual: datetime,
        ventanaHoras: int = 12,
    ) -> bool:
        """Verifica si ya se emitió una alerta del mismo tipo en las últimas 12 horas (RF-06)."""
        if tipo is None:
            return False
        limite = instanteActual - timedelta(hours=ventanaHoras)
        for alerta in self.alertas:
            if alerta.tipoAlerta == tipo and alerta.timestamp >= limite:
                return True
        return False

    def registrarAlerta(self, alerta: AlertaTemprana) -> None:
        """Registra una nueva AlertaTemprana en el sector (RF-06)."""
        self.alertas.append(alerta)
        if alerta.tipoAlerta == TipoAlerta.FALLO_VALVULA:
            self.estadoSector = EstadoSector.ERROR_VALVULA
        elif self.estadoSector != EstadoSector.ERROR_VALVULA:
            self.estadoSector = EstadoSector.ALERTA_ACTIVA
