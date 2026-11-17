# AgriTech Precision — Entrega Final (Sesión 6)

**Cátedra:** Ingeniería de Software I (PCIA5008)  
**Institución:** Escuela de Ciencias Exactas e Ingeniería, Universidad Sergio Arboleda  
**Grupo 2:**
- Juan David López Yara
- Santiago José Rodríguez Gutiérrez
- Camilo Andrés Díaz García
- Roger Adrián Bohórquez Moreno

---

## 📌 Descripción del Proyecto

**AgriTech Precision** es una plataforma integral de monitoreo agrícola IoT, control automatizado de riego por balance hídrico y sistema de detección temprana de riesgos fitosanitarios. Diseñada bajo los principios de *Deep Modules* (módulos profundos), Arquitectura Limpia (*Clean Architecture*), Desarrollo Guiado por Pruebas (*TDD*) y coherencia nominal estricta con el estándar **ISO/IEC/IEEE 29148** y calidad **ISO/IEC 25010**.

---

## 🗂️ Estructura del Repositorio

El espacio de trabajo se encuentra organizado de forma modular y estandarizada:

```text
proyecto final INGW/
├── README.md                              # Documentación general y guía del repositorio
├── .gitignore                             # Reglas de exclusión para Git (LaTeX, Python, SQLite)
│
├── INFORME_FINAL_SESION6_AgriTech.pdf     # Documento PDF oficial de Entrega Final (22 páginas)
├── INFORME_FINAL_SESION6_AgriTech.tex     # Código fuente LaTeX del informe final
├── figures/                               # Recursos gráficos vectoriales y logos para LaTeX
│   └── sergio_arboleda.png
│
├── agritech_cloud_app/                    # Aplicación Web & Cloud (Producción)
│   ├── app.py                             # Entrypoint Flask, endpoints REST y rutas analíticas
│   ├── GLOSSARY.md                        # Lenguaje ubicuo y modelo de dominio estricto
│   ├── requirements.txt                   # Dependencias de producción y pruebas
│   ├── wsgi.py                            # Adaptador WSGI para despliegue en la nube
│   ├── Dockerfile                         # Contenedorización lista para producción
│   ├── render.yaml                        # Manifiesto de despliegue PaaS (Render)
│   ├── data/
│   │   └── agritech.db                    # Base de datos SQLite inicializada con datos semilla
│   ├── src/
│   │   ├── domain/                        # Entidades, Enums, Value Objects y Excepciones
│   │   ├── application/                   # Servicios, Puertos y Estrategias (McCabe V(G) <= 10)
│   │   └── infrastructure/                # Adaptadores REST/APIs, Repositorio SQLite y Simulador
│   ├── templates/
│   │   ├── dashboard.html                 # Dashboard principal en Tailwind CSS v4 + Three.js 3D
│   │   └── sector_detalle.html            # Vista analítica y telemetría por sector individual
│   └── tests/                             # Suite de pruebas automatizadas (TDD)
│       ├── test_unit_mccabe_and_domain.py # Pruebas unitarias de algoritmos e invariantes
│       └── test_integration_seams.py      # Pruebas de integración sobre seams, mocks y Flask
│
├── documentacion/                         # Documentación oficial de referencia
│   ├── guia_materia/                      # Enunciado y rúbrica oficial del proyecto
│   │   └── proyecto-final-ingenieria-de-software-i.pdf
│   └── entrega_1/                         # Artefactos y backlog corregidos de Entrega 1
│       ├── PROYECTO_FINAL_AgriTech-1.pdf
│       ├── DOC-20261112-WA0002.pdf
│       └── historias_de_usuario_backlog.md
│
├── capturas/                              # Capturas de pantalla y evidencias de análisis
│   ├── Imagen pegada.png
│   ├── page_21-21.png
│   └── ...
│
└── legacy/                                # Histórico y versiones intermedias previas
    ├── agritech_prototype/                # Prototipo inicial previo (Sesión 5)
    ├── borrador_latex_sesion5/            # Borrador inicial previo de informe LaTeX
    └── dumps_texto/                       # Volcados de texto de análisis preliminar
```

---

## 🚀 Puesta en Marcha de la Aplicación

### 1. Requisitos Previos
- Python 3.10 o superior.
- Navegador web moderno con soporte WebGL (Chrome, Firefox, Safari o Edge).

### 2. Instalación de Dependencias
```bash
cd agritech_cloud_app
pip install -r requirements.txt
```

### 3. Ejecución del Servidor Web
```bash
python3 app.py
```
El servidor iniciará en `http://localhost:5000`.

### 4. Cuentas Semilla RBAC para Pruebas
| Rol | Correo Electrónico | Contraseña | Capacidades |
| :--- | :--- | :--- | :--- |
| **Gestor de Sensores** | `gestor@agritech.co` | `AgriGestor2026!` | Telemetría, conmutar nodo, exportar Excel. |
| **Técnico Agrícola** | `tecnico@agritech.co` | `AgriTecnico2026!` | Riego manual/auto, calibrar umbrales, exportar Excel. |
| **Administrador** | `admin@agritech.co` | `AgriAdmin2026!` | Gestión de usuarios, alta de nodos, log de auditoría. |

---

## 🧪 Ejecución de Pruebas Automatizadas (TDD)

Para ejecutar la pirámide completa de 21 pruebas unitarias y de integración:

```bash
cd agritech_cloud_app
python3 -m unittest discover -v -s tests
```

**Resultado esperado:**
- `test_unit_mccabe_and_domain.py`: 14 pruebas unitarias (caminos independientes de McCabe, lógica agronómica, anti-spam 12h, invariantes).
- `test_integration_seams.py`: 7 pruebas de integración (simulador físico, ciclo de riego con timeout 45 min, caché API Meteo 3h, tolerancia a fallos de válvulas, endpoints Flask RBAC y exportación Excel).
- **Cobertura:** 21/21 pruebas en estado `OK` (0 fallos, 0 errores).

---

## 📄 Compilación del Informe en LaTeX

Para recompilar el documento académico de entrega final:

```bash
pdflatex -interaction=nonstopmode INFORME_FINAL_SESION6_AgriTech.tex
pdflatex -interaction=nonstopmode INFORME_FINAL_SESION6_AgriTech.tex
```
*(Se ejecuta dos veces para resolver referencias cruzadas de figuras, tablas y tabla de contenido).*
