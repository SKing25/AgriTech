"""Entidades y agregado raíz del dominio AgriTech Precision."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import ClassVar, Dict, List, Optional, Set

from .enums import (
    EstadoCicloRiego,
    EstadoSector,
    EstadoSensor,
    MotivoCierreRiego,
    NivelSeveridad,
    TipoAlerta,
)
from .exceptions import (
    TransicionEstadoInvalidaError,
    UmbralesInvalidosError,
)


@dataclass
class ZonaCultivo:
    """Subzona agronómica perteneciente por composición fuerte a un SectorAgricola."""

    idZona: str
    tipoCultivo: str
    areaHectareas: float
    etapaFenologica: str


@dataclass
class SensorSuelo:
    """Dispositivo de sensado IoT asociado por composición fuerte a un SectorAgricola."""

    idNodo: str
    tokenAutenticacion: str
    estadoOperativo: EstadoSensor = EstadoSensor.ACTIVO
    bateriaPorcentaje: float = 100.0

    def cambiarEstadoOperativo(self, encendido: bool) -> None:
        """Activa o apaga el sensor respetando la traza operativa (RF-08)."""
        self.estadoOperativo = EstadoSensor.ACTIVO if encendido else EstadoSensor.APAGADO

    @staticmethod
    def validarTrama(humedad: float, temperatura: float) -> bool:
        """Valida rangos físicos admisibles: humedad [0, 100]% y temperatura [-10, 60]°C."""
        return (0.0 <= humedad <= 100.0) and (-10.0 <= temperatura <= 60.0)


@dataclass(frozen=True)
class LecturaTelemetria:
    """Registro inmutable de medición telemétrica enviada por NodoSensorIoT."""

    idLectura: str
    idNodo: str
    idSector: str
    humedadSuelo: float
    temperaturaSuelo: float
    temperaturaAmbiente: float
    humedadRelativa: float
    timestamp: datetime
    esValida: bool = True


@dataclass(frozen=True)
class PronosticoMeteo:
    """Objeto de valor obtenido desde APIMeteo (en línea o caché de respaldo 3h)."""

    probabilidadLluvia: float
    tempMinimaEsperada: float
    humedadAmbientePronosticada: float
    obtenidoDesdeCache: bool
    consultadoEn: datetime


@dataclass
class AlertaTemprana:
    """Evento de alerta temprana fitosanitaria o de fallo operativo (RF-05, RF-09)."""

    idAlerta: str
    idSector: str
    tipoAlerta: TipoAlerta
    nivelSeveridad: NivelSeveridad
    mensaje: str
    timestampGeneracion: datetime
    reconocida: bool = False

    def reconocer(self) -> None:
        """Marca la alerta temprana como revisada por un usuario autorizado."""
        self.reconocida = True


_TRANSICIONES_CICLO_VALIDAS: Dict[EstadoCicloRiego, Set[EstadoCicloRiego]] = {
    EstadoCicloRiego.EVALUANDO: {
        EstadoCicloRiego.REGANDO,
        EstadoCicloRiego.POSPUESTO,
        EstadoCicloRiego.FINALIZADO,
        EstadoCicloRiego.ERROR_ACTUADOR,
    },
    EstadoCicloRiego.POSPUESTO: {
        EstadoCicloRiego.EVALUANDO,
        EstadoCicloRiego.FINALIZADO,
    },
    EstadoCicloRiego.REGANDO: {
        EstadoCicloRiego.REGANDO,
        EstadoCicloRiego.FINALIZADO,
        EstadoCicloRiego.ABORTADO_TIMEOUT,
        EstadoCicloRiego.ERROR_ACTUADOR,
    },
    EstadoCicloRiego.FINALIZADO: set(),
    EstadoCicloRiego.ABORTADO_TIMEOUT: set(),
    EstadoCicloRiego.ERROR_ACTUADOR: set(),
}


@dataclass
class CicloRiego:
    """Entidad con Máquina de Estados UML para controlar un ciclo de riego."""

    MAX_DURACION_SEGUNDOS: ClassVar[int] = 2700  # 45 minutos exactos (regla de seguridad hidráulica)

    idCiclo: str
    idSector: str
    estado: EstadoCicloRiego
    laminaAplicadaMm: float
    humedadInicial: float
    fechaInicio: datetime
    subestadoRegando: Optional[str] = None
    humedadFinal: Optional[float] = None
    fechaFin: Optional[datetime] = None
    duracionSegundos: int = 0
    motivoCierre: Optional[MotivoCierreRiego] = None

    def transicionarA(
        self,
        nuevoEstado: EstadoCicloRiego,
        motivo: Optional[MotivoCierreRiego] = None,
        subestado: Optional[str] = None,
    ) -> None:
        """Ejecuta una transición verificada de acuerdo con la FSM UML de CicloRiego."""
        permitidos = _TRANSICIONES_CICLO_VALIDAS.get(self.estado, set())
        if nuevoEstado not in permitidos:
            raise TransicionEstadoInvalidaError(
                f"Transición prohibida en CicloRiego {self.idCiclo}: {self.estado.value} -> {nuevoEstado.value}"
            )
        self.estado = nuevoEstado
        if nuevoEstado == EstadoCicloRiego.REGANDO:
            self.subestadoRegando = subestado or "VALVULA_SOLICITANDO_APERTURA"
        else:
            self.subestadoRegando = None
        if motivo is not None:
            self.motivoCierre = motivo

    def estaActivo(self) -> bool:
        """Indica si el ciclo aún no ha alcanzado un estado terminal."""
        return self.estado in {
            EstadoCicloRiego.EVALUANDO,
            EstadoCicloRiego.POSPUESTO,
            EstadoCicloRiego.REGANDO,
        }

    def finalizar(
        self,
        humedadFinal: float,
        duracionSegundos: int,
        motivo: MotivoCierreRiego,
        timestamp: datetime,
    ) -> None:
        """Cierra formalmente un ciclo activo asignando su estado terminal exacto."""
        if not self.estaActivo():
            raise TransicionEstadoInvalidaError(
                f"No es posible finalizar el ciclo {self.idCiclo} desde estado terminal {self.estado.value}"
            )
        if motivo == MotivoCierreRiego.TIMEOUT_MAXIMO_45MIN:
            destino = EstadoCicloRiego.ABORTADO_TIMEOUT
        elif motivo == MotivoCierreRiego.FALLO_VALVULA:
            destino = EstadoCicloRiego.ERROR_ACTUADOR
        else:
            destino = EstadoCicloRiego.FINALIZADO
        self.transicionarA(destino, motivo=motivo)
        self.humedadFinal = humedadFinal
        self.duracionSegundos = max(0, duracionSegundos)
        self.fechaFin = timestamp


@dataclass
class SectorAgricola:
    """Raíz de agregado que posee por Composición Fuerte sus zonas, sensores, lecturas, ciclos y alertas."""

    idSector: str
    nombre: str
    latitud: float
    longitud: float
    umbralCritico: float = 15.0
    umbralMinimo: float = 30.0
    umbralObjetivo: float = 60.0
    estadoActual: EstadoSector = EstadoSector.OPTIMO
    zonas: List[ZonaCultivo] = field(default_factory=list)
    sensores: List[SensorSuelo] = field(default_factory=list)
    lecturas: List[LecturaTelemetria] = field(default_factory=list)
    ciclosRiego: List[CicloRiego] = field(default_factory=list)
    alertas: List[AlertaTemprana] = field(default_factory=list)

    def configurarUmbrales(self, critico: float, minimo: float, objetivo: float) -> None:
        """Actualiza umbrales validando invariante 0 < critico < minimo < objetivo <= 100."""
        if not (0.0 < critico < minimo < objetivo <= 100.0):
            raise UmbralesInvalidosError(
                f"Umbrales inválidos ({critico}, {minimo}, {objetivo}): debe cumplirse 0 < critico < minimo < objetivo <= 100."
            )
        self.umbralCritico = float(critico)
        self.umbralMinimo = float(minimo)
        self.umbralObjetivo = float(objetivo)

    def agregarZonaCultivo(self, zona: ZonaCultivo) -> None:
        """Agrega una ZonaCultivo bajo composición fuerte al sector."""
        self.zonas.append(zona)

    def agregarSensorSuelo(self, sensor: SensorSuelo) -> None:
        """Agrega un SensorSuelo bajo composición fuerte al sector."""
        self.sensores.append(sensor)

    def registrarLectura(self, lectura: LecturaTelemetria) -> None:
        """Almacena una lectura telemétrica validando pertenencia al sector."""
        if lectura.idSector != self.idSector:
            raise ValueError(
                f"Lectura de sector {lectura.idSector} no corresponde al sector {self.idSector}"
            )
        self.lecturas.append(lectura)

    def obtenerUltimaLecturaValida(self) -> Optional[LecturaTelemetria]:
        """Retorna la lectura válida más reciente del sector, o None si no hay lecturas."""
        for lectura in reversed(self.lecturas):
            if lectura.esValida:
                return lectura
        return None

    def obtenerCicloActivo(self) -> Optional[CicloRiego]:
        """Retorna el CicloRiego activo del sector (máximo uno por invariante)."""
        for ciclo in reversed(self.ciclosRiego):
            if ciclo.estaActivo():
                return ciclo
        return None

    def iniciarCicloRiego(self, ciclo: CicloRiego) -> None:
        """Registra e inicia un nuevo CicloRiego verificando unicidad de ciclo activo."""
        activo = self.obtenerCicloActivo()
        if activo is not None:
            raise TransicionEstadoInvalidaError(
                f"El sector {self.idSector} ya tiene el ciclo activo {activo.idCiclo} en estado {activo.estado.value}"
            )
        self.ciclosRiego.append(ciclo)
        if ciclo.estado == EstadoCicloRiego.REGANDO:
            self.estadoActual = EstadoSector.REGANDO
        elif ciclo.estado == EstadoCicloRiego.POSPUESTO:
            self.estadoActual = EstadoSector.RIEGO_POSPUESTO

    def cerrarCicloActivo(
        self,
        humedadFinal: float,
        duracionSegundos: int,
        motivo: MotivoCierreRiego,
        timestamp: datetime,
    ) -> CicloRiego:
        """Cierra el CicloRiego activo y actualiza el estado consolidado del sector."""
        activo = self.obtenerCicloActivo()
        if activo is None:
            raise TransicionEstadoInvalidaError(
                f"No existe un CicloRiego activo para cerrar en el sector {self.idSector}"
            )
        activo.finalizar(
            humedadFinal=humedadFinal,
            duracionSegundos=duracionSegundos,
            motivo=motivo,
            timestamp=timestamp,
        )
        if motivo == MotivoCierreRiego.FALLO_VALVULA:
            self.estadoActual = EstadoSector.ERROR_VALVULA
        elif self.estadoActual != EstadoSector.ERROR_VALVULA:
            if humedadFinal >= self.umbralMinimo:
                self.estadoActual = EstadoSector.OPTIMO
            else:
                self.estadoActual = EstadoSector.REQUIERE_RIEGO
        return activo

    def tieneAlertaReciente(
        self,
        tipo: Optional[TipoAlerta],
        instanteActual: datetime,
        ventanaHoras: int = 12,
    ) -> bool:
        """Verifica regla anti-spam de 12h por (idSector, tipoAlerta) usando reloj explícito."""
        limite = instanteActual - timedelta(hours=ventanaHoras)
        for alerta in reversed(self.alertas):
            if tipo is not None and alerta.tipoAlerta != tipo:
                continue
            if alerta.timestampGeneracion >= limite and alerta.timestampGeneracion <= instanteActual:
                return True
        return False

    def registrarAlerta(self, alerta: AlertaTemprana) -> None:
        """Registra una alerta preservando ERROR_VALVULA si ya está activo o si la alerta es FALLO_VALVULA."""
        self.alertas.append(alerta)
        if alerta.tipoAlerta == TipoAlerta.FALLO_VALVULA:
            self.estadoActual = EstadoSector.ERROR_VALVULA
        elif self.estadoActual != EstadoSector.ERROR_VALVULA:
            self.estadoActual = EstadoSector.ALERTA_FITOSANITARIA
