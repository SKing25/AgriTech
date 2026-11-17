"""Controlador REST <<boundary>> y generador de reportes Excel (.xlsx)."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from ..application.services import ServicioMonitoreoRiego
from ..domain.entities import SectorAgricola
from ..domain.enums import RolUsuario
from ..domain.exceptions import (
    AccesoNoAutorizadoError,
    DominioAgriTechError,
    EntidadNoEncontradaError,
    TelemetriaFueraDeRangoError,
    TokenDispositivoInvalidoError,
)

TZ_BOGOTA = ZoneInfo("America/Bogota")


class ControladorTelemetriaREST:
    """Adaptador de entrada HTTP <<boundary>> alineado con IE-02, SEG-01 y RF-06."""

    def __init__(self, servicio: ServicioMonitoreoRiego) -> None:
        self.servicio = servicio

    def postLecturaTelemetria(
        self,
        payload: Dict[str, Any],
        tokenHeader: str,
        instanteActual: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Procesa POST /api/lecturas devolviendo código HTTP y cuerpo normalizado."""
        try:
            idNodo = str(payload["idNodo"])
            humedad = float(payload["humedadSuelo"])
            tempSuelo = float(payload["temperaturaSuelo"])
            tempAmb = float(payload["temperaturaAmbiente"]) if "temperaturaAmbiente" in payload else None
            hrAmb = float(payload["humedadRelativa"]) if "humedadRelativa" in payload else None
            horasFungo = int(payload.get("horasCondicionFungo", 0))
            horasCalor = int(payload.get("horasCalorSuelo", 0))
            if "timestamp" in payload and isinstance(payload["timestamp"], str):
                ts = datetime.fromisoformat(payload["timestamp"])
            else:
                ts = instanteActual or datetime.now(TZ_BOGOTA)
        except (KeyError, TypeError, ValueError) as exc:
            return {
                "httpStatus": 400,
                "body": {"error": "Payload telemétrico incompleto o mal formado", "detalle": str(exc)},
            }

        try:
            resultado = self.servicio.procesarTelemetria(
                idNodo=idNodo,
                humedadSuelo=humedad,
                temperaturaSuelo=tempSuelo,
                token=tokenHeader,
                timestamp=ts,
                horasCondicionFungo=horasFungo,
                horasCalorSuelo=horasCalor,
                temperaturaAmbiente=tempAmb,
                humedadRelativa=hrAmb,
            )
            return {
                "httpStatus": 201,
                "body": {
                    "idSector": resultado.idSector,
                    "estadoSector": resultado.estadoSector.value,
                    "accionTomada": resultado.accionTomada,
                    "cicloActivo": resultado.cicloActivo.idCiclo if resultado.cicloActivo else None,
                    "estadoCiclo": resultado.cicloActivo.estado.value if resultado.cicloActivo else None,
                    "alerta": resultado.alertaGenerada.tipoAlerta.value if resultado.alertaGenerada else None,
                },
            }
        except (TokenDispositivoInvalidoError, TelemetriaFueraDeRangoError, EntidadNoEncontradaError) as exc:
            return {"httpStatus": exc.httpStatus, "body": {"error": str(exc)}}
        except DominioAgriTechError as exc:
            return {"httpStatus": exc.httpStatus, "body": {"error": str(exc)}}

    def putEstadoNodo(
        self,
        idNodo: str,
        encendido: bool,
        rolHeader: str,
        usuarioEmail: str,
        instanteActual: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Procesa actualización de estado de NodoSensorIoT bajo RBAC (HTTP 200 / 403 / 404)."""
        try:
            rol = RolUsuario(rolHeader)
        except ValueError:
            return {"httpStatus": 403, "body": {"error": f"Rol desconocido: {rolHeader}"}}

        ts = instanteActual or datetime.now(TZ_BOGOTA)
        try:
            sensor = self.servicio.cambiarEstadoNodo(idNodo, encendido, rol, usuarioEmail, ts)
            return {
                "httpStatus": 200,
                "body": {"idNodo": sensor.idNodo, "estadoOperativo": sensor.estadoOperativo.value},
            }
        except (AccesoNoAutorizadoError, EntidadNoEncontradaError) as exc:
            return {"httpStatus": exc.httpStatus, "body": {"error": str(exc)}}

    def putUmbralesSector(
        self,
        idSector: str,
        critico: float,
        minimo: float,
        objetivo: float,
        rolHeader: str,
        usuarioEmail: str,
        instanteActual: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Procesa actualización de umbrales agronómicos bajo RBAC (HTTP 200 / 400 / 403 / 404)."""
        try:
            rol = RolUsuario(rolHeader)
        except ValueError:
            return {"httpStatus": 403, "body": {"error": f"Rol desconocido: {rolHeader}"}}

        ts = instanteActual or datetime.now(TZ_BOGOTA)
        try:
            sector = self.servicio.configurarUmbralesSector(
                idSector, critico, minimo, objetivo, rol, usuarioEmail, ts
            )
            return {
                "httpStatus": 200,
                "body": {
                    "idSector": sector.idSector,
                    "umbralCritico": sector.umbralCritico,
                    "umbralMinimo": sector.umbralMinimo,
                    "umbralObjetivo": sector.umbralObjetivo,
                },
            }
        except DominioAgriTechError as exc:
            return {"httpStatus": exc.httpStatus, "body": {"error": str(exc)}}

    @staticmethod
    def _enRango(ts: datetime, inicio: Optional[datetime], fin: Optional[datetime]) -> bool:
        tsNorm = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if inicio is not None:
            iNorm = inicio if inicio.tzinfo else inicio.replace(tzinfo=timezone.utc)
            if tsNorm < iNorm:
                return False
        if fin is not None:
            fNorm = fin if fin.tzinfo else fin.replace(tzinfo=timezone.utc)
            if tsNorm > fNorm:
                return False
        return True

    def exportarFilasInformeExcel(
        self,
        sectores: List[SectorAgricola],
        fechaInicio: Optional[datetime] = None,
        fechaFin: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Construye la tabla estructurada consolidada (lecturas, ciclos y alertas) para exportación RF-06."""
        filas: List[Dict[str, Any]] = []
        for s in sectores:
            for lec in s.lecturas:
                if self._enRango(lec.timestamp, fechaInicio, fechaFin):
                    filas.append(
                        {
                            "tipoRegistro": "LECTURA",
                            "idSector": s.idSector,
                            "sectorNombre": s.nombre,
                            "referencia": lec.idLectura,
                            "timestamp": lec.timestamp.isoformat(),
                            "humedadSuelo": lec.humedadSuelo,
                            "temperaturaSuelo": lec.temperaturaSuelo,
                            "humedadRelativa": lec.humedadRelativa,
                            "detalle": f"Nodo {lec.idNodo}",
                        }
                    )
            for cic in s.ciclosRiego:
                if self._enRango(cic.fechaInicio, fechaInicio, fechaFin):
                    filas.append(
                        {
                            "tipoRegistro": "CICLO_RIEGO",
                            "idSector": s.idSector,
                            "sectorNombre": s.nombre,
                            "referencia": cic.idCiclo,
                            "timestamp": cic.fechaInicio.isoformat(),
                            "humedadSuelo": cic.humedadFinal if cic.humedadFinal is not None else cic.humedadInicial,
                            "temperaturaSuelo": None,
                            "humedadRelativa": None,
                            "detalle": f"{cic.estado.value} ({cic.laminaAplicadaMm} mm, {cic.duracionSegundos}s)",
                        }
                    )
            for alt in s.alertas:
                if self._enRango(alt.timestampGeneracion, fechaInicio, fechaFin):
                    filas.append(
                        {
                            "tipoRegistro": "ALERTA",
                            "idSector": s.idSector,
                            "sectorNombre": s.nombre,
                            "referencia": alt.idAlerta,
                            "timestamp": alt.timestampGeneracion.isoformat(),
                            "humedadSuelo": None,
                            "temperaturaSuelo": None,
                            "humedadRelativa": None,
                            "detalle": f"{alt.tipoAlerta.value} [{alt.nivelSeveridad.value}]: {alt.mensaje}",
                        }
                    )
        return filas

    def generarArchivoXlsxBytes(
        self,
        sectores: List[SectorAgricola],
        fechaInicio: Optional[datetime] = None,
        fechaFin: Optional[datetime] = None,
    ) -> bytes:
        """Genera libro Excel (.xlsx) real con OpenPyXL para descarga directa (RF-06)."""
        wb = Workbook()
        headerFill = PatternFill(start_color="1B5E20", end_color="1B5E20", fill_type="solid")
        headerFont = Font(color="FFFFFF", bold=True)

        wsResumen = wb.active
        wsResumen.title = "Resumen Sectores"
        headersResumen = [
            "ID Sector",
            "Nombre",
            "Estado Actual",
            "Umbral Crítico (%)",
            "Umbral Mínimo (%)",
            "Umbral Objetivo (%)",
            "Total Lecturas",
            "Total Ciclos",
            "Total Alertas",
        ]
        wsResumen.append(headersResumen)
        for col in range(1, len(headersResumen) + 1):
            celda = wsResumen.cell(row=1, column=col)
            celda.fill = headerFill
            celda.font = headerFont

        for s in sectores:
            wsResumen.append(
                [
                    s.idSector,
                    s.nombre,
                    s.estadoActual.value,
                    s.umbralCritico,
                    s.umbralMinimo,
                    s.umbralObjetivo,
                    len(s.lecturas),
                    len(s.ciclosRiego),
                    len(s.alertas),
                ]
            )

        wsHist = wb.create_sheet("Registro Consolidado")
        headersHist = [
            "Tipo",
            "ID Sector",
            "Sector",
            "Referencia",
            "Fecha/Hora ISO",
            "Humedad Suelo (%)",
            "Temp. Suelo (°C)",
            "Humedad Relativa (%)",
            "Detalle",
        ]
        wsHist.append(headersHist)
        for col in range(1, len(headersHist) + 1):
            celda = wsHist.cell(row=1, column=col)
            celda.fill = headerFill
            celda.font = headerFont

        for fila in self.exportarFilasInformeExcel(sectores, fechaInicio, fechaFin):
            wsHist.append(
                [
                    fila["tipoRegistro"],
                    fila["idSector"],
                    fila["sectorNombre"],
                    fila["referencia"],
                    fila["timestamp"],
                    fila["humedadSuelo"],
                    fila["temperaturaSuelo"],
                    fila["humedadRelativa"],
                    fila["detalle"],
                ]
            )

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()
