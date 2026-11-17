"""Estrategias de cálculo agronómico de riego (Patrón Strategy GoF)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IEstrategiaRiego(ABC):
    """Interfaz pública del patrón Strategy para calcular la lámina de riego."""

    @abstractmethod
    def calcularLaminaRiego(
        self,
        humedadActual: float,
        umbralMinimo: float,
        umbralCritico: float,
        umbralObjetivo: float,
        probLluvia: float,
        tempSuelo: float,
    ) -> float:
        """Calcula la lámina de riego requerida en milímetros (mm)."""


class EstrategiaRiegoAgronomico(IEstrategiaRiego):
    """Implementación agronómica con complejidad ciclomática v(G) = 6 (P = 5)."""

    def calcularLaminaRiego(
        self,
        humedadActual: float,
        umbralMinimo: float,
        umbralCritico: float,
        umbralObjetivo: float,
        probLluvia: float,
        tempSuelo: float,
    ) -> float:
        """Determina si se requiere riego y calcula la lámina neta (v(G) = 6 <= 10)."""
        if humedadActual >= umbralMinimo:  # P1
            return 0.0
        if humedadActual >= umbralCritico:  # P2
            if probLluvia > 70.0:  # P3
                return 0.0
        deficitPorcentual = umbralObjetivo - humedadActual
        if deficitPorcentual <= 0.0:  # P4
            return 0.0
        laminaBase = deficitPorcentual * 0.45
        if tempSuelo >= 30.0:  # P5
            laminaBase = laminaBase * 1.15
        return round(laminaBase, 2)
