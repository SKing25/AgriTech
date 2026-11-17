# 2. Product Backlog & Tablero Scrum — AgriTech Precision (Grupo 2)

**Proyecto:** AgriTech Precision — Monitoreo Agrícola IoT y Riego Automatizado  
**Integrantes:** Juan David López Yara, Santiago José Rodríguez Gutiérrez, Camilo Andrés Díaz García, Roger Adrián Bohórquez Moreno  
**Curso:** Ingeniería de Software I (PCIA5008) — Universidad Sergio Arboleda  

---

## 2.1. Requerimientos del Sistema (Base de Trazabilidad del PDF)

Todas las Historias de Usuario del Product Backlog trazan directamente a los **5 Requerimientos Funcionales (`RF-01` a `RF-05`)** y se apoyan en los **5 Requerimientos No Funcionales (`RNF-01` a `RNF-05`)** definidos en el documento del proyecto:

### Requerimientos Funcionales (RF)
- **`RF-01`:** El sistema debe permitir al usuario encargado visualizar las mediciones recopiladas por los nodos sensores mediante una interfaz gráfica intuitiva y legible, presentando información como humedad y temperatura de cada sector agrícola.
- **`RF-02`:** El sistema debe permitir al usuario encargado controlar el funcionamiento de los nodos sensores mediante opciones de encendido y apagado disponibles en la interfaz gráfica.
- **`RF-03`:** El sistema debe permitir generar y descargar informes en formato Excel (`.xlsx`) que contengan los datos recopilados por los sensores, incluyendo sus respectivos valores, fechas y sectores agrícolas asociados.
- **`RF-04`:** El sistema debe evaluar automáticamente las mediciones de humedad del suelo y ejecutar los ciclos de riego correspondientes mediante la activación o desactivación de las electroválvulas, de acuerdo con los umbrales establecidos.
- **`RF-05`:** El sistema debe permitir consultar las condiciones meteorológicas actuales y los pronósticos del clima mediante la integración con una API externa, presentando la información obtenida en la interfaz gráfica.

### Requerimientos No Funcionales (RNF)
- **`RNF-01`:** El sistema debe estar desplegado en un entorno de computación en la nube que permita alojar y ejecutar aplicaciones web, garantizando su disponibilidad mediante una conexión a internet.
- **`RNF-02`:** El sistema debe estar desarrollado bajo una arquitectura MVC (Modelo-Vista-Controlador), utilizando un framework de desarrollo web como Flask, FastAPI o Django para la gestión de rutas y endpoints.
- **`RNF-03`:** La interfaz gráfica debe ser responsiva y adaptable a diferentes resoluciones de pantalla, permitiendo su utilización desde computadores y dispositivos móviles.
- **`RNF-04`:** El sistema debe garantizar el procesamiento y actualización de la información recibida desde los nodos sensores en un tiempo adecuado, evitando retrasos significativos en la visualización de las mediciones y la ejecución de los procesos automatizados.
- **`RNF-05`:** La arquitectura del sistema debe permitir la incorporación de nuevos nodos sensores y variables ambientales sin requerir modificaciones significativas en la estructura general de la aplicación.

---

## 2.2. Resumen del Product Backlog y Trazabilidad

Tal como se establece en el documento del proyecto, todas las historias se redactan desde el rol del **gestor de sensores** (único actor humano del sistema en el diagrama de contexto, denominado *usuario encargado* en los requerimientos), estimadas en **Story Points (SP)** con la escala de Fibonacci y priorizadas con el método **MoSCoW**.

| ID | Historia de usuario | RF | Prioridad | SP | Sprint | Épica | Estado |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- | :---: |
| **HU-01** | Encender y apagar nodos sensores | `RF-02` | Must | 3 | S4 | `EP-01 Control de nodos` | Product Backlog |
| **HU-02** | Recibir y validar lecturas | `RF-01` | Must | 5 | S4 | `EP-02 Telemetría y visualización` | Product Backlog |
| **HU-03** | Visualizar mediciones por sector | `RF-01` | Must | 5 | S4 | `EP-02 Telemetría y visualización` | Product Backlog |
| **HU-04** | Activar riego automático | `RF-04` | Must | 8 | S5 | `EP-03 Riego automatizado` | Product Backlog |
| **HU-05** | Considerar el pronóstico antes de regar | `RF-04`, `RF-05` | Must | 5 | S5 | `EP-03 Riego automatizado` | Product Backlog |
| **HU-06** | Consultar el clima | `RF-05` | Must | 3 | S5 | `EP-04 Clima y alertas` | Product Backlog |
| **HU-07** | Recibir alertas tempranas | `RF-05` | Should | 5 | S5 | `EP-04 Clima y alertas` | Product Backlog |
| **HU-08** | Descargar informe en Excel | `RF-03` | Must | 5 | S5 | `EP-05 Informes` | Product Backlog |
| **HU-09** | Consultar el estado del riego | `RF-01`, `RF-04` | Should | 2 | S5 | `EP-03 Riego automatizado` | Product Backlog |
| **HU-10** | Ver histórico de lecturas | `RF-01` | Could | 3 | S5 | `EP-02 Telemetría y visualización` | Product Backlog |
| **Total** | | | | **44** | | | |

---

## 2.3. Especificación de las Historias de Usuario

Cada tarjeta sigue la estructura definida en la sección *"Estructura de una historia de usuario"* del documento del proyecto (páginas 12–13):
1. Formato **`Como gestor de sensores, quiero [acción], para [beneficio]`**.
2. **Criterios de aceptación (`CA1` a `CA4`)** redactados en formato **`Dado / Cuando / Entonces`**.
3. Lista de verificación de la **Definición de Terminado (DoD)**.
4. **Trazabilidad** con los requerimientos funcionales (`RF-01` a `RF-05`), flujos de contexto (`F1` a `F7`) y componentes del sistema (`NodoSensorIoT`, `ServidorValvulas`, `APIMeteo`).

---

### HU-01: Encender y apagar nodos sensores

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-02`
- **Sprint:** `S4`
- **Story Points:** `3`
- **Tipo:** `Historia`
- **Épica:** `EP-01 Control de nodos`

#### Historia de usuario
> **Como gestor de sensores**, quiero controlar el funcionamiento de los tres nodos sensores (`NODO-01`, `NODO-02`, `NODO-03`) mediante opciones de encendido y apagado en la interfaz gráfica, **para** iniciar o detener la captura y transmisión de telemetría en cada sector agrícola según se requiera.

#### Criterios de aceptación
- [ ] **CA1.** Dado un nodo sensor en estado apagado, cuando el gestor de sensores selecciona la opción de encender en la interfaz web, entonces el sistema cambia el estado del `NodoSensorIoT` a activo y comienza a recibir sus lecturas de humedad y temperatura.
- [ ] **CA2.** Dado un nodo sensor en estado encendido, cuando el gestor de sensores selecciona la opción de apagar en la interfaz web, entonces el sistema cambia el estado del `NodoSensorIoT` a inactivo y detiene el muestreo de ese sector.
- [ ] **CA3.** Dado el panel de control de nodos, cuando el gestor de sensores cambia el estado de cualquiera de los tres nodos (`NODO-01`, `NODO-02`, `NODO-03`), entonces la interfaz gráfica actualiza de forma inmediata el indicador visual de estado (`Encendido` / `Apagado`) del nodo correspondiente.
- [ ] **CA4.** Dado que todos los nodos sensores han sido apagados por el gestor de sensores, cuando finaliza el intervalo de muestreo actual, entonces el ciclo de monitoreo se detiene de forma segura hasta que al menos un nodo vuelva a encenderse.

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-02` · Flujos `F1` (Comandos de encendido y apagado) y `F3` (Estado de los nodos) · Control interno de `NodoSensorIoT` simulado (`NODO-01`, `02`, `03`).

---

### HU-02: Recibir y validar lecturas

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-01`
- **Sprint:** `S4`
- **Story Points:** `5`
- **Tipo:** `Historia`
- **Épica:** `EP-02 Telemetría y visualización`

#### Historia de usuario
> **Como gestor de sensores**, quiero que el sistema reciba y valide las lecturas de humedad y temperatura del suelo enviadas por cada nodo sensor encendido, **para** almacenar únicamente mediciones válidas y descartar lecturas corruptas o fuera de rango antes de actualizar el dashboard o evaluar el riego.

#### Criterios de aceptación
- [ ] **CA1.** Dado un `NodoSensorIoT` encendido que mide la humedad y la temperatura del suelo, cuando envía la lectura al sistema y los valores están dentro del rango válido (humedad entre `0 %` y `100 %`, temperatura entre `-10 °C` y `60 °C`), entonces el sistema valida la lectura y la almacena con su fecha, hora y sector agrícola asociado.
- [ ] **CA2.** Dada una lectura recibida desde un `NodoSensorIoT`, cuando presenta valores fuera de rango físico o datos incompletos (lectura inválida), entonces el sistema registra la lectura inválida en el log, la descarta y no la utiliza para decisiones de riego ni alertas.
- [ ] **CA3.** Dado un nodo sensor en estado apagado, cuando el sistema ejecuta el ciclo de muestreo, entonces no procesa ni almacena nuevas lecturas de ese nodo hasta que sea encendido nuevamente.
- [ ] **CA4.** Dada una lectura válida almacenada, cuando concluye la validación, entonces el sistema habilita en paralelo la evaluación de riesgo fitosanitario y la comparación de humedad contra el umbral mínimo de riego sin retrasos significativos (`RNF-04`).

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-01` · Interacción interna entre `NodoSensorIoT` simulado y el proceso central del `Sistema AgriTech Precision`.

---

### HU-03: Visualizar mediciones por sector

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-01`
- **Sprint:** `S4`
- **Story Points:** `5`
- **Tipo:** `Historia`
- **Épica:** `EP-02 Telemetría y visualización`

#### Historia de usuario
> **Como gestor de sensores**, quiero visualizar en una interfaz gráfica intuitiva y legible las mediciones actuales de humedad y temperatura recopiladas por los nodos sensores en cada sector agrícola, **para** conocer en tiempo real las condiciones ambientales del suelo y el estado de cada sector del cultivo.

#### Criterios de aceptación
- [ ] **CA1.** Dado que existen lecturas válidas almacenadas, cuando el gestor de sensores consulta el dashboard en la interfaz web, entonces el sistema presenta la humedad (`%`) y la temperatura (`°C`) actuales de cada uno de los tres sectores agrícolas junto con el estado de su nodo sensor (`NODO-01`, `NODO-02`, `NODO-03`).
- [ ] **CA2.** Dado un nuevo intervalo de muestreo con lecturas válidas, cuando el sistema actualiza el dashboard, entonces las mediciones mostradas al gestor de sensores se refrescan oportunamente sin retrasos significativos (`RNF-04`).
- [ ] **CA3.** Dado un sector agrícola cuyo nodo sensor se encuentra apagado o sin lecturas previas, cuando el gestor de sensores visualiza el dashboard, entonces se muestra el estado `Inactivo` / `Sin lecturas` junto con la última medición registrada si existiera.
- [ ] **CA4.** Dado que el gestor de sensores accede desde un computador o un dispositivo móvil, cuando visualiza el panel de mediciones por sector, entonces la interfaz gráfica se adapta de forma responsiva a la resolución de pantalla (`RNF-03`).

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-01` · Flujo `F3` (Mediciones de humedad y temperatura por sector, estado de los nodos y del riego).

---

### HU-04: Activar riego automático

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-04`
- **Sprint:** `S5`
- **Story Points:** `8`
- **Tipo:** `Historia`
- **Épica:** `EP-03 Riego automatizado`

#### Historia de usuario
> **Como gestor de sensores**, quiero que el sistema abra la electroválvula cuando la humedad caiga bajo el umbral mínimo y la cierre al alcanzar la humedad objetivo, **para** regar solo cuando el cultivo lo necesita.

#### Criterios de aceptación
- [ ] **CA1.** Dado un sector cuya humedad cae bajo el umbral mínimo, cuando se evalúa la lectura, entonces se envía la orden de apertura al `ServidorValvulas` y se inicia el ciclo de riego.
- [ ] **CA2.** Dado un ciclo de riego activo, cuando la humedad alcanza el objetivo, entonces se ordena el cierre de la válvula y se registra la duración del ciclo.
- [ ] **CA3.** Dado un ciclo de riego activo, cuando pasan 45 minutos sin alcanzar el objetivo, entonces la válvula se cierra por seguridad.
- [ ] **CA4.** Dado un sector sin configuración propia, cuando se evalúa, entonces se usan los umbrales por defecto (mínimo `30 %`, objetivo `60 %`).

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-04` · Interacción interna con el `ServidorValvulas` simulado (Figura 4 del documento del proyecto).

---

### HU-05: Considerar el pronóstico antes de regar

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-04`, `RF-05`
- **Sprint:** `S5`
- **Story Points:** `5`
- **Tipo:** `Historia`
- **Épica:** `EP-03 Riego automatizado`

#### Historia de usuario
> **Como gestor de sensores**, quiero que el sistema consulte el pronóstico del clima en la API meteorológica externa (`APIMeteo`) antes de activar las electroválvulas cuando la humedad sea baja, **para** posponer el riego si se espera lluvia próxima y evitar riegos innecesarios optimizando el consumo de agua.

#### Criterios de aceptación
- [ ] **CA1.** Dado un sector agrícola cuya humedad está por debajo del umbral mínimo (`< 30 %`), cuando el sistema evalúa la necesidad de riego, entonces consulta las condiciones y el pronóstico del clima a `APIMeteo` antes de enviar la orden de apertura al `ServidorValvulas`.
- [ ] **CA2.** Dado que el pronóstico de `APIMeteo` indica alta probabilidad de lluvia (`lluvia > 70 %`) y la humedad del suelo no es crítica (`humedad >= 15 %`), cuando se evalúa la decisión de riego, entonces el sistema pospone el riego, no abre la electroválvula y registra el motivo de la suspensión.
- [ ] **CA3.** Dado que la humedad está bajo el umbral mínimo y no se espera lluvia (`lluvia <= 70 %`) o la humedad se encuentra en nivel crítico (`humedad < 15 %`), cuando se evalúa el pronóstico, entonces el sistema envía inmediatamente la orden de apertura al `ServidorValvulas` para proteger el cultivo.
- [ ] **CA4.** Dado que la API externa `APIMeteo` no responde o presenta un fallo de conexión, cuando un sector tiene humedad inferior al umbral mínimo, entonces el sistema ejecuta el riego basándose en la medición local de humedad y registra que no fue posible consultar el pronóstico.

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-04`, `RF-05` · Flujos `F6` (Consulta de clima del cultivo) y `F7` (Condiciones actuales y pronóstico del clima) con `APIMeteo` e interacción interna con `ServidorValvulas`.

---

### HU-06: Consultar el clima

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-05`
- **Sprint:** `S5`
- **Story Points:** `3`
- **Tipo:** `Historia`
- **Épica:** `EP-04 Clima y alertas`

#### Historia de usuario
> **Como gestor de sensores**, quiero consultar en la interfaz gráfica las condiciones meteorológicas actuales y los pronósticos del clima obtenidos mediante la integración con la API externa (`APIMeteo`), **para** contar con información meteorológica actualizada del entorno del cultivo para la toma de decisiones.

#### Criterios de aceptación
- [ ] **CA1.** Dado que el gestor de sensores solicita consultar el clima desde la interfaz web, cuando el sistema realiza la petición HTTPS REST a `APIMeteo`, entonces presenta en pantalla las condiciones meteorológicas actuales y el pronóstico del clima (temperatura ambiente, humedad ambiental y probabilidad de lluvia) para la ubicación del cultivo.
- [ ] **CA2.** Dada una respuesta exitosa en formato JSON desde `APIMeteo`, cuando se renderiza en la interfaz gráfica, entonces se muestra la fecha y hora de la última actualización meteorológica de forma legible y adaptada al dispositivo (`RNF-03`).
- [ ] **CA3.** Dado un fallo de comunicación o indisponibilidad temporal de `APIMeteo`, cuando el gestor de sensores solicita consultar el clima, entonces el sistema muestra un aviso de indisponibilidad del servicio externo junto con la última información meteorológica registrada, sin bloquear la aplicación.

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-05` · Flujos `F2` (Solicitud de consulta de condiciones meteorológicas), `F5` (Clima, pronóstico y alertas), `F6` y `F7` (Integración HTTPS REST/JSON con `APIMeteo`).

---

### HU-07: Recibir alertas tempranas

- **Estado:** `Product Backlog`
- **Prioridad:** `Should`
- **RF:** `RF-05`
- **Sprint:** `S5`
- **Story Points:** `5`
- **Tipo:** `Historia`
- **Épica:** `EP-04 Clima y alertas`

#### Historia de usuario
> **Como gestor de sensores**, quiero recibir alertas tempranas en el dashboard cuando el sistema detecte condiciones ambientales o fitosanitarias desfavorables a partir de las mediciones del suelo y los datos meteorológicos, **para** tomar decisiones oportunas y prevenir afectaciones en los sectores del cultivo.

#### Criterios de aceptación
- [ ] **CA1.** Dada una lectura válida almacenada y la información meteorológica del cultivo, cuando el sistema evalúa el riesgo fitosanitario y detecta condiciones desfavorables (como exceso de humedad con temperatura propicia para hongos, temperaturas extremas o sequía crítica), entonces genera una alerta temprana asociada al sector afectado.
- [ ] **CA2.** Dada la generación de una alerta temprana, cuando el sistema actualiza el dashboard, entonces el gestor de sensores visualiza en la interfaz web la alerta con el sector agrícola correspondiente, la condición detectada y la marca de tiempo.
- [ ] **CA3.** Dada la evaluación de riesgo fitosanitario en un sector cuyas mediciones de humedad, temperatura y clima se encuentran en rangos normales, cuando concluye la verificación, entonces el sistema no genera alertas y mantiene el estado del sector como normal en el dashboard.

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-05` · Flujo `F5` (Condiciones actuales, pronóstico y alertas tempranas hacia el gestor de sensores) y primera rama paralela del Diagrama de Actividades (Figura 5).

---

### HU-08: Descargar informe en Excel

- **Estado:** `Product Backlog`
- **Prioridad:** `Must`
- **RF:** `RF-03`
- **Sprint:** `S5`
- **Story Points:** `5`
- **Tipo:** `Historia`
- **Épica:** `EP-05 Informes`

#### Historia de usuario
> **Como gestor de sensores**, quiero generar y descargar un informe en formato Excel (`.xlsx`) que contenga los datos recopilados por los nodos sensores con sus valores, fechas y sectores agrícolas asociados, **para** conservar el respaldo documental y analizar externamente el comportamiento de los sectores del cultivo.

#### Criterios de aceptación
- [ ] **CA1.** Dado que existen mediciones válidas almacenadas en el sistema, cuando el gestor de sensores solicita la descarga del informe desde la interfaz web, entonces el sistema genera y descarga un archivo en formato Excel (`.xlsx`).
- [ ] **CA2.** Dado el archivo `.xlsx` descargado, cuando el gestor de sensores lo abre, entonces el documento incluye de forma estructurada los datos recopilados por los sensores: identificador del sector agrícola, nodo sensor (`NODO-01`, `NODO-02`, `NODO-03`), valores de humedad (`%`), valores de temperatura (`°C`) y sus respectivas fechas y horas de captura.
- [ ] **CA3.** Dado que aún no se han registrado lecturas en el sistema o en el filtro solicitado, cuando el gestor de sensores intenta descargar el informe, entonces el sistema muestra un mensaje informativo en la interfaz web indicando que no hay mediciones disponibles para exportar.

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-03` · Flujos `F2` (Solicitud de informe en Excel) y `F4` (Informe `.xlsx` con valores, fechas y sectores asociados).

---

### HU-09: Consultar el estado del riego

- **Estado:** `Product Backlog`
- **Prioridad:** `Should`
- **RF:** `RF-01`, `RF-04`
- **Sprint:** `S5`
- **Story Points:** `2`
- **Tipo:** `Historia`
- **Épica:** `EP-03 Riego automatizado`

#### Historia de usuario
> **Como gestor de sensores**, quiero consultar en la interfaz gráfica el estado actual del riego y de las electroválvulas de cada sector agrícola, **para** supervisar si un sector se encuentra regando, inactivo o con el riego pospuesto por pronóstico de lluvia.

#### Criterios de aceptación
- [ ] **CA1.** Dado el dashboard principal del sistema, cuando el gestor de sensores visualiza la información de cada sector agrícola, entonces se muestra el estado actual del riego y de su electroválvula (`Abierta / Regando`, `Cerrada / Inactivo` o `Pospuesto por lluvia`).
- [ ] **CA2.** Dado que el sistema envía una orden de apertura o de cierre al `ServidorValvulas`, cuando cambia el estado del ciclo de riego, entonces el indicador de estado en la interfaz web se actualiza automáticamente junto con el tiempo transcurrido o la duración registrada del último ciclo.
- [ ] **CA3.** Dado un ciclo de riego que fue pospuesto por pronóstico de lluvia (`lluvia > 70 %` y `humedad >= 15 %`), cuando el gestor de sensores consulta el estado del sector, entonces visualiza el motivo por el cual la electroválvula permanece cerrada.

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-01`, `RF-04` · Flujo `F3` (Mediciones de humedad y temperatura por sector, estado de los nodos y del riego).

---

### HU-10: Ver histórico de lecturas

- **Estado:** `Product Backlog`
- **Prioridad:** `Could`
- **RF:** `RF-01`
- **Sprint:** `S5`
- **Story Points:** `3`
- **Tipo:** `Historia`
- **Épica:** `EP-02 Telemetría y visualización`

#### Historia de usuario
> **Como gestor de sensores**, quiero visualizar en la interfaz gráfica el histórico de lecturas validadas de humedad y temperatura registradas por cada nodo sensor, **para** observar la evolución temporal de las condiciones del suelo en cada sector agrícola sin necesidad de salir de la aplicación web.

#### Criterios de aceptación
- [ ] **CA1.** Dado que el sistema ha almacenado múltiples lecturas válidas a lo largo de los intervalos de muestreo, cuando el gestor de sensores accede a la vista de histórico de un sector agrícola, entonces el sistema presenta el listado cronológico de mediciones con su fecha, hora, humedad (`%`) y temperatura (`°C`).
- [ ] **CA2.** Dada la vista de histórico de lecturas, cuando el gestor de sensores filtra por sector o por nodo (`NODO-01`, `NODO-02`, `NODO-03`), entonces la interfaz muestra únicamente las lecturas válidas asociadas a dicho sector, excluyendo las lecturas descartadas durante la validación.
- [ ] **CA3.** Dado que el gestor de sensores consulta el histórico desde cualquier dispositivo, cuando se cargan los registros en pantalla, entonces la vista se presenta de manera legible y responsiva (`RNF-03`, `RNF-04`).

#### Definición de Terminado
- [ ] Código revisado y en `main`
- [ ] Pruebas unitarias pasan
- [ ] Desplegado en la nube (`RNF-01`)
- [ ] Diagrama de actividades y de secuencia actualizados

**Trazabilidad:** `RF-01` · Flujo `F3` (Visualización de mediciones recopiladas por los nodos sensores en la interfaz gráfica).
