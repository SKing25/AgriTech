"""Aplicación Web MVC Cloud (Flask + SQLite) para AgriTech Precision."""

from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.application.services import ServicioMonitoreoRiego
from src.domain.entities import PronosticoMeteo
from src.domain.enums import RolUsuario
from src.infrastructure.adapters import (
    AdaptadorAPIMeteo,
    AdaptadorServidorValvulas,
    BitacoraAuditoriaObserver,
)
from src.infrastructure.controllers import ControladorTelemetriaREST
from src.infrastructure.simulator import MotorSimuladorFisico, RelojSimulacion
from src.infrastructure.sqlite_repository import RepositorioSQLite, verificarPassword


def create_app(
    dbPath: Optional[str] = None,
    iniciarSimulador: bool = True,
    adaptadorMeteo: Optional[AdaptadorAPIMeteo] = None,
    adaptadorValvulas: Optional[AdaptadorServidorValvulas] = None,
) -> Flask:
    """Fábrica de aplicación Flask con composición limpia de capas hexagonales."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    templates_dir = os.path.join(base_dir, "templates")
    app = Flask(__name__, template_folder=templates_dir)
    app.secret_key = os.environ.get("AGRITECH_SECRET_KEY", "agritech-precision-sergio-arboleda-2026")

    es_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
    if dbPath:
        rutaBd = dbPath
    elif os.environ.get("AGRITECH_DB_PATH"):
        rutaBd = os.environ["AGRITECH_DB_PATH"]
    elif es_serverless:
        # En entornos serverless (Vercel / Lambda) el único directorio escribible es /tmp
        rutaBd = "/tmp/agritech.db"
        if not os.path.exists(rutaBd):
            template_db = os.path.join(base_dir, "data", "agritech.db")
            if os.path.exists(template_db):
                import shutil
                try:
                    shutil.copyfile(template_db, rutaBd)
                except Exception:
                    pass
    else:
        rutaBd = os.path.join(base_dir, "data", "agritech.db")

    repositorio = RepositorioSQLite(dbPath=rutaBd)
    repositorio.sembrarDatosIniciales()

    respaldoMeteo = PronosticoMeteo(
        probabilidadLluvia=15.0,
        tempMinimaEsperada=10.5,
        humedadAmbientePronosticada=68.0,
        obtenidoDesdeCache=True,
        consultadoEn=datetime.now(timezone.utc),
    )
    meteo = adaptadorMeteo or AdaptadorAPIMeteo(respaldoOffline=respaldoMeteo)
    valvulas = adaptadorValvulas or AdaptadorServidorValvulas()
    observador = BitacoraAuditoriaObserver()
    servicio = ServicioMonitoreoRiego(
        repositorio=repositorio,
        puertoMeteo=meteo,
        puertoValvulas=valvulas,
        observadores=[observador],
    )
    controlador = ControladorTelemetriaREST(servicio=servicio)
    reloj = RelojSimulacion()
    simulador = MotorSimuladorFisico(
        repositorio=repositorio,
        servicio=servicio,
        controlador=controlador,
        adaptadorMeteo=meteo,
        adaptadorValvulas=valvulas,
        reloj=reloj,
    )

    app.config["AGRITECH_REPO"] = repositorio
    app.config["AGRITECH_SERVICIO"] = servicio
    app.config["AGRITECH_CONTROLADOR"] = controlador
    app.config["AGRITECH_SIMULADOR"] = simulador
    app.config["AGRITECH_METEO"] = meteo
    app.config["AGRITECH_VALVULAS"] = valvulas
    app.config["AGRITECH_OBSERVADOR"] = observador

    # Sembrar historial inicial de 6 ticks en BD vacía o sincronizar físico con BD existente
    if all(len(s.lecturas) == 0 for s in repositorio.listarSectores()):
        for _ in range(6):
            simulador.ejecutarCicloTick()
    else:
        simulador.sincronizarDesdeRepositorio()

    if iniciarSimulador and not es_serverless:
        def _loopSimulador() -> None:
            while True:
                time.sleep(3)
                try:
                    simulador.ejecutarCicloTick()
                except Exception:
                    pass

        hilo = threading.Thread(target=_loopSimulador, daemon=True, name="agritech-sim-loop")
        hilo.start()

    def _usuarioActual() -> Optional[Dict[str, Any]]:
        if "usuario_email" not in session:
            return None
        return {
            "email": session["usuario_email"],
            "nombre": session.get("usuario_nombre", session["usuario_email"]),
            "rol": session["usuario_rol"],
        }

    def _construirSnapshot() -> Dict[str, Any]:
        sectores = repositorio.listarSectores()
        fisicos = simulador.obtenerEstadosFisicos()
        tarjetas = []
        alertasGlobales = []
        ciclosRecientes = []

        for s in sectores:
            ultima = s.obtenerUltimaLecturaValida()
            cicloActivo = s.obtenerCicloActivo()
            sensor = s.sensores[0] if s.sensores else None
            zona = s.zonas[0] if s.zonas else None
            try:
                pronostico = meteo.consultarPronostico(s.latitud, s.longitud, reloj.ahora())
            except Exception:
                pronostico = respaldoMeteo

            tarjetas.append(
                {
                    "idSector": s.idSector,
                    "nombre": s.nombre,
                    "latitud": s.latitud,
                    "longitud": s.longitud,
                    "estadoActual": s.estadoActual.value,
                    "umbralCritico": s.umbralCritico,
                    "umbralMinimo": s.umbralMinimo,
                    "umbralObjetivo": s.umbralObjetivo,
                    "valvulaAbierta": valvulas.valvulaEstaAbierta(s.idSector),
                    "zona": {
                        "tipoCultivo": zona.tipoCultivo,
                        "areaHectareas": zona.areaHectareas,
                        "etapaFenologica": zona.etapaFenologica,
                    }
                    if zona
                    else None,
                    "sensor": {
                        "idNodo": sensor.idNodo,
                        "estadoOperativo": sensor.estadoOperativo.value,
                        "bateriaPorcentaje": sensor.bateriaPorcentaje,
                    }
                    if sensor
                    else None,
                    "ultimaLectura": {
                        "humedadSuelo": ultima.humedadSuelo,
                        "temperaturaSuelo": ultima.temperaturaSuelo,
                        "temperaturaAmbiente": ultima.temperaturaAmbiente,
                        "humedadRelativa": ultima.humedadRelativa,
                        "timestamp": ultima.timestamp.strftime("%Y-%m-%d %H:%M"),
                    }
                    if ultima
                    else None,
                    "historialHumedad": [l.humedadSuelo for l in s.lecturas[-30:]],
                    "historialTempSuelo": [l.temperaturaSuelo for l in s.lecturas[-30:]],
                    "historialTempAmbiente": [l.temperaturaAmbiente for l in s.lecturas[-30:]],
                    "historialHumedadRelativa": [l.humedadRelativa for l in s.lecturas[-30:]],
                    "historialTimestamps": [l.timestamp.strftime("%H:%M") for l in s.lecturas[-30:]],
                    "lecturasDetalladas": [
                        {
                            "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M"),
                            "hora": l.timestamp.strftime("%H:%M"),
                            "humedadSuelo": l.humedadSuelo,
                            "temperaturaSuelo": l.temperaturaSuelo,
                            "temperaturaAmbiente": l.temperaturaAmbiente,
                            "humedadRelativa": l.humedadRelativa,
                        }
                        for l in s.lecturas[-30:]
                    ],
                    "cicloActivo": {
                        "idCiclo": cicloActivo.idCiclo,
                        "estado": cicloActivo.estado.value,
                        "subestado": cicloActivo.subestadoRegando,
                        "laminaMm": cicloActivo.laminaAplicadaMm,
                        "duracionSegundos": cicloActivo.duracionSegundos,
                    }
                    if cicloActivo
                    else None,
                    "pronostico": {
                        "probabilidadLluvia": pronostico.probabilidadLluvia,
                        "tempMinimaEsperada": pronostico.tempMinimaEsperada,
                        "humedadAmbientePronosticada": pronostico.humedadAmbientePronosticada,
                        "obtenidoDesdeCache": pronostico.obtenidoDesdeCache,
                    },
                    "simulacionFisica": {
                        "horasCondicionFungo": fisicos[sensor.idNodo].horasCondicionFungo
                        if sensor and sensor.idNodo in fisicos
                        else 0,
                        "horasCalorSuelo": fisicos[sensor.idNodo].horasCalorSuelo
                        if sensor and sensor.idNodo in fisicos
                        else 0,
                    },
                }
            )
            for a in s.alertas:
                alertasGlobales.append(
                    {
                        "idAlerta": a.idAlerta,
                        "idSector": a.idSector,
                        "tipoAlerta": a.tipoAlerta.value,
                        "nivelSeveridad": a.nivelSeveridad.value,
                        "mensaje": a.mensaje,
                        "timestamp": a.timestampGeneracion.strftime("%Y-%m-%d %H:%M"),
                        "reconocida": a.reconocida,
                    }
                )
            for c in s.ciclosRiego:
                ciclosRecientes.append(
                    {
                        "idCiclo": c.idCiclo,
                        "idSector": c.idSector,
                        "estado": c.estado.value,
                        "laminaMm": c.laminaAplicadaMm,
                        "humedadInicial": c.humedadInicial,
                        "humedadFinal": c.humedadFinal,
                        "duracionSegundos": c.duracionSegundos,
                        "motivoCierre": c.motivoCierre.value if c.motivoCierre else "En curso",
                        "fechaInicio": c.fechaInicio.strftime("%Y-%m-%d %H:%M"),
                    }
                )

        alertasGlobales.sort(key=lambda x: x["timestamp"], reverse=True)
        ciclosRecientes.sort(key=lambda x: x["fechaInicio"], reverse=True)

        return {
            "relojSimulado": reloj.ahora().strftime("%Y-%m-%d %H:%M:%S %Z"),
            "usuario": _usuarioActual(),
            "sectores": tarjetas,
            "alertas": alertasGlobales[:25],
            "ciclos": ciclosRecientes[:20],
        }

    @app.get("/api/health")
    def health() -> Response:
        return jsonify(
            {
                "status": "UP",
                "servicio": "AgriTech Precision Cloud",
                "sectores": len(repositorio.listarSectores()),
                "relojSimulado": reloj.ahora().isoformat(),
            }
        )

    def _detalleSectorSnapshot(idSector: str) -> Optional[Dict[str, Any]]:
        snapshot = _construirSnapshot()
        sector = next((s for s in snapshot["sectores"] if s["idSector"] == idSector), None)
        if sector is None:
            return None
        return {
            "snapshot": snapshot,
            "sector": sector,
            "alertas": [a for a in snapshot["alertas"] if a["idSector"] == idSector],
            "ciclos": [c for c in snapshot["ciclos"] if c["idSector"] == idSector],
        }

    @app.get("/")
    def index():
        if es_serverless:
            try:
                simulador.ejecutarCicloTick()
            except Exception:
                pass
        snapshot = _construirSnapshot()
        auditoria = (
            repositorio.obtenerAuditoria(30)
            if snapshot["usuario"] and snapshot["usuario"]["rol"] == RolUsuario.ADMINISTRADOR.value
            else []
        )
        return render_template(
            "dashboard.html",
            snapshot=snapshot,
            auditoria=auditoria,
            error_login=request.args.get("error"),
        )

    @app.get("/sectores/<idSector>")
    def vistaDetalleSector(idSector: str):
        detalle = _detalleSectorSnapshot(idSector)
        if detalle is None:
            return jsonify({"error": f"Sector no encontrado: {idSector}"}), 404
        return render_template(
            "sector_detalle.html",
            snapshot=detalle["snapshot"],
            sector=detalle["sector"],
            alertas_sector=detalle["alertas"],
            ciclos_sector=detalle["ciclos"],
        )

    @app.get("/api/sectores/<idSector>/historial")
    def apiHistorialSector(idSector: str):
        detalle = _detalleSectorSnapshot(idSector)
        if detalle is None:
            return jsonify({"error": f"Sector no encontrado: {idSector}"}), 404
        snapshot = detalle["snapshot"]
        return jsonify(
            {
                "relojSimulado": snapshot["relojSimulado"],
                "usuario": snapshot["usuario"],
                "sector": detalle["sector"],
                "alertas": detalle["alertas"],
                "ciclos": detalle["ciclos"],
            }
        ), 200

    @app.post("/login")
    def loginWeb():
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        usuario = repositorio.obtenerUsuarioPorEmail(email)
        if not usuario or not verificarPassword(password, usuario["password_hash"]):
            repositorio.registrarAuditoriaEnBD(
                email or "ANONIMO", "LOGIN_FALLIDO", "Credenciales inválidas", reloj.ahora()
            )
            return redirect(url_for("index", error="Credenciales inválidas"))

        session["usuario_email"] = usuario["email"]
        session["usuario_nombre"] = usuario["nombre"]
        session["usuario_rol"] = usuario["rol"]
        repositorio.registrarAuditoriaEnBD(
            usuario["email"], "LOGIN_EXITOSO", f"Rol={usuario['rol']}", reloj.ahora()
        )
        return redirect(url_for("index"))

    @app.post("/logout")
    def logoutWeb():
        usuario = _usuarioActual()
        if usuario:
            repositorio.registrarAuditoriaEnBD(
                usuario["email"], "LOGOUT", "Cierre de sesión", reloj.ahora()
            )
        session.clear()
        return redirect(url_for("index"))

    @app.post("/api/auth/login")
    def apiLogin():
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        usuario = repositorio.obtenerUsuarioPorEmail(email)
        if not usuario or not verificarPassword(password, usuario["password_hash"]):
            return jsonify({"error": "Credenciales inválidas"}), 401
        session["usuario_email"] = usuario["email"]
        session["usuario_nombre"] = usuario["nombre"]
        session["usuario_rol"] = usuario["rol"]
        return jsonify({"email": usuario["email"], "nombre": usuario["nombre"], "rol": usuario["rol"]}), 200

    @app.post("/api/auth/logout")
    def apiLogout():
        session.clear()
        return jsonify({"ok": True}), 200

    @app.get("/api/estado")
    def apiEstado():
        if es_serverless:
            ahora_ts = time.time()
            if ahora_ts - getattr(app, "_ultimo_tick_serverless", 0) >= 2.0:
                setattr(app, "_ultimo_tick_serverless", ahora_ts)
                try:
                    simulador.ejecutarCicloTick()
                except Exception:
                    pass
        return jsonify(_construirSnapshot()), 200

    @app.post("/api/lecturas")
    def apiPostLectura():
        token = request.headers.get("X-Device-Token", "")
        payload = request.get_json(silent=True) or {}
        res = controlador.postLecturaTelemetria(payload, token, instanteActual=reloj.ahora())
        return jsonify(res["body"]), res["httpStatus"]

    @app.put("/api/nodos/<idNodo>/estado")
    def apiPutEstadoNodo(idNodo: str):
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        data = request.get_json(silent=True) or {}
        encendido = bool(data.get("encendido", True))
        res = controlador.putEstadoNodo(
            idNodo=idNodo,
            encendido=encendido,
            rolHeader=usuario["rol"],
            usuarioEmail=usuario["email"],
            instanteActual=reloj.ahora(),
        )
        return jsonify(res["body"]), res["httpStatus"]

    @app.put("/api/sectores/<idSector>/umbrales")
    def apiPutUmbrales(idSector: str):
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        data = request.get_json(silent=True) or {}
        try:
            critico = float(data["umbralCritico"])
            minimo = float(data["umbralMinimo"])
            objetivo = float(data["umbralObjetivo"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Parámetros numéricos requeridos"}), 400
        res = controlador.putUmbralesSector(
            idSector=idSector,
            critico=critico,
            minimo=minimo,
            objetivo=objetivo,
            rolHeader=usuario["rol"],
            usuarioEmail=usuario["email"],
            instanteActual=reloj.ahora(),
        )
        return jsonify(res["body"]), res["httpStatus"]

    @app.post("/api/sectores/<idSector>/restablecer")
    def apiRestablecerSector(idSector: str):
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        try:
            rol = RolUsuario(usuario["rol"])
            sector = servicio.restablecerErrorValvula(idSector, rol, usuario["email"], reloj.ahora())
            return jsonify({"idSector": sector.idSector, "estadoActual": sector.estadoActual.value}), 200
        except Exception as exc:
            status = getattr(exc, "httpStatus", 400)
            return jsonify({"error": str(exc)}), status

    @app.post("/api/alertas/<idAlerta>/reconocer")
    def apiReconocerAlerta(idAlerta: str):
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        if usuario["rol"] not in {RolUsuario.TECNICO_AGRICOLA.value, RolUsuario.ADMINISTRADOR.value}:
            return jsonify({"error": "Permiso RBAC insuficiente"}), 403
        for s in repositorio.listarSectores():
            for a in s.alertas:
                if a.idAlerta == idAlerta:
                    a.reconocer()
                    repositorio.guardarSector(s)
                    repositorio.registrarAuditoriaEnBD(
                        usuario["email"], "RECONOCER_ALERTA", idAlerta, reloj.ahora()
                    )
                    return jsonify({"idAlerta": idAlerta, "reconocida": True}), 200
        return jsonify({"error": "Alerta no encontrada"}), 404

    @app.get("/api/reportes/excel")
    def apiExportarExcel():
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        if usuario["rol"] not in {RolUsuario.GESTOR_SENSORES.value, RolUsuario.TECNICO_AGRICOLA.value, RolUsuario.ADMINISTRADOR.value}:
            return jsonify({"error": "Solo Gestor de Sensores, Técnico Agrícola o Administrador pueden exportar reportes"}), 403
        sectores = repositorio.listarSectores()
        archivoBytes = controlador.generarArchivoXlsxBytes(sectores)
        repositorio.registrarAuditoriaEnBD(
            usuario["email"], "EXPORTAR_EXCEL", f"Exportados {len(sectores)} sectores", reloj.ahora()
        )
        return Response(
            archivoBytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=AgriTech_Reporte_Consolidado.xlsx"},
        )

    @app.get("/api/auditoria")
    def apiAuditoria():
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        if usuario["rol"] != RolUsuario.ADMINISTRADOR.value:
            return jsonify({"error": "Acceso restringido a Administrador del Sistema"}), 403
        return jsonify({"eventos": repositorio.obtenerAuditoria(50)}), 200

    @app.post("/api/simulador/tick")
    def apiSimuladorTick():
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        resultados = simulador.ejecutarCicloTick()
        return jsonify({"resultados": resultados, "relojSimulado": reloj.ahora().isoformat()}), 200

    @app.post("/api/simulador/escenario")
    def apiSimuladorEscenario():
        usuario = _usuarioActual()
        if not usuario:
            return jsonify({"error": "Autenticación requerida"}), 401
        data = request.get_json(silent=True) or {}
        idSector = str(data.get("idSector", "SEC-01"))
        escenario = str(data.get("escenario", "normalizar"))
        res = simulador.activarEscenario(idSector, escenario)
        repositorio.registrarAuditoriaEnBD(
            usuario["email"], "SIMULADOR_ESCENARIO", f"{idSector}: {escenario}", reloj.ahora()
        )
        return jsonify(res), 200

    return app


if __name__ == "__main__":
    appSim = create_app(iniciarSimulador=True)
    port = int(os.environ.get("PORT", "5000"))
    appSim.run(host="0.0.0.0", port=port, debug=False)
