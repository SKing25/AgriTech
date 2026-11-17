"""Persistencia relacional SQLite e inicialización de catálogo y cuentas RBAC."""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

import bcrypt

from ..application.ports import IRepositorioAgricola
from ..domain.entities import (
    AlertaTemprana,
    CicloRiego,
    LecturaTelemetria,
    SectorAgricola,
    SensorSuelo,
    ZonaCultivo,
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


def hashPassword(passwordPlano: str) -> str:
    """Genera hash bcrypt seguro con factor de costo >= 10 (SEG-03)."""
    hashed = bcrypt.hashpw(passwordPlano.encode("utf-8"), bcrypt.gensalt(rounds=10))
    return hashed.decode("utf-8")


def verificarPassword(passwordPlano: str, passwordHash: str) -> bool:
    """Verifica contraseña en texto plano contra hash bcrypt almacenado (SEG-03)."""
    try:
        return bcrypt.checkpw(passwordPlano.encode("utf-8"), passwordHash.encode("utf-8"))
    except ValueError:
        return False


class RepositorioSQLite(IRepositorioAgricola):
    """Implementación SQLite thread-safe del puerto IRepositorioAgricola."""

    def __init__(self, dbPath: str = "data/agritech.db") -> None:
        self.dbPath = dbPath
        self._lock = threading.RLock()
        if dbPath != ":memory:":
            parent = os.path.dirname(dbPath)
            if parent:
                os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(dbPath, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._crearEsquema()

    def _crearEsquema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS sectores (
                    id_sector TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    latitud REAL NOT NULL,
                    longitud REAL NOT NULL,
                    umbral_critico REAL NOT NULL,
                    umbral_minimo REAL NOT NULL,
                    umbral_objetivo REAL NOT NULL,
                    estado_actual TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS zonas_cultivo (
                    id_zona TEXT PRIMARY KEY,
                    id_sector TEXT NOT NULL,
                    tipo_cultivo TEXT NOT NULL,
                    area_hectareas REAL NOT NULL,
                    etapa_fenologica TEXT NOT NULL,
                    FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS sensores (
                    id_nodo TEXT PRIMARY KEY,
                    id_sector TEXT NOT NULL,
                    token_autenticacion TEXT NOT NULL,
                    estado_operativo TEXT NOT NULL,
                    bateria_porcentaje REAL NOT NULL,
                    FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS lecturas (
                    id_lectura TEXT PRIMARY KEY,
                    id_nodo TEXT NOT NULL,
                    id_sector TEXT NOT NULL,
                    humedad_suelo REAL NOT NULL,
                    temperatura_suelo REAL NOT NULL,
                    temperatura_ambiente REAL NOT NULL,
                    humedad_relativa REAL NOT NULL,
                    timestamp_iso TEXT NOT NULL,
                    es_valida INTEGER NOT NULL,
                    FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS ciclos_riego (
                    id_ciclo TEXT PRIMARY KEY,
                    id_sector TEXT NOT NULL,
                    estado TEXT NOT NULL,
                    subestado_regando TEXT,
                    lamina_aplicada_mm REAL NOT NULL,
                    humedad_inicial REAL NOT NULL,
                    humedad_final REAL,
                    fecha_inicio_iso TEXT NOT NULL,
                    fecha_fin_iso TEXT,
                    duracion_segundos INTEGER NOT NULL,
                    motivo_cierre TEXT,
                    FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS alertas (
                    id_alerta TEXT PRIMARY KEY,
                    id_sector TEXT NOT NULL,
                    tipo_alerta TEXT NOT NULL,
                    nivel_severidad TEXT NOT NULL,
                    mensaje TEXT NOT NULL,
                    timestamp_iso TEXT NOT NULL,
                    reconocida INTEGER NOT NULL,
                    FOREIGN KEY (id_sector) REFERENCES sectores(id_sector) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS usuarios (
                    email TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    rol TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS bitacora_auditoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL,
                    operacion TEXT NOT NULL,
                    detalle TEXT NOT NULL,
                    timestamp_iso TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def _cargarSectorDesdeFila(self, row: sqlite3.Row) -> SectorAgricola:
        idSector = row["id_sector"]
        zonas = [
            ZonaCultivo(
                idZona=z["id_zona"],
                tipoCultivo=z["tipo_cultivo"],
                areaHectareas=float(z["area_hectareas"]),
                etapaFenologica=z["etapa_fenologica"],
            )
            for z in self._conn.execute(
                "SELECT * FROM zonas_cultivo WHERE id_sector = ? ORDER BY id_zona", (idSector,)
            ).fetchall()
        ]
        sensores = [
            SensorSuelo(
                idNodo=s["id_nodo"],
                tokenAutenticacion=s["token_autenticacion"],
                estadoOperativo=EstadoSensor(s["estado_operativo"]),
                bateriaPorcentaje=float(s["bateria_porcentaje"]),
            )
            for s in self._conn.execute(
                "SELECT * FROM sensores WHERE id_sector = ? ORDER BY id_nodo", (idSector,)
            ).fetchall()
        ]
        lecturas = [
            LecturaTelemetria(
                idLectura=l["id_lectura"],
                idNodo=l["id_nodo"],
                idSector=l["id_sector"],
                humedadSuelo=float(l["humedad_suelo"]),
                temperaturaSuelo=float(l["temperatura_suelo"]),
                temperaturaAmbiente=float(l["temperatura_ambiente"]),
                humedadRelativa=float(l["humedad_relativa"]),
                timestamp=datetime.fromisoformat(l["timestamp_iso"]),
                esValida=bool(l["es_valida"]),
            )
            for l in self._conn.execute(
                "SELECT * FROM lecturas WHERE id_sector = ? ORDER BY timestamp_iso ASC", (idSector,)
            ).fetchall()
        ]
        ciclos = [
            CicloRiego(
                idCiclo=c["id_ciclo"],
                idSector=c["id_sector"],
                estado=EstadoCicloRiego(c["estado"]),
                subestadoRegando=c["subestado_regando"],
                laminaAplicadaMm=float(c["lamina_aplicada_mm"]),
                humedadInicial=float(c["humedad_inicial"]),
                humedadFinal=float(c["humedad_final"]) if c["humedad_final"] is not None else None,
                fechaInicio=datetime.fromisoformat(c["fecha_inicio_iso"]),
                fechaFin=datetime.fromisoformat(c["fecha_fin_iso"]) if c["fecha_fin_iso"] else None,
                duracionSegundos=int(c["duracion_segundos"]),
                motivoCierre=MotivoCierreRiego(c["motivo_cierre"]) if c["motivo_cierre"] else None,
            )
            for c in self._conn.execute(
                "SELECT * FROM ciclos_riego WHERE id_sector = ? ORDER BY fecha_inicio_iso ASC",
                (idSector,),
            ).fetchall()
        ]
        alertas = [
            AlertaTemprana(
                idAlerta=a["id_alerta"],
                idSector=a["id_sector"],
                tipoAlerta=TipoAlerta(a["tipo_alerta"]),
                nivelSeveridad=NivelSeveridad(a["nivel_severidad"]),
                mensaje=a["mensaje"],
                timestampGeneracion=datetime.fromisoformat(a["timestamp_iso"]),
                reconocida=bool(a["reconocida"]),
            )
            for a in self._conn.execute(
                "SELECT * FROM alertas WHERE id_sector = ? ORDER BY timestamp_iso ASC", (idSector,)
            ).fetchall()
        ]
        return SectorAgricola(
            idSector=idSector,
            nombre=row["nombre"],
            latitud=float(row["latitud"]),
            longitud=float(row["longitud"]),
            umbralCritico=float(row["umbral_critico"]),
            umbralMinimo=float(row["umbral_minimo"]),
            umbralObjetivo=float(row["umbral_objetivo"]),
            estadoActual=EstadoSector(row["estado_actual"]),
            zonas=zonas,
            sensores=sensores,
            lecturas=lecturas,
            ciclosRiego=ciclos,
            alertas=alertas,
        )

    def obtenerSector(self, idSector: str) -> Optional[SectorAgricola]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sectores WHERE id_sector = ?", (idSector,)
            ).fetchone()
            return self._cargarSectorDesdeFila(row) if row else None

    def obtenerSectorPorNodo(self, idNodo: str) -> Optional[SectorAgricola]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id_sector FROM sensores WHERE id_nodo = ?", (idNodo,)
            ).fetchone()
            if not row:
                return None
            return self.obtenerSector(row["id_sector"])

    def obtenerSensor(self, idNodo: str) -> Optional[SensorSuelo]:
        with self._lock:
            s = self._conn.execute(
                "SELECT * FROM sensores WHERE id_nodo = ?", (idNodo,)
            ).fetchone()
            if not s:
                return None
            return SensorSuelo(
                idNodo=s["id_nodo"],
                tokenAutenticacion=s["token_autenticacion"],
                estadoOperativo=EstadoSensor(s["estado_operativo"]),
                bateriaPorcentaje=float(s["bateria_porcentaje"]),
            )

    def guardarSector(self, sector: SectorAgricola) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO sectores (id_sector, nombre, latitud, longitud, umbral_critico, umbral_minimo, umbral_objetivo, estado_actual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id_sector) DO UPDATE SET
                    nombre=excluded.nombre,
                    latitud=excluded.latitud,
                    longitud=excluded.longitud,
                    umbral_critico=excluded.umbral_critico,
                    umbral_minimo=excluded.umbral_minimo,
                    umbral_objetivo=excluded.umbral_objetivo,
                    estado_actual=excluded.estado_actual
                """,
                (
                    sector.idSector,
                    sector.nombre,
                    sector.latitud,
                    sector.longitud,
                    sector.umbralCritico,
                    sector.umbralMinimo,
                    sector.umbralObjetivo,
                    sector.estadoActual.value,
                ),
            )
            for z in sector.zonas:
                cur.execute(
                    """
                    INSERT INTO zonas_cultivo (id_zona, id_sector, tipo_cultivo, area_hectareas, etapa_fenologica)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id_zona) DO UPDATE SET
                        tipo_cultivo=excluded.tipo_cultivo,
                        area_hectareas=excluded.area_hectareas,
                        etapa_fenologica=excluded.etapa_fenologica
                    """,
                    (z.idZona, sector.idSector, z.tipoCultivo, z.areaHectareas, z.etapaFenologica),
                )
            for s in sector.sensores:
                cur.execute(
                    """
                    INSERT INTO sensores (id_nodo, id_sector, token_autenticacion, estado_operativo, bateria_porcentaje)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id_nodo) DO UPDATE SET
                        token_autenticacion=excluded.token_autenticacion,
                        estado_operativo=excluded.estado_operativo,
                        bateria_porcentaje=excluded.bateria_porcentaje
                    """,
                    (
                        s.idNodo,
                        sector.idSector,
                        s.tokenAutenticacion,
                        s.estadoOperativo.value,
                        s.bateriaPorcentaje,
                    ),
                )
            for l in sector.lecturas:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO lecturas (id_lectura, id_nodo, id_sector, humedad_suelo, temperatura_suelo, temperatura_ambiente, humedad_relativa, timestamp_iso, es_valida)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        l.idLectura,
                        l.idNodo,
                        l.idSector,
                        l.humedadSuelo,
                        l.temperaturaSuelo,
                        l.temperaturaAmbiente,
                        l.humedadRelativa,
                        l.timestamp.isoformat(),
                        1 if l.esValida else 0,
                    ),
                )
            for c in sector.ciclosRiego:
                cur.execute(
                    """
                    INSERT INTO ciclos_riego (id_ciclo, id_sector, estado, subestado_regando, lamina_aplicada_mm, humedad_inicial, humedad_final, fecha_inicio_iso, fecha_fin_iso, duracion_segundos, motivo_cierre)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id_ciclo) DO UPDATE SET
                        estado=excluded.estado,
                        subestado_regando=excluded.subestado_regando,
                        lamina_aplicada_mm=excluded.lamina_aplicada_mm,
                        humedad_final=excluded.humedad_final,
                        fecha_fin_iso=excluded.fecha_fin_iso,
                        duracion_segundos=excluded.duracion_segundos,
                        motivo_cierre=excluded.motivo_cierre
                    """,
                    (
                        c.idCiclo,
                        c.idSector,
                        c.estado.value,
                        c.subestadoRegando,
                        c.laminaAplicadaMm,
                        c.humedadInicial,
                        c.humedadFinal,
                        c.fechaInicio.isoformat(),
                        c.fechaFin.isoformat() if c.fechaFin else None,
                        c.duracionSegundos,
                        c.motivoCierre.value if c.motivoCierre else None,
                    ),
                )
            for a in sector.alertas:
                cur.execute(
                    """
                    INSERT INTO alertas (id_alerta, id_sector, tipo_alerta, nivel_severidad, mensaje, timestamp_iso, reconocida)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id_alerta) DO UPDATE SET reconocida=excluded.reconocida
                    """,
                    (
                        a.idAlerta,
                        a.idSector,
                        a.tipoAlerta.value,
                        a.nivelSeveridad.value,
                        a.mensaje,
                        a.timestampGeneracion.isoformat(),
                        1 if a.reconocida else 0,
                    ),
                )
            self._conn.commit()

    def listarSectores(self) -> List[SectorAgricola]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM sectores ORDER BY id_sector").fetchall()
            return [self._cargarSectorDesdeFila(r) for r in rows]

    def guardarCuenta(self, email: str, nombre: str, rol: RolUsuario, passwordHash: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO usuarios (email, nombre, rol, password_hash)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    nombre=excluded.nombre,
                    rol=excluded.rol,
                    password_hash=excluded.password_hash
                """,
                (email.lower().strip(), nombre, rol.value, passwordHash),
            )
            self._conn.commit()

    def obtenerUsuarioPorEmail(self, email: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM usuarios WHERE email = ?", (email.lower().strip(),)
            ).fetchone()
            return dict(row) if row else None

    def registrarAuditoriaEnBD(
        self,
        usuario: str,
        operacion: str,
        detalle: str,
        timestamp: datetime,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO bitacora_auditoria (usuario, operacion, detalle, timestamp_iso) VALUES (?, ?, ?, ?)",
                (usuario, operacion, detalle, timestamp.isoformat()),
            )
            self._conn.commit()

    def obtenerAuditoria(self, limite: int = 100) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM bitacora_auditoria ORDER BY id DESC LIMIT ?", (limite,)
            ).fetchall()
            return [dict(r) for r in rows]

    def sembrarDatosIniciales(self) -> None:
        """Siembra los 3 sectores/nodos de AgriTech Precision y las 3 cuentas RBAC si no existen."""
        if not self.listarSectores():
            s1 = SectorAgricola("SEC-01", "Sector Norte — Papa Pastusa", 4.748, -74.065)
            s1.agregarZonaCultivo(ZonaCultivo("ZON-01", "Papa Pastusa", 3.5, "Floración"))
            s1.agregarSensorSuelo(SensorSuelo("NODO-01", "tk-nodo-01-agritech", EstadoSensor.ACTIVO, 94.0))

            s2 = SectorAgricola("SEC-02", "Sector Centro — Fresa Albión", 4.872, -74.144)
            s2.agregarZonaCultivo(ZonaCultivo("ZON-02", "Fresa Albión", 2.2, "Fructificación"))
            s2.agregarSensorSuelo(SensorSuelo("NODO-02", "tk-nodo-02-agritech", EstadoSensor.ACTIVO, 88.5))

            s3 = SectorAgricola("SEC-03", "Sector Sur — Lechuga Crespa", 4.861, -74.058)
            s3.agregarZonaCultivo(ZonaCultivo("ZON-03", "Lechuga Crespa", 1.8, "Crecimiento Vegetativo"))
            s3.agregarSensorSuelo(SensorSuelo("NODO-03", "tk-nodo-03-agritech", EstadoSensor.ACTIVO, 91.2))

            for sector in (s1, s2, s3):
                self.guardarSector(sector)

        cuentasDefecto = [
            ("gestor@agritech.co", "Gestor de Sensores", RolUsuario.GESTOR_SENSORES, "AgriGestor2026!"),
            ("tecnico@agritech.co", "Técnico Agrícola", RolUsuario.TECNICO_AGRICOLA, "AgriTecnico2026!"),
            ("admin@agritech.co", "Administrador del Sistema", RolUsuario.ADMINISTRADOR, "AgriAdmin2026!"),
        ]
        for email, nombre, rol, clave in cuentasDefecto:
            if not self.obtenerUsuarioPorEmail(email):
                self.guardarCuenta(email, nombre, rol, hashPassword(clave))

    def cerrar(self) -> None:
        with self._lock:
            self._conn.close()
