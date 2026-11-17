# Glosario del Dominio — AgriTech Precision (Grupo 2)

Este glosario establece el lenguaje ubicuo (*Ubiquitous Language*) del proyecto **AgriTech Precision**, garantizando coherencia nominal estricta entre el documento SRS (`ISO/IEC/IEEE 29148`), los diagramas UML 2.5 (Secuencia, Clases de Diseño y Máquina de Estados), el código fuente y la suite de pruebas automatizadas.

## Términos del Dominio

- **`SectorAgricola`**: Unidad geográfica y productiva del cultivo monitoreada de forma autónoma. Posee umbrales propios de humedad del suelo (`umbralCritico = 15%`, `umbralMinimo = 30%`, `umbralObjetivo = 60%`) y está compuesta fuertemente por sus zonas de cultivo (`ZonaCultivo`), sensores asignados (`SensorSuelo`), lecturas (`LecturaTelemetria`), ciclos de riego (`CicloRiego`) y alertas (`AlertaTemprana`).
- **`ZonaCultivo`**: Subdivisión agronómica dentro de un `SectorAgricola` caracterizada por un tipo de cultivo, área en metros cuadrados y coeficiente de cultivo ($K_c$). Su ciclo de vida depende estrictamente del `SectorAgricola` (Composición Fuerte).
- **`SensorSuelo` (`NodoSensorIoT`)**: Dispositivo IoT asociado a un `SectorAgricola` (`NODO-01`, `NODO-02`, `NODO-03`) que mide humedad (`%`) y temperatura (`°C`) del suelo. Se identifica mediante un `tokenDispositivo` único (`SEG-02`) y opera según su estado (`encendido: bool`).
- **`LecturaTelemetria`**: Registro inmutable originado por un `SensorSuelo` en un instante dado (`timestamp`). Es válida únicamente si la humedad del suelo pertenece a $[0\%, 100\%]$ y la temperatura del suelo pertenece a $[-10\text{ }^\circ\text{C}, 60\text{ }^\circ\text{C}]$.
- **`CicloRiego`**: Proceso transaccional de irrigación ejecutado sobre un `SectorAgricola` cuando la humedad cae por debajo del `umbralMinimo`. Registra `fechaInicio`, `fechaFin`, `duracionSegundos`, `laminaAguaMm`, `estado` (`EstadoCicloRiego`) y `motivoCierre` (`MotivoCierreRiego`). Ningún ciclo puede mantener abierta una electroválvula por más de 45 minutos (`2700` segundos).
- **`PronosticoMeteo`**: Estructura de datos climáticos suministrada por el servicio externo `APIMeteo` para las próximas 6 horas (`temperaturaAmbiente`, `humedadRelativaAire`, `probabilidadLluvia`, `temperaturaMinimaPronosticada`). Tiene una vigencia en caché de 3 horas (`RNF-03`).
- **`AlertaTemprana`**: Notificación preventiva emitida cuando convergen condiciones agroclimáticas adversas en un `SectorAgricola` (`RIESGO_FITOSANITARIO`, `ESTRES_TERMICO`, `RIESGO_HELADA` o `FALLO_VALVULA`), sujeta a una ventana de supresión de duplicados de 12 horas (`RF-06`).
- **`Gestor de sensores`**: Rol humano encargado de supervisar el dashboard, encender/apagar nodos sensores y descargar informes en formato Excel (`.xlsx`).
- **`Técnico agrícola`**: Rol humano responsable de parametrizar los umbrales de humedad (`umbralCritico`, `umbralMinimo`, `umbralObjetivo`), analizar el histórico de lecturas y atender las alertas tempranas.
- **`Administrador del sistema`**: Rol humano facultado para gestionar cuentas de usuario, registrar nodos sensores y auditar la bitácora del sistema (`SEG-01`, `SEG-04`).
