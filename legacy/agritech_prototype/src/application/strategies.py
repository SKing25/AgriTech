"""Patrón GoF Strategy para el cálculo de lámina de riego y evaluación hídrica."""
from abc import ABC, abstractmethod


class IEstrategiaRiego(ABC):
    """Interfaz Strategy para algoritmos de cálculo de lámina de riego."""

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
        """Calcula los milímetros de agua a aplicar (0.0 si no debe regarse)."""


class EstrategiaRiegoAgronomico(IEstrategiaRiego):
    """
    Implementación concreta del algoritmo de riego de precisión (RF-04, RF-05).
    Complejidad Ciclomática de McCabe: P = 5 nodos predicado -> v(G) = P + 1 = 6 <= 10 (RNF-06).
    """

    def calcularLaminaRiego(
        self,
        humedadActual: float,
        umbralMinimo: float,
        umbralCritico: float,
        umbralObjetivo: float,
        probLluvia: float,
        tempSuelo: float,
    ) -> float:
        # P1: Si la humedad es igual o superior al umbral mínimo, no se requiere riego (Flujo A3)
        if humedadActual >= umbralMinimo:
            return 0.0

        # P2: Evaluación de pronóstico de lluvia (RF-05)
        if probLluvia > 70.0:
            # P3: Si la humedad no es crítica (>= umbralCritico), se pospone el riego (Flujo A2)
            if humedadActual >= umbralCritico:
                return 0.0

        # Cálculo de lámina base proporcional al déficit hídrico
        deficitHidrico = umbralObjetivo - humedadActual
        laminaMm = deficitHidrico * 0.45

        # P4: Incremento del 20% por déficit hídrico crítico (< 15%)
        if humedadActual < umbralCritico:
            laminaMm = laminaMm * 1.20

        # P5: Incremento del 15% por alta evaporación cuando la temperatura del suelo >= 35 °C
        if tempSuelo >= 35.0:
            laminaMm = laminaMm * 1.15

        return round(laminaMm, 2)
