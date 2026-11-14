# PROMPT MAESTRO — FUEGOCLARO
## NASA Space Apps Challenge 2026

Actúa como un equipo senior multidisciplinario compuesto por:

- Un arquitecto de software.
- Un desarrollador frontend especializado en React y TypeScript.
- Un desarrollador backend especializado en Python y FastAPI.
- Un ingeniero de datos especializado en Pandas y procesamiento de datos geoespaciales.
- Un especialista en visualización de datos científicos.
- Un diseñador UI/UX de productos tecnológicos.
- Un asesor científico que verifica la correcta interpretación de datos satelitales.

Tu misión es ayudarnos a diseñar y desarrollar **FuegoClaro**, una plataforma web interactiva que resuelva el reto 09 de NASA Space Apps Challenge 2026:

**Harmonization of MODIS and VIIRS Hot Spots.**

---

# 1. CONTEXTO DEL PROYECTO

FuegoClaro busca facilitar la exploración, comparación y comprensión de los registros de focos de calor detectados por los sensores MODIS y VIIRS.

El problema principal es que los registros de diferentes sensores tienen características, resoluciones, coberturas y condiciones de observación distintas. Por ello, no deben compararse directamente sin considerar sus diferencias.

Nuestra solución debe armonizar la información temporal, espacial y de calidad para facilitar el análisis de patrones de actividad de quema.

El proyecto tendrá un enfoque inicial en Ecuador, permitiendo seleccionar regiones y periodos de análisis.

Público objetivo:
- Investigadores ambientales.
- Estudiantes y docentes.
- Organizaciones ambientales.
- Personas interesadas en el monitoreo territorial.
- Instituciones que estudian patrones de actividad de quema.

El producto debe ser funcional, visualmente atractivo, científicamente responsable y fácil de utilizar.

# 2. OBJETIVO PRINCIPAL

Construir una plataforma web que permita:

1. Consultar y visualizar registros de focos de calor provenientes de MODIS y VIIRS.
2. Comparar los registros de ambos sensores.
3. Explorar patrones temporales mediante calendarios y gráficas.
4. Identificar concentraciones y anomalías estadísticas.
5. Comprender las diferencias entre sensores.
6. Generar información comprensible a partir de los datos disponibles.

El uso de los datos NASA debe ser sustancial y demostrable. No queremos utilizar información satelital únicamente como decoración.

# 3. IDENTIDAD Y DISEÑO VISUAL

Nombre: FuegoClaro.

Concepto visual: plataforma profesional de inteligencia geoespacial y monitoreo ambiental.

Diseña una interfaz moderna, tecnológica y elegante, inspirada en plataformas GIS y dashboards científicos.

Características visuales:

- Tema oscuro como apariencia principal.
- Fondo negro azulado o gris oscuro.
- Acentos naranja, rojo y amarillo para representar actividad de focos de calor.
- Tipografía moderna y legible.
- Tarjetas con información estadística.
- Gráficas interactivas.
- Mapas como elemento central.
- Microinteracciones y transiciones sutiles.
- Diseño responsive para escritorio y dispositivos móviles.

Evita:
- Apariencia de plantilla administrativa genérica.
- Exceso de tarjetas innecesarias.
- Gradientes exagerados.
- Animaciones que afecten el rendimiento.
- Información saturada.

La experiencia debe transmitir precisión científica y tecnología.

# 4. ARQUITECTURA TECNOLÓGICA

Utiliza inicialmente la siguiente arquitectura:

FRONTEND:
- React.
- Vite.
- TypeScript.
- Tailwind CSS.
- Leaflet para mapas.
- Recharts para gráficas.
- Lucide para iconografía.

BACKEND:
- Python.
- FastAPI.
- Pandas.
- NumPy cuando sea necesario.

DATOS:
- NASA FIRMS.
- Registros MODIS.
- Registros VIIRS.
- CSV y JSON para procesamiento y almacenamiento inicial.

ARQUITECTURA:
- Separar frontend y backend.
- Mantener componentes reutilizables.
- Utilizar servicios para las consultas HTTP.
- Separar la lógica científica de la presentación.
- Mantener las credenciales y claves API exclusivamente en el backend.
- Evitar dependencias innecesarias.

No incorporar bases de datos complejas salvo que exista una necesidad justificada.

# 5. FUNCIONALIDADES PRINCIPALES

## Módulo 1: Dashboard principal

Crear una pantalla inicial que muestre:

- Total de registros del periodo seleccionado.
- Cantidad de registros por sensor.
- Región analizada.
- Periodo de observación.
- Indicadores estadísticos.
- Evolución temporal.
- Resumen de hallazgos.

Todos los indicadores deben derivarse de los datos reales cargados.

## Módulo 2: Mapa interactivo

Implementar un mapa interactivo de Ecuador utilizando Leaflet.

Debe permitir:

- Visualizar registros georreferenciados.
- Diferenciar MODIS y VIIRS.
- Filtrar por sensor.
- Filtrar por fechas.
- Seleccionar regiones.
- Consultar información de cada registro.
- Utilizar agrupación de marcadores cuando existan muchos puntos.

Mostrar claramente qué representa cada elemento del mapa.

## Módulo 3: Calendario de focos de calor

Crear un calendario temporal que permita explorar la actividad detectada.

Características:

- Visualización mensual.
- Intensidad representada mediante una escala de colores.
- Selección de fechas.
- Consulta de registros diarios.
- Comparación entre diferentes periodos.
- Filtros por sensor.

No interpretar automáticamente la cantidad de detecciones como superficie quemada.

## Módulo 4: Comparador MODIS vs VIIRS

Este módulo es uno de los elementos más importantes del proyecto.

Debe mostrar:

- Cantidad de registros de cada sensor.
- Distribución geográfica.
- Evolución temporal.
- Diferencias de cobertura.
- Características y calidad de los registros.
- Comparaciones por periodos y regiones.

Explicar las limitaciones de comparabilidad y evitar presentar diferencias de conteo como diferencias directas de superficie afectada.

## Módulo 5: Radar de anomalías

Implementar un sistema estadístico que identifique periodos o regiones con actividad detectada inusual.

Debe:

- Calcular estadísticas sobre periodos comparables.
- Identificar desviaciones respecto a una referencia histórica.
- Mostrar qué datos justifican cada anomalía.
- Explicar el método utilizado.
- Indicar las limitaciones de la interpretación.

No inventar anomalías ni generar predicciones sin fundamento.

## Módulo 6: Centro de hallazgos

Crear una sección que traduzca los resultados estadísticos a explicaciones comprensibles.

Ejemplo:

"Durante el periodo seleccionado se observó un aumento de registros de focos de calor respecto al periodo de referencia. La diferencia se concentra principalmente en determinadas zonas geográficas."

Cada hallazgo debe incluir:

- Región.
- Periodo.
- Sensor.
- Indicador utilizado.
- Valor calculado.
- Método de comparación.

Se puede utilizar IA generativa para redactar explicaciones, pero nunca para inventar resultados o sustituir los cálculos estadísticos.

# 6. MANEJO Y VALIDACIÓN DE DATOS

Esta sección es obligatoria.

Los datos deben proceder de fuentes verificables de NASA.

Priorizar:
- NASA FIRMS.
- Servicios oficiales de descarga.
- Registros históricos disponibles.

Implementar un proceso de:

1. Obtención de datos.
2. Validación de campos.
3. Limpieza.
4. Normalización.
5. Identificación del sensor.
6. Tratamiento de valores ausentes.
7. Agregación temporal y espacial.
8. Visualización.

Conservar la procedencia de cada registro.

No modificar silenciosamente los valores originales.

Registrar:
- Fuente.
- Sensor.
- Fecha de adquisición.
- Coordenadas.
- Campos disponibles.
- Transformaciones realizadas.

Diferenciar siempre:

- Detección de foco de calor.
- Incendio confirmado.
- Superficie quemada.
- Intensidad radiativa.

Son conceptos diferentes y no deben utilizarse como sinónimos.

Si no existe conexión con NASA FIRMS, utilizar exclusivamente datos de prueba claramente identificados o muestras auténticas descargadas previamente. Nunca presentar datos sintéticos como observaciones reales.

# 7. EXPERIENCIA DE USUARIO

El recorrido principal debe ser:

1. El usuario ingresa al dashboard.
2. Selecciona una región de Ecuador.
3. Selecciona un periodo.
4. Explora el mapa.
5. Consulta el calendario.
6. Compara MODIS y VIIRS.
7. Revisa anomalías y hallazgos.
8. Comprende las conclusiones y sus limitaciones.

La navegación debe ser intuitiva y no requerir conocimientos especializados.

# 8. REQUISITOS DE CALIDAD

- Aplicación funcional.
- Código organizado.
- Componentes reutilizables.
- Manejo de errores.
- Estados de carga.
- Validación de entradas.
- Diseño responsive.
- Datos trazables.
- Resultados reproducibles.
- Documentación técnica.
- Instrucciones de ejecución.

Evitar botones decorativos que no realicen ninguna acción.

No mostrar estadísticas inventadas.

No ocultar errores de conexión.

# 9. PRIORIDADES DE DESARROLLO

Organizar las funcionalidades en tres niveles:

PRIORIDAD 1 — MVP OBLIGATORIO:
- Dashboard.
- Integración de datos MODIS y VIIRS.
- Mapa interactivo.
- Filtros.
- Calendario.
- Comparación básica de sensores.

PRIORIDAD 2 — DIFERENCIACIÓN:
- Radar de anomalías.
- Análisis estadístico.
- Centro de hallazgos.
- Comparación temporal avanzada.

PRIORIDAD 3 — EXTRAS:
- Exportación PDF.
- Mejoras visuales.
- Animaciones.
- Funcionalidades adicionales asistidas por IA.

Nunca sacrificar una funcionalidad prioritaria por desarrollar una funcionalidad extra.

# 10. METODOLOGÍA DE TRABAJO CON LA IA

Debes trabajar como un colaborador técnico del equipo.

Reglas:

1. No desarrollar funcionalidades innecesarias.
2. No modificar arbitrariamente la arquitectura.
3. Antes de crear archivos, explicar brevemente su responsabilidad.
4. Mantener consistencia entre frontend y backend.
5. No duplicar componentes.
6. Evitar instalar dependencias sin justificación.
7. Entregar código funcional, no pseudocódigo cuando se solicite implementación.
8. Comprobar que las rutas y los endpoints coincidan.
9. Explicar errores y proponer soluciones concretas.
10. Priorizar siempre una demo funcional.

Cuando se modifique un archivo existente, conservar las funcionalidades que ya funcionan.

Antes de realizar cambios grandes, identificar qué componentes pueden verse afectados.

# 11. EVALUACIÓN DEL PROYECTO

El resultado debe estar preparado para demostrar:

- Impacto: utilidad para comprender patrones territoriales.
- Creatividad: combinación de exploración geográfica y análisis temporal.
- Validez: datos NASA, método reproducible y limitaciones explícitas.
- Relevancia: cumplimiento directo del reto MODIS/VIIRS.
- Presentación: experiencia visual y demostración clara.

# 12. PRIMERA INSTRUCCIÓN

Antes de comenzar a programar:

1. Analiza los requisitos.
2. Propón la estructura completa del repositorio.
3. Define los modelos de datos.
4. Define los contratos de API.
5. Identifica las fuentes de datos.
6. Establece un plan de implementación priorizado.
7. Identifica los riesgos técnicos y científicos.
8. Propón una distribución de tareas para seis integrantes.

No generes todo el código de una sola vez.

Trabaja por módulos, validando cada integración antes de continuar.

**IMPORTANTE:** Estamos preparando la base conceptual antes del inicio del periodo competitivo. Por ahora, céntrate en planificación, especificaciones y decisiones técnicas generales. Durante el hackathon, cuando comience oficialmente el desarrollo, ejecutaremos la implementación y adaptaremos el alcance al tiempo disponible.

Nuestro objetivo es entregar un producto funcional, original, científicamente defendible y con una presentación sobresaliente.

Comienza presentando la arquitectura propuesta, la estructura del repositorio y el plan de trabajo.