---
title: Planteamiento del proyecto
subtitle: Estimación de cambios de emisión de NOₓ en la Zona Metropolitana del Valle de México con redes neuronales informadas por la física y datos satelitales (TEMPO)
---

# 1. Datos generales del proyecto

Este documento es el entregable de la semana 1 del Proyecto Integrador. Fija el planteamiento del proyecto del equipo 39, el plan de entregables comprometido para las semanas 1 a 11 y la ubicación del repositorio. La propuesta completa, con su marco metodológico CRISP-ML(Q), se desarrolla en el Avance 0.

## 1.1 Equipo y título del proyecto

Equipo 39: Isabella Arango Restrepo (A01796305), Manuel Alejandro Vázquez Meza (A01796404) e Isaí Ambrocio (A01625101).

El título del proyecto es: **Estimación de cambios de emisión de NOₓ en la Zona Metropolitana del Valle de México con redes neuronales informadas por la física y datos satelitales (TEMPO)**. El título nombra el contaminante (NOₓ), el lugar (ZMVM), la técnica (redes neuronales informadas por la física) y la fuente de datos que lo distingue (el satélite TEMPO de la NASA).

La pregunta de fondo es cuánto cambia la emisión de NOₓ de cada zona de la ciudad entre tipos de día o bajo una restricción de tráfico, separando el efecto de la emisión del efecto del viento y de la altura de la capa de mezcla, que también modifican la concentración medida.

Tabla 1. Resumen de los datos generales del proyecto.

| Elemento | Dato |
|---|---|
| Equipo | 39 |
| Beneficiario | Hub de Ciencia de Datos, Tecnológico de Monterrey |
| Sector (SCIAN) | Sector 54, Servicios profesionales, científicos y técnicos; rama 5417, Servicios de investigación científica y desarrollo |
| Lugar de aplicación | Zona Metropolitana del Valle de México (Ciudad de México y municipios conurbados del Estado de México), México |
| Área que recibe la solución | Hub de Ciencia de Datos, Campus Monterrey, Nuevo León |
| Patrocinador | Dr. Juan Arturo Nolazco Flores, Decano asociado de la Escuela de Ingeniería y Ciencias, Tecnológico de Monterrey, Campus Monterrey (jnolazco@tec.mx) |
| Dominio de IA | Optimización y apoyo a la toma de decisiones |
| Repositorio | <https://github.com/Mvzqz/nox_ml> |

## 1.2 Beneficiario

El beneficiario es el **Hub de Ciencia de Datos del Tecnológico de Monterrey**. Recibe un método reproducible, con código, datos versionados y documentación, para estimar cambios de emisión a partir de mediciones. El Hub puede reutilizarlo en otras ciudades: la fase de investigación ya probó el método en Los Ángeles (caso de control con satélite) y en Bogotá (caso sin satélite), y su integración al repositorio está planeada.

## 1.3 Sector y rama (SCIAN)

El proyecto se clasifica en el **Sector 54, Servicios profesionales, científicos y técnicos**, y dentro de él en la **rama 5417, Servicios de investigación científica y desarrollo** del Sistema de Clasificación Industrial de América del Norte (<https://www.inegi.org.mx/scian/>). La justificación es que el entregable es un servicio de investigación aplicada: desarrolla y valida un método científico (una inversión física con aprendizaje automático) y lo entrega a una unidad de ciencia de datos. No es un producto comercial ni un servicio de gestión ambiental operativa.

## 1.4 Lugar de aplicación y área que recibe la solución

El lugar de aplicación es la **Zona Metropolitana del Valle de México (ZMVM)**: la Ciudad de México y los municipios conurbados del Estado de México, en México. La prueba de concepto usa un dominio de 3,260 km² (19.25–19.77 °N, 99.35–98.81 °O) y cubre la Ciudad de México y los municipios conurbados del Estado de México.

El área que recibe la solución es el **Hub de Ciencia de Datos**, en el Campus Monterrey (Nuevo León). La ZMVM es el caso de estudio y la fuente de datos; el Hub es la unidad que adopta y mantiene la herramienta.

## 1.5 Patrocinador

El patrocinador es el **Dr. Juan Arturo Nolazco Flores**, Decano asociado de la Escuela de Ingeniería y Ciencias del Tecnológico de Monterrey, Campus Monterrey (correo: jnolazco@tec.mx). Su perfil institucional está en <https://research.tec.mx/vivo-tec/display/PID_532>. Además de patrocinar el proyecto, es uno de los profesores del curso.

## 1.6 Dominio de inteligencia artificial

El dominio es **Optimización y apoyo a la toma de decisiones**. El producto estima cuánto cambia la emisión de NOₓ por zona y por tipo de día con la meteorología descontada. Con ello apoya la evaluación de políticas ambientales, como las restricciones vehiculares de las contingencias ambientales y el programa Hoy No Circula. Hoy esas medidas se evalúan con concentraciones, que mezclan emisión y estancamiento del aire, y por eso no permiten decidir si conviene mantenerlas, endurecerlas o cambiarlas. El modelo no controla un sistema: entrega una estimación con su incertidumbre para que una autoridad decida.

## 1.7 Repositorio

El código, los datos versionados y los documentos están en <https://github.com/Mvzqz/nox_ml>. El repositorio no contiene credenciales: el acceso a los datos se configura de forma local con las variables de DVC (`--local`) y un token personal de DagsHub, que nunca se sube a git. Su estructura se describe en la sección 3.

# 2. Plan de entregables

La tabla siguiente lista, semana por semana, el entregable del curso y el entregable que el equipo se compromete a presentar. En todas las semanas el compromiso es igual a la referencia del curso.

Tabla 2. Plan de entregables, semanas 1 a 11.

| Semana | Entregable del curso | Entregable comprometido | Contenido previsto |
|---|---|---|---|
| 1 | Planteamiento | Planteamiento del proyecto (este documento) | Datos generales, plan de entregables y repositorio |
| 2 | Avance 0 | Propuesta de proyecto (CRISP-ML(Q)) | Antecedentes, entendimiento del negocio y de los datos, bibliografía |
| 3 | Avance 1: EDA | Análisis exploratorio de datos (cuaderno `Avance1.39`) | Calidad y cobertura de estaciones, viento, capa límite y TEMPO |
| 4 | Avance 2: Ingeniería de características | Ingeniería de características (cuaderno `Avance2.39`) | Construcción de las entradas del modelo: ventilación, calendario, zonas |
| 5 | Avance 3: Baseline | Baseline (cuaderno `Avance3.39`) | Inversión bayesiana lineal con pluma estacionaria y su desempeño |
| 6 | Avance 4: Modelos alternativos | Modelos alternativos (cuaderno `Avance4.39`) | Al menos seis modelos con algoritmos distintos, tabla comparativa y ajuste de los dos mejores |
| 7 | Avance 5: Modelo final | Modelo final y evaluación en el periodo de prueba | Ensambles, evaluación en datos no vistos (feb–may 2024) y gráficos del modelo final |
| 8 | Avance 6: Producto de difusión | Producto de difusión | Interfaz de resultados (Streamlit) que lee los resultados exportados |
| 9 | Avance 7: Resumen ejecutivo | Resumen ejecutivo | Hallazgos, límites y recomendaciones para quien decide |
| 10 | Presentación final | Presentación final | Presentación del proyecto completo |
| 11 | Presentación final | Presentación final | Presentación del proyecto completo |

Los cuadernos de las semanas 3 a 6 viven en la carpeta `deliverables/` del repositorio y solo llaman funciones del paquete `nox_ml`, de modo que cada resultado puede reproducirse. Las exportaciones en HTML, ya ejecutadas, van en `docs/entregables/html/`.

# 3. Repositorio

El repositorio público <https://github.com/Mvzqz/nox_ml> está conectado a DagsHub, donde se guardan los datos. Contiene el README con la descripción, el objetivo, los integrantes y la estructura, y cumple los elementos que pide el curso: datos, cuadernos y documentación.

Tabla 3. Estructura del repositorio.

| Elemento | Contenido |
|---|---|
| `README.md` | Descripción, objetivo, integrantes del equipo, requisitos del curso y estructura |
| `data/` | Datos versionados con DVC en un remoto de DagsHub (privado), nunca con git. Catálogo en `data/README.md`: origen, periodo, formato, licencia y acceso de cada fuente |
| `deliverables/` | Cuadernos de los avances (`Avance1.39` a `Avance4.39`), sin salidas |
| `docs/` | Instalación, uso, pruebas y contratos de los modelos; los entregables del curso están en `docs/entregables/` (Markdown, PDF y exportaciones HTML) |
| `ml/` | Paquete `nox_ml`: datos, física, inversión, modelos, validación y la línea de comandos `nox-ml` |
| `app/` | Paquete `nox_app`: interfaz de usuario (Streamlit) que lee solo resultados exportados |
| `configs/` | Configuración por ciudad y por experimento |
| `tests/` | Pruebas de extremo a extremo (modelo, resultados exportados y aplicación) |
| `context/` | Conocimiento técnico, decisiones de diseño (ADR) y gestión del proyecto |
| `bin/` | Scripts `uptodate`, `check`, `export-notebooks` y de los procesos de datos |

Reglas del repositorio. El código, los comentarios y la documentación del código están en inglés; los cuadernos y los reportes, en español. Los datos se obtienen con `dvc pull` tras configurar las credenciales de DagsHub en el entorno local, y las fuentes originales pueden descargarse de sus URL, que se listan en el catálogo. Una máquina nueva queda lista con `bin/uptodate`, y `bin/check` ejecuta las mismas verificaciones rápidas que la integración continua.
