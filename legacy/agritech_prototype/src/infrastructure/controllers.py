"""Controlador <<boundary>> que expone las interfaces IE-01 e IE-02 y generación de reportes."""
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.application.services import ServicioMonitoreoRiego
from src.domain.enums import RolUsuario
from src.domain.exceptions import (
    AccesoNoAutorizadoError,
    DispositivoNoAutorizadoError,
    UmbralInvalidoError,
)


class ControladorTelemetriaREST:
    """
    Componente <<boundary>> de la arquitectura MVC (RD-02).
    Traduce las peticiones de interfaz web y sensores IoT hacia ServicioMonitoreoRiego.
    """

    def __init__(self, servicio: ServicioMonitoreoRiego) -> None:
        self._servicio = servicio

    def postLecturaTelemetria(
        self, payload: Dict[str, Any], tokenHeader: str
    ) -> Dict[str, Any]:
        """
        Endpoint POST /api/lecturas (IE-02).
        Retorna 201 (aceptada), 400 (datos inválidos) o 401 (no autorizado).
        """
        try:
            timestampStr = payload.get("timestamp")
            timestamp = (
                datetime.fromisoformat(timestampStr)
                if isinstance(timestampStr, str)
                else datetime.now()
            )
            resultado = self._servicio.procesarTelemetria(
                idNodo=str(payload.get("id_nodo", "")),
                humedadSuelo=payload.get("humedad"),
                temperaturaSuelo=payload.get("temperatura"),
                token=tokenHeader,
                timestamp=timestamp,
                horasCondicionFungo=int(payload.get("horas_condicion_fungo", 0)),
                horasCalorSuelo=int(payload.get("horas_calor_suelo", 0)),
            )
            return {
                "status_code": resultado.codigoHttp,
                "lectura_valida": resultado.lecturaValida,
                "estado_sector": resultado.estadoSector,
                "estado_valvula": resultado.estadoValvula,
                "lamina_agua_mm": resultado.laminaAguaMm,
                "alerta": (
                    resultado.alertaGenerada.tipoAlerta.value
                    if resultado.alertaGenerada
                    else None
                ),
                "mensaje": resultado.mensaje,
            }
        except DispositivoNoAutorizadoError as exc:
            return {"status_code": 401, "error": str(exc)}

    def putEstadoNodo(
        self,
        idNodo: str,
        encendido: bool,
        rolHeader: str,
        usuarioEmail: str,
    ) -> Dict[str, Any]:
        """Endpoint PUT /api/nodos/{id_nodo} (RF-02, SEG-01)."""
        try:
            rol = RolUsuario(rolHeader)
            sensor = self._servicio.cambiarEstadoNodo(
                idNodo=idNodo,
                encendido=encendido,
                rolUsuario=rol,
                usuarioEmail=usuarioEmail,
                timestamp=datetime.now(),
            )
            return {
                "status_code": 200,
                "id_nodo": sensor.idNodo,
                "encendido": sensor.encendido,
                "intervalo_s": sensor.intervaloSegundos,
            }
        except AccesoNoAutorizadoError as exc:
            return {"status_code": 403, "error": str(exc)}
        except DispositivoNoAutorizadoError as exc:
            return {"status_code": 404, "error": str(exc)}

    def exportarFilasInformeExcel(
        self,
        sectores: List[Any],
        fechaInicio: Optional[datetime] = None,
        fechaFin: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Genera las filas estructuradas del informe Excel .xlsx (RF-03, F4)."""
        filas: List[Dict[str, Any]] = []
        for sector in sectores:
            for lectura in sector.lecturas:
                if not lectura.esValida:
                    continue
                if fechaInicio and lectura.timestamp < fechaInicio:
                    continue
                if fechaFin and lectura.timestamp > fechaFin:
                    continue
                filas.append(
                    {
                        "sector": sector.idSector,
                        "nodo": lectura.idNodo,
                        "fecha_hora": lectura.timestamp.isoformat(),
                        "humedad": lectura.humedadSuelo,
                        "temperatura": lectura.temperaturaSuelo,
                    }
                )
        return filas
