# Glosario del Dominio — AgriTech Precision (Grupo 2)

> **Fuente Canónica de Coherencia Nominal (Skill `domain-modeling`)**  
> Todo identificador definido en este glosario es **estricto e inmutable** a través de los requerimientos (`ISO/IEC/IEEE 29148`), diagramas UML 2.5 (Secuencia, Clases y Máquina de Estados), código fuente Python (`agritech_cloud_app/src/`), esquema SQLite y pruebas automatizadas (`agritech_cloud_app/tests/`).

---

## 1. Actores y Sistemas Externos

| Identificador Canónico | Estereotipo | Descripción y Frontera |
| :--- | :--- | :--- |
| `GestorSensores` | `<<actor>>` | Usuario (`RolUsuario.GESTOR_SENSORES`) encargado de encender/apagar nodos, supervisar telemetría y riego, consultar clima y descargar informes Excel (`HU-01`, `HU-02`, `HU-03`, `HU-04`, `HU-05`, `HU-06`, `HU-08`, `HU-09`). |
| `TecnicoAgricola` | `<<actor>>` | Usuario (`RolUsuario.TECNICO_AGRICOLA`) encargado de configurar umbrales por sector, recibir alertas tempranas y analizar histórico de lecturas (`HU-07`, `HU-10`, `HU-11`). |
| `AdministradorSistema` | `<<actor>>` | Usuario (`RolUsuario.ADMINISTRADOR`) con control total sobre cuentas, roles RBAC, registro de nodos y bitácora de auditoría (`HU-12`, `HU-13`, `HU-14`, `SEG-01..04`). |
| `NodoSensorIoT` | `<<external system>>` | Dispositivo físico/simulado (`NODO-01`, `NODO-02`, `NODO-03`) que transmite tramas JSON vía `POST /api/lecturas` con token `X-Device-Token` (`IE-02`, `SEG-02`). |
| `APIMeteo` | `<<external system>>` | Servicio meteorológico externo (Open-Meteo HTTPS + respaldo caché local de 3 horas, timeout 5 s) que provee pronóstico de lluvia, temperatura mínima y humedad relativa (`IE-04`). |
| `ServidorValvulas` | `<<external system>>` | Actuador electrohidráulico externo (`PUT /valvulas/{id}`) con timeout de 3 s y política de hasta 3 reintentos (`IE-03`). |

---

## 2. Entidades del Dominio y Agregados (`src/domain/entities.py`)

### 2.1 `SectorAgricola` (Raíz de Agregado — Composición Fuerte)
Unidad agrícola geolocalizada con latitud/longitud, umbrales configurables de humedad y propiedad exclusiva (composición fuerte `*--`) sobre sus zonas, sensores, lecturas, ciclos y alertas.

- **Atributos privados**: `idSector: str`, `nombre: str`, `latitud: float`, `longitud: float`, `umbralCritico: float = 15.0`, `umbralMinimo: float = 30.0`, `umbralObjetivo: float = 60.0`, `estadoActual: EstadoSector`, `zonas: List[ZonaCultivo]` (`1..*`), `sensores: List[SensorSuelo]` (`1..*`), `lecturas: List[LecturaTelemetria]` (`0..*`), `ciclosRiego: List[CicloRiego]` (`0..*`), `alertas: List[AlertaTemprana]` (`0..*`).
- **Invariantes**:
  1. $0.0 < \text{umbralCritico} < \text{umbralMinimo} < \text{umbralObjetivo} \le 100.0$.
  2. Como máximo existe **un** `CicloRiego` con `estaActivo() == True` simultáneamente por `SectorAgricola`.
  3. Un estado `EstadoSector.ERROR_VALVULA` no es sobrescrito por alertas fitosanitarias hasta resolución técnica.
- **Métodos públicos exactos**:
  - `configurarUmbrales(critico: float, minimo: float, objetivo: float) -> None`
  - `agregarZonaCultivo(zona: ZonaCultivo) -> None`
  - `agregarSensorSuelo(sensor: SensorSuelo) -> None`
  - `registrarLectura(lectura: LecturaTelemetria) -> None`
  - `obtenerUltimaLecturaValida() -> Optional[LecturaTelemetria]`
  - `obtenerCicloActivo() -> Optional[CicloRiego]`
  - `iniciarCicloRiego(ciclo: CicloRiego) -> None`
  - `cerrarCicloActivo(humedadFinal: float, duracionSegundos: int, motivo: MotivoCierreRiego, timestamp: datetime) -> CicloRiego`
  - `tieneAlertaReciente(tipo: Optional[TipoAlerta], instanteActual: datetime, ventanaHoras: int = 12) -> bool`
  - `registrarAlerta(alerta: AlertaTemprana) -> None`

### 2.2 `ZonaCultivo` (Parte Compuesta de `SectorAgricola`)
- **Atributos**: `idZona: str`, `tipoCultivo: str`, `areaHectareas: float`, `etapaFenologica: str`.

### 2.3 `SensorSuelo` (Parte Compuesta de `SectorAgricola`)
- **Atributos**: `idNodo: str`, `tokenAutenticacion: str`, `estadoOperativo: EstadoSensor`, `bateriaPorcentaje: float`.
- **Métodos públicos exactos**:
  - `cambiarEstadoOperativo(encendido: bool) -> None`
  - `@staticmethod validarTrama(humedad: float, temperatura: float) -> bool` (valida `0.0 <= humedad <= 100.0` y `-10.0 <= temperatura <= 60.0`).

### 2.4 `LecturaTelemetria` (Parte Compuesta de `SectorAgricola`)
- **Atributos**: `idLectura: str`, `idNodo: str`, `idSector: str`, `humedadSuelo: float`, `temperaturaSuelo: float`, `temperaturaAmbiente: float`, `humedadRelativa: float`, `timestamp: datetime`, `esValida: bool`.

### 2.5 `PronosticoMeteo` (Objeto de Valor desde `APIMeteo`)
- **Atributos**: `probabilidadLluvia: float`, `tempMinimaEsperada: float`, `humedadAmbientePronosticada: float`, `obtenidoDesdeCache: bool`, `consultadoEn: datetime`.

### 2.6 `AlertaTemprana` (Parte Compuesta de `SectorAgricola`)
- **Atributos**: `idAlerta: str`, `idSector: str`, `tipoAlerta: TipoAlerta`, `nivelSeveridad: NivelSeveridad`, `mensaje: str`, `timestampGeneracion: datetime`, `reconocida: bool`.
- **Métodos públicos exactos**:
  - `reconocer() -> None`

### 2.7 `CicloRiego` (Entidad con Máquina de Estados UML — Parte Compuesta de `SectorAgricola`)
- **Constante de dominio**: `MAX_DURACION_SEGUNDOS: int = 2700` (45 minutos).
- **Atributos**: `idCiclo: str`, `idSector: str`, `estado: EstadoCicloRiego`, `subestadoRegando: Optional[str]`, `laminaAplicadaMm: float`, `humedadInicial: float`, `humedadFinal: Optional[float]`, `fechaInicio: datetime`, `fechaFin: Optional[datetime]`, `duracionSegundos: int`, `motivoCierre: Optional[MotivoCierreRiego]`.
- **Métodos públicos exactos**:
  - `transicionarA(nuevoEstado: EstadoCicloRiego, motivo: Optional[MotivoCierreRiego] = None, subestado: Optional[str] = None) -> None`
  - `estaActivo() -> bool`
  - `finalizar(humedadFinal: float, duracionSegundos: int, motivo: MotivoCierreRiego, timestamp: datetime) -> None`

---

## 3. Enumeraciones (`src/domain/enums.py`)

| Enumeración | Valores Canónicos |
| :--- | :--- |
| `RolUsuario` | `GESTOR_SENSORES`, `TECNICO_AGRICOLA`, `ADMINISTRADOR` |
| `EstadoSector` | `OPTIMO`, `REQUIERE_RIEGO`, `REGANDO`, `RIEGO_POSPUESTO`, `ALERTA_FITOSANITARIA`, `ERROR_VALVULA` |
| `EstadoSensor` | `ACTIVO`, `APAGADO`, `FALLA_COMUNICACION` |
| `EstadoCicloRiego` | `EVALUANDO`, `POSPUESTO`, `REGANDO`, `FINALIZADO`, `ABORTADO_TIMEOUT`, `ERROR_ACTUADOR` |
| `MotivoCierreRiego` | `OBJETIVO_ALCANZADO`, `TIMEOUT_MAXIMO_45MIN`, `CIERRE_MANUAL`, `LLUVIA_INMINENTE`, `FALLO_VALVULA` |
| `TipoAlerta` | `HELADA`, `ESTRES_TERMICO`, `RIESGO_FUNGICO`, `FALLO_VALVULA`, `BATERIA_CRITICA` |
| `NivelSeveridad` | `INFORMATIVA`, `ADVERTENCIA`, `CRITICA` |

---

## 4. Excepciones de Dominio (`src/domain/exceptions.py`)

- `DominioAgriTechError`
- `TokenDispositivoInvalidoError` (HTTP `401`)
- `TelemetriaFueraDeRangoError` (HTTP `400`)
- `AccesoNoAutorizadoError` (HTTP `403`)
- `TransicionEstadoInvalidaError` (HTTP `409`)
- `FalloComunicacionValvulaError` (HTTP `502`)
- `UmbralesInvalidosError` (HTTP `400`)
- `EntidadNoEncontradaError` (HTTP `404`)

---

## 5. Puertos, Estrategias, Servicios y Controladores (Patrones GoF + Deep Modules)

| Componente | Estereotipo / Patrón GoF | Relación con `SectorAgricola` / Servicio | Interfaz Pública Exacta |
| :--- | :--- | :--- | :--- |
| `IEstrategiaRiego` / `EstrategiaRiegoAgronomico` | `<<interface>>` / **Strategy** | Agregación (`o--`) desde `ServicioMonitoreoRiego` (`1`) | `calcularLaminaRiego(humedadActual, umbralMinimo, umbralCritico, umbralObjetivo, probLluvia, tempSuelo) -> float` |
| `IPuertoAPIMeteo` / `AdaptadorAPIMeteo` | `<<interface>>` / **Adapter** | Dependencia / Inyección (`<<use>>`) | `consultarPronostico(latitud, longitud, instanteActual=None) -> PronosticoMeteo` |
| `IPuertoServidorValvulas` / `AdaptadorServidorValvulas` | `<<interface>>` / **Adapter** | Dependencia / Inyección (`<<use>>`) | `activarValvula(sectorId, duracionSegundos) -> EstadoValvulaDTO`, `desactivarValvula(sectorId) -> EstadoValvulaDTO` |
| `IObservadorEvento` / `BitacoraAuditoriaObserver` | `<<interface>>` / **Observer** | Agregación (`o--`) desde `ServicioMonitoreoRiego` (`0..*`) | `actualizarAlerta(alerta) -> None`, `registrarEventoAuditoria(usuario, operacion, detalle, timestamp) -> None` |
| `IRepositorioAgricola` / `RepositorioSQLite` | `<<interface>>` / Repository | Dependencia (`1`) desde `ServicioMonitoreoRiego` | `obtenerSector`, `obtenerSectorPorNodo`, `obtenerSensor`, `guardarSector`, `listarSectores`, `obtenerUsuarioPorEmail`, `guardarCuenta`, `registrarAuditoriaEnBD`, `obtenerAuditoria` |
| `ServicioMonitoreoRiego` | `<<control>>` / Deep Module | Orquestador central de telemetría, riego y riesgo fitosanitario | `suscribirObservador`, `procesarTelemetria`, `evaluarRiesgoFitosanitario`, `calcularLaminaRiego`, `verificarTimeoutRiego`, `cambiarEstadoNodo`, `configurarUmbralesSector` |
| `ControladorTelemetriaREST` | `<<boundary>>` | Controlador HTTP de borde y exportación Excel | `postLecturaTelemetria`, `putEstadoNodo`, `putUmbralesSector`, `exportarFilasInformeExcel`, `generarArchivoXlsxBytes` |
