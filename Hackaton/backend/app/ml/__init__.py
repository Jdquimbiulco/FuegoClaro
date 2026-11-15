"""Pipeline de machine learning para el riesgo de incendios de FuegoClaro.

El paquete es independiente de FastAPI: los scripts de ``scripts/`` lo
importan para construir el dataset, entrenar el modelo y ejecutar la
inferencia. Se mantiene dentro de ``backend/app/ml`` para poder reutilizarlo
desde la API en una fase posterior.
"""

__all__ = ["grid", "external", "features", "dataset", "training", "inference"]
