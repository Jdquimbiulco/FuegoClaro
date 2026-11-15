# Checklist personalizado de evaluación — FuegoClaro

**NASA Space Apps Challenge — Sangolquí 2026**  
Proyecto: armonización y exploración de detecciones de focos de calor MODIS y VIIRS de NASA FIRMS en Ecuador.

Este checklist adapta los requisitos administrativos y la rúbrica descritos en `LINEAMIENTOS_CONCURSO.md` al alcance y la arquitectura documentados de FuegoClaro. Sirve para preparar la ficha de la plataforma, el repositorio, la demostración y las respuestas al jurado. Las marcas indican el estado documental conocido: **[x]** ya está descrito o implementado según la documentación del proyecto; **[ ]** requiere preparar evidencia, completar una entrega externa o verificarlo antes del concurso. Una marca [x] no sustituye una comprobación final de funcionamiento.

## 1. Auditoría administrativa antes del cierre

Cada incumplimiento indicado puede descontarse directamente de la nota base, según los lineamientos. Verificar las condiciones y la redacción exacta de la plataforma oficial antes de enviar.

| Listo | Verificación para FuegoClaro | Evidencia que debe quedar a mano | Deducción indicada |
|---|---|---|---:|
| [x] | Identificar como fuente principal **NASA FIRMS**, con detecciones de MODIS y VIIRS; la aplicación y la ficha deben enlazar a la fuente y nombrar los productos usados. | Vista de Metodología/Procedencia, manifiesto de datos y enlace oficial en la ficha. | −2 |
| [ ] | Publicar el repositorio en modo público y añadir un archivo `LICENSE` válido en su raíz. La documentación revisada no confirma visibilidad pública ni licencia. | URL abierta en ventana privada y archivo de licencia visible en la raíz. | −2 |
| [ ] | Probar en ventana privada todos los enlaces entregados: demo, repositorio, video, diapositivas y documentación; que abran sin inicio de sesión ni permisos privados. | Lista final de URLs probadas y capturas o registro de la prueba. | −1 |
| [ ] | Subir un PDF de pitch con **máximo 7 diapositivas contando la portada**, o un video demo de **máximo 35 segundos**. | PDF contabilizado o duración comprobada del video. | −1 |
| [ ] | Completar la declaración de uso de IA en la plataforma; declarar herramientas usadas para código o recursos visuales. Añadir las marcas de agua requeridas a multimedia generado con IA. Usar correctamente los logos NASA, sin alterar ni sugerir aval institucional. | Texto de declaración, recursos revisados y atribuciones/marcas de agua aplicables. | −1 |
| [ ] | Cargar la ficha del proyecto y entregables descriptivos en **español e inglés**; tener también README en ambos idiomas. El README actual está en español. | Ficha bilingüe y README/documentación bilingües publicados. | −1 |

**Puntaje protegido:** 8 puntos de penalización administrativa en total si se incumplen todos los seis controles (según la tabla de lineamientos). Revisar la plataforma por separado, porque algunas condiciones se aplican a campos o entregas específicos.

## 2. Repositorio, reproducibilidad y preparación técnica

### Repositorio y documentación

- [ ] El repositorio público abre sin autenticación y su URL coincide en la plataforma, README y diapositivas.
- [ ] Existe `LICENSE` en la raíz del repositorio y el texto corresponde a la licencia declarada.
- [x] El repositorio contiene frontend, backend, scripts, documentación, configuración de contenedores y pruebas según `Hackaton/README.md`.
- [x] El README describe arquitectura, dependencias, configuración y ejecución; antes de publicar, adaptar sus comandos de `.venv/bin/...` al entorno Windows/equipo o documentar Docker como ruta reproducible.
- [ ] Se añade una sección en inglés al README y a la ficha pública.
- [x] La clave FIRMS se mantiene en el backend y se excluye del frontend y de los archivos versionados según la documentación. Confirmar que no se publique ningún secreto antes de liberar el repositorio.
- [x] Docker Compose está documentado como forma reproducible de levantar backend y frontend.
- [ ] Preparar un entorno alternativo sin internet o un plan de contingencia por si falla la red durante el pitch.

### Datos NASA y cadena de procesamiento

- [x] La fuente de los focos de calor se identifica como NASA FIRMS; los productos documentados son `MODIS_SP`, `MODIS_NRT`, `VIIRS_NOAA20_SP` y `VIIRS_NOAA20_NRT`.
- [x] La procedencia del dataset se conserva en CSV/manifiesto con hashes, cobertura, transformaciones y limitaciones, según la guía del proyecto.
- [x] El pipeline documentado cubre ingesta, normalización, validación, deduplicación, recorte a provincias y agregaciones.
- [ ] Preparar una lámina o recorrido de 30–45 segundos que muestre **dataset NASA → transformación → API → mapa/gráfico/resultado**; explicar qué se conserva y qué se filtra.
- [ ] Tener a mano la cobertura y fecha de actualización que efectivamente aparecen en el manifiesto el día de la evaluación; no copiar cifras antiguas de la guía.
- [ ] Mostrar un ejemplo de trazabilidad de un dato hasta su producto/fuente original y explicar la limitación de cobertura cuando corresponda.
- [x] Se conserva la confianza original (`confidence_raw`/`confidence_level`) y se evita inventar una puntuación numérica para la confianza VIIRS.
- [x] La atribución también identifica Natural Earth para límites provinciales y CARTO/OpenStreetMap para el mapa base; citar todas las librerías, fuentes secundarias y literatura pertinente en la ficha y/o sección de créditos.
- [ ] Revisar si se utilizaron modelos preentrenados u otras herramientas de IA: declararlos y atribuirlos; si no se usaron, decirlo con claridad.

### Ciencia, interpretación responsable y metodología

- [x] La documentación aclara que una detección térmica no confirma un incendio ni mide directamente superficie quemada.
- [x] Advierte que no detectar un foco no demuestra ausencia de fuego.
- [x] Advierte que los conteos MODIS y VIIRS no son intercambiables ni comparables directamente como área o gravedad; explica diferencias de resolución, sensibilidad, algoritmo y horario.
- [x] El análisis de anomalías se describe con z-score, p-valor bilateral y control FDR Benjamini–Hochberg, línea base histórica y mínimos de observaciones.
- [x] Los hallazgos se documentan como deterministas, con evidencia, método y límite interpretativo.
- [ ] Poder explicar con un ejemplo sencillo cómo se construye una anomalía, qué referencia usa y qué significan el z-score, el p-valor y el ajuste FDR sin presentarla como causa de un incendio.
- [ ] Explicar las limitaciones por nubosidad, humo, geometría de observación, productos SP/NRT y longitud de la línea base.
- [ ] Si se presenta el módulo de riesgo ML, distinguirlo de la observación FIRMS: aclarar etiqueta, horizonte, variables, evaluación/calibración, umbrales percentiles y límites; no llamarlo alerta operacional ni predicción confirmada.
- [ ] Tener listas las respuestas sobre validez científica, sesgos, datos ausentes, reproducibilidad y mejoras futuras.

### Demostración del producto y estabilidad

- [x] La aplicación documentada incluye dashboard, mapa, calendario, comparador, anomalías, hallazgos, metodología y exportación CSV.
- [x] Existe una muestra auténtica para operar en modo offline si no está disponible el dataset completo.
- [ ] Elegir previamente modo de demostración (**real**, **muestra** o **vacío**) y decirlo al público; no presentar la muestra como cobertura completa.
- [ ] Confirmar antes del pitch el estado de la API (`/api/v1/health`), la carga de la web y las rutas críticas; comprobar que las cifras que se narrarán coinciden con el modo y filtro seleccionados.
- [ ] Ensayar el recorrido interactivo: filtrar periodo/región/sensor, abrir una detección en el mapa, comparar sensores, explorar una anomalía con evidencia y cerrar en metodología/procedencia.
- [ ] Verificar conexión API, exportación CSV, carga de geometrías, mapa, gráficos y cambio de filtros. Llevar capturas o video corto de respaldo.
- [ ] Preparar reinicio rápido y datos locales listos. Evitar ejecutar una nueva ingesta durante la preparación de la presentación.
- [ ] Mostrar la app en móvil o explicar su comportamiento responsive si forma parte del argumento de accesibilidad.

## 3. Rúbrica del pitch y preguntas — 20 criterios

Calificar cada criterio de **1 a 5**: 1 = pobre/insuficiente; 5 = excepcional. Reservar 5 para evidencia sobresaliente y demostrable. Registrar nota y evidencia concreta para cada punto.

### Área 1 — Rigor científico y datos (RCD)

| Listo | Criterio (1–5) | Evidencia que debería mostrar FuegoClaro | Nota |
|---|---|---|---:|
| [ ] | Uso evidente de datos oficiales | Identificar NASA FIRMS, productos MODIS/VIIRS y su uso funcional en módulos reales; señalar procedencia en pantalla. | __/5 |
| [ ] | Solidez del sustento científico | Justificar normalización, comparación, confianza y detección estadística de anomalías; reconocer qué no permiten concluir los datos. | __/5 |
| [ ] | Explicación del procesamiento de datos | Narrar ingesta → validación/normalización → recorte/atribución territorial → almacenamiento/manifiesto → API → visualización. | __/5 |
| [ ] | Dominio científico en Q&A | Responder sobre sensores, cobertura, confianza, detecciones, anomalías y limitaciones sin sobreafirmar. | __/5 |
| [ ] | Transparencia y atribución | Citar FIRMS, límites geográficos, mapa base, librerías, fuentes secundarias, bibliografía y modelos/herramientas aplicables. | __/5 |

### Área 2 — Innovación y ejecución técnica (IET)

| Listo | Criterio (1–5) | Evidencia que debería mostrar FuegoClaro | Nota |
|---|---|---|---:|
| [ ] | Demostración del prototipo funcional (MVP) | Interactuar con la app ejecutándose; resolver una tarea del usuario con filtros y datos, no solo mostrar capturas/maquetas. | __/5 |
| [ ] | Arquitectura y complejidad técnica | Explicar React/Vite/TypeScript, FastAPI, dominio separado, API, datos y Docker; mostrar por qué esa estructura sirve al caso. | __/5 |
| [ ] | Creatividad e ingenio tecnológico | Mostrar cómo FuegoClaro armoniza y contextualiza dos sensores, conecta evidencia espacial/temporal y hace comprensibles sus diferencias. | __/5 |
| [ ] | Defensa técnica en Q&A | Responder por decisiones de esquema, filtros, métodos, errores, API, almacenamiento, seguridad de credenciales y compromisos. | __/5 |
| [ ] | Factibilidad técnica y reproducibilidad | Levantar con Docker o pasos documentados, usar dataset/manifiesto verificables y explicar modos real/muestra y dependencias externas. | __/5 |

### Área 3 — Impacto y relevancia (IR)

| Listo | Criterio (1–5) | Evidencia que debería mostrar FuegoClaro | Nota |
|---|---|---|---:|
| [ ] | Alineación con el reto oficial | Explicar explícitamente cómo armoniza MODIS y VIIRS y ayuda a explorar detecciones, patrones y diferencias de sensores. | __/5 |
| [ ] | Magnitud de impacto | Definir usuarios/decisiones que podría apoyar y cómo medir utilidad; presentar resultados o métricas reales, no impacto hipotético como hecho. | __/5 |
| [ ] | Viabilidad de adopción y escalabilidad | Ruta realista: mantener fuentes/dataset, despliegue, accesibilidad, responsables, costos/riesgos y pasos posteriores al hackathon. | __/5 |
| [ ] | Pertinencia territorial o de misión | Conectar el análisis con Ecuador, sus 24 provincias y regiones naturales; explicar cuándo se requiere más contexto local. | __/5 |
| [ ] | Accesibilidad y UX centrada en el usuario | Mostrar interfaz entendible, filtros compartibles, leyendas, definiciones y advertencias que ayudan a interpretar los datos. | __/5 |

### Área 4 — Storytelling y presentación (STP)

| Listo | Criterio (1–5) | Evidencia que debería mostrar el equipo | Nota |
|---|---|---|---:|
| [ ] | Estructura narrativa del pitch | Problema → datos y solución demostrada → impacto; mantener una idea central y un caso de uso concreto. | __/5 |
| [ ] | Calidad visual y material de apoyo | Láminas legibles, consistentes y limpias; mapas/gráficos con etiquetas, fuentes, unidades y límites claros. | __/5 |
| [ ] | Gestión del tiempo | Ensayo cronometrado; cubrir problema, demo, datos, impacto y cierre sin sacrificar el recorrido técnico ni acelerar al final. | __/5 |
| [ ] | Expresión oral y seguridad | Explicar con claridad, ritmo, lenguaje accesible y dominio de cifras, métodos y limitaciones. | __/5 |
| [ ] | Cohesión de equipo en Q&A | Asignar quién responde datos/ciencia, arquitectura, UX/impacto y operación; complementar respuestas sin contradecirse. | __/5 |

**Promedio de área** = suma de sus cinco notas ÷ 5.  
**Nota ponderada de categoría** = RCD × peso RCD + IET × peso IET + IR × peso IR + STP × peso STP. Usar pesos como decimales (50 % = 0,50). Aplicar los bonos de nominación y deducciones según el procedimiento oficial.

## 4. Enfoque según nominación

| Categoría | RCD | IET | IR | STP | Qué debe enfatizar FuegoClaro |
|---|---:|---:|---:|---:|---|
| Best Use of Data | 50 % | 20 % | 15 % | 15 % | Trazabilidad NASA FIRMS, productos, transformaciones, calidad y uso sustancial en la app. |
| Best Use of Science | 50 % | 20 % | 20 % | 10 % | Rigor de la armonización, estadística, interpretación y límites científicos. |
| Best Use of Technology | 20 % | 50 % | 15 % | 15 % | MVP operativo, arquitectura, ingeniería, reproducibilidad e innovación. |
| Best Mission Concept | 25 % | 35 % | 25 % | 15 % | Plausibilidad del sistema, arquitectura coherente, utilidad y despliegue posible. |
| Galactic Impact | 15 % | 15 % | 50 % | 20 % | Escala y valor potencial para usuarios; respaldar el impacto con medidas verificables. |
| Best Storytelling | 15 % | 15 % | 20 % | 50 % | Narrativa clara que conecte datos satelitales, caso local y aprendizaje. |
| Art & Technology | 15 % | 40 % | 15 % | 30 % | Diseño visual e interacción integrados con la ingeniería y los datos. |
| Global Connection | 15 % | 15 % | 45 % | 25 % | Relevancia transferible, acceso, colaboración y alcance de la solución. |
| Local Impact | 15 % | 15 % | 50 % | 20 % | Uso territorial para Ecuador y pertinencia para quienes toman decisiones/locales. |
| Most Inspirational | 10 % | 15 % | 25 % | 50 % | Historia humana, propósito, claridad y capacidad de inspirar con honestidad. |

Los lineamientos indican un bono de **+3 puntos por voto de nominación directa**, hasta **+12 por categoría**, aplicado sobre la nota ponderada base y sujeto a deducciones de auditoría. Confirmar el cálculo exacto con la guía y el formulario oficial del evento.

## 5. Materiales finales para dejar preparados

- [ ] Ficha oficial completa en español e inglés, con descripción, reto, solución, impacto, tecnologías y fuentes.
- [ ] URL pública del repositorio con `LICENSE` y README bilingüe.
- [ ] Demo pública y enlaces a documentación probados en ventana privada.
- [ ] Declaración de IA y créditos completos; revisar marcas de agua y uso de logos.
- [ ] PDF del pitch (hasta 7 diapositivas) y/o video demo (hasta 35 s).
- [ ] Guion cronometrado y demo en vivo ensayada por todo el equipo.
- [ ] Plan de respaldo offline, capturas/video de respaldo y modo de datos claramente identificado.
- [ ] Respuestas preparadas para los 20 criterios, incluyendo limitaciones y evidencia asociada.
- [ ] Selección de las categorías de nominación que mejor correspondan a la evidencia real del proyecto.
- [ ] Validación final por una persona que no desarrolló la aplicación: que pueda entender fuentes, filtros, comparaciones y límites sin explicación adicional.

## 6. Guion mínimo recomendado para la demostración

1. **Problema:** MODIS y VIIRS observan focos térmicos con características distintas; sus conteos requieren contexto para interpretarse.
2. **Fuente y método:** mostrar NASA FIRMS y la procedencia; resumir normalización, cobertura, geografía y limitaciones.
3. **Uso:** filtrar un periodo/región, explorar el mapa y calendario, y abrir una comparación MODIS/VIIRS.
4. **Hallazgo:** mostrar una anomalía o resultado con su evidencia y explicar lo que sí y lo que no concluye.
5. **Impacto y siguiente paso:** indicar usuarios, utilidad medible y ruta de continuidad.

