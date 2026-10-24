# Solicitudes de datos

Fecha: 2026-10-20. Cartas listas para copiar. Antes de enviar, completa los campos entre corchetes y verifica los contactos marcados ⚠️.

## Por qué estas solicitudes

> **Actualización (2026-10-22): cambió el orden de prioridades.** La prueba de Los Ángeles con datos reales (`otras_ciudades.md`) mostró que un viento mucho mejor (HRRR, 16° de error frente a 30°) **no mejoró** la inversión por sí solo. Además, el sesgo de los domingos se explicó sin viento: lo fijaba el a priori, y el cociente de tráfico de Infovial lo corrige (`sesgo_domingos.md`). Por eso ahora la prioridad son los **datos de tráfico y los perfiles de emisión**, y el campo de viento pasa a segundo lugar: sirve junto con transporte dependiente del tiempo y emisión basada en tráfico, no solo.

**Primera necesidad: tráfico y perfiles de emisión.** Conteos vehiculares posteriores a 2019 (Infovial, SEMOVI, C5, Waze) y los perfiles temporales e inventario por municipio de SEDEMA. Son la referencia que hoy valida los cambios relativos, el producto que ya funciona (`caso_de_uso.md`, `mejoras.md`).

**Segunda necesidad: campo de viento de ~1 km.** El error real de dirección al interpolar estaciones tiene una mediana de 28–32°; ERA5 llega a 55° (`viento.md`). En los gemelos, un viento mejor ayudaba mucho, pero con datos reales en LA no bastó. El campo existe en el pronóstico de SEDEMA y en el grupo UNAM–LSCE; pedirlo sigue siendo mucho más barato que correr WRF nosotros, pero no conviene correr WRF propio: en LA, con transporte dependiente del tiempo (puffs), el viento HRRR a 10 m tampoco mejoró frente al viento promedio (`otras_ciudades.md`, «Puffs + HRRR»). Si se pide el campo, lo valioso es la **capa límite, el viento en altura y la recirculación**, no el viento de superficie.

## Destinatarios

| # | Institución | Contacto | Canal | Fuente |
|---|---|---|---|---|
| 1 | SEDEMA, Dirección General de Calidad del Aire | Gabriel Pérez Zaguilan, titular; gperez@sedema.cdmx.gob.mx; 55 5278 9931 ext. 6110 | Correo de colaboración | [Directorio SEDEMA](https://www.sedema.cdmx.gob.mx/secretaria/directorio) |
| 1b | SEDEMA, atención ciudadana (copia) | atencionciudadana@sedema.cdmx.gob.mx; 55 5345 8187 | Correo | [Estructura SEDEMA](https://www.sedema.cdmx.gob.mx/secretaria/estructura) |
| 2 | SEDEMA, por transparencia | Sujeto obligado: Secretaría del Medio Ambiente (Ciudad de México) | Plataforma Nacional de Transparencia | [PNT](https://www.plataformadetransparencia.org.mx/); el canal de solicitudes a SEDEMA aparece en resoluciones del [INFOCDMX](https://documentosobligaciones.infocdmx.org.mx/ST/LTAIPRC-2016-OT/Art133/Fr01/2025/T01/INFOCDMX.RR.IP.0551.2025.pdf) |
| 3 | UNAM, Instituto de Ciencias de la Atmósfera y Cambio Climático (ICAyCC), Grupo de Espectroscopía y Percepción Remota | Dr. Michel Grutter de la Mora. ⚠️ El correo grutter@unam.mx viene de un CV de 2021 que no pude abrir (lo muestra un buscador); verifícalo. Sitio: http://www.atmosfera.unam.mx/espectroscopia | Correo | [Perfil Humboldt](https://www.humboldt-foundation.de/en/connect/explore-the-humboldt-network/singleview/1129025/prof-dr-michel-grutter-de-la-mora); [EGU23-16636](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html) |
| 3b | UNAM-ICAyCC, modelación y pronóstico (WRF-Chem, inventario de emisiones) | Dr. Agustín García-Reynoso. ⚠️ No encontré correo público; búscalo en el directorio del ICAyCC o pídelo a Grutter | Correo, con copia a Grutter | [EGU21-15117](https://meetingorganizer.copernicus.org/EGU21/EGU21-15117.html?EGUSphere); [EGU23-16636](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html) |
| 3c | LSCE (Francia), coordinación de MERCI-CO₂ | Michel Ramonet (coordinador francés), Thomas Lauvaux (hoy Univ. de Reims, GSMA). ⚠️ Sin correo público verificado: contactarlos por medio de Grutter | Copia en el correo 3 | [ANR, proyecto MERCI-CO₂](https://anr.fr/Project-ANR-17-CE04-0013); [EGU23-16636](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html) |
| 4 | Agencia Digital de Innovación Pública (ADIP), Datos Abiertos CDMX | infoadip@cdmx.gob.mx; 55 3090 0500 | Correo | [Datos Abiertos CDMX](https://datos.cdmx.gob.mx/) |

Lo que sabemos del viento de cada grupo:
- **SEDEMA:** su sistema de pronóstico, desarrollado con el Barcelona Supercomputing Center, corre WRF anidado hasta 1 km de forma operativa desde 2017 (fuentes citadas en `viento.md`). No está confirmado que archive las salidas pasadas.
- **UNAM–LSCE (MERCI-CO₂):** proyecto franco-mexicano (LSCE, CCA-UNAM, ARIA Technologies y SEDEMA). Corrieron WRF-Chem a 1 km con modelo de dosel urbano, evaluado contra 26 estaciones de SEDEMA ([EGU21-15117](https://meetingorganizer.copernicus.org/EGU21/EGU21-15117.html?EGUSphere)), e inversiones bayesianas de CO₂ a 1 km y 1 h con X-STILT, FTIR y OCO-3 para oct 2020–may 2021 ([EGU23-16636](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html)). El grupo de pronóstico del ICAyCC además corre WRF-Chem a 3 km para el centro de México ([presentación IWAWFR 2021](https://congresos.cuaieed.unam.mx/event/5/contributions/16/attachments/6/94/IWAWFR_2021.pdf), según el buscador; no la abrí).

## Carta 1. SEDEMA: correo de colaboración académica

**Para:** gperez@sedema.cdmx.gob.mx
**CC:** atencionciudadana@sedema.cdmx.gob.mx
**Asunto:** Solicitud de colaboración: inventario, perfiles de emisión y campos de viento del pronóstico AQFS-Mex para estimar emisiones de NOₓ

> Mtro. Gabriel Pérez Zaguilan
> Director General de Calidad del Aire
> Secretaría del Medio Ambiente de la Ciudad de México
>
> Estimado Mtro. Pérez Zaguilan:
>
> Le escribo para solicitar la colaboración de la Dirección General de Calidad del Aire en un proyecto de investigación sin fines comerciales. El proyecto estima las emisiones de óxidos de nitrógeno (NOₓ) de la Zona Metropolitana del Valle de México a partir de mediciones: las estaciones de SIMAT, el satélite TEMPO de la NASA y un modelo físico de transporte. El objetivo es ofrecer una estimación independiente, por zona y por tipo de día, que complemente el inventario de emisiones y ayude a evaluar medidas como las restricciones vehiculares de las contingencias. Todos los resultados y métodos se compartirán con la Secretaría.
>
> Con datos públicos ya obtuvimos resultados útiles. Separando el efecto de la meteorología, el método estima que en domingo la emisión vial es 0.65 de la de un día hábil, en línea con los conteos vehiculares de Infovial, y que el confinamiento de 2020 redujo la emisión de NOₓ alrededor de 35 %. También evaluamos los días de contingencia de 2024. Para afinar y validar estos resultados nos serían muy útiles el inventario por municipio y los perfiles temporales de emisión que usa la Secretaría. Además, interpolar el viento de las estaciones deja un error de dirección de 28–32° (mediana); con un campo de ~1 km como el de su sistema de pronóstico esperamos mejorar la estimación por zona.
>
> Por ello, le solicitamos de la manera más atenta:
>
> 1. **El inventario de emisiones más reciente posterior a 2018** (2020 u otro) y sus **anexos con NOₓ por alcaldía y municipio**, así como la **distribución espacial en malla**, si está disponible.
> 2. **Los perfiles temporales** (horarios y semanales) que usa el inventario o el sistema de pronóstico para distribuir las emisiones vehiculares.
> 3. **Salidas archivadas del modelo meteorológico del sistema de pronóstico de calidad del aire (AQFS-Mex)**, dominio de ~1 km, con frecuencia horaria: viento a 10 m (u, v), viento en los primeros niveles del modelo y altura de la capa límite. Periodos: noviembre–diciembre de 2023 y febrero–mayo de 2024, y abril–mayo de 2020 si existen. Nos basta el dominio de la ZMVM y las horas de 12:00 a 18:00 (hora local), en NetCDF, GRIB o el formato en que se archiven.
>
> Usaremos la información solo para este proyecto, citaremos a la SEDEMA como fuente y no la redistribuiremos sin su autorización. Con gusto firmamos un convenio o carta de confidencialidad si lo requieren, y podemos presentar los resultados a su equipo.
>
> Quedo atento a sus comentarios.
>
> Atentamente,
> [Nombre]
> [Institución o afiliación]
> [Correo y teléfono]

## Carta 2. SEDEMA: solicitud por la Plataforma Nacional de Transparencia

**Dónde:** [Plataforma Nacional de Transparencia](https://www.plataformadetransparencia.org.mx/) → Solicitudes → Información pública → Ciudad de México → **Secretaría del Medio Ambiente**. ⚠️ Los nombres exactos de los menús pueden variar; elige el sujeto obligado de la Ciudad de México, no la SEMARNAT federal.

**Modalidad de entrega:** electrónica, a través del sistema de solicitudes de la PNT o por correo electrónico.
**Formato preferido:** archivos digitales en su formato original (NetCDF, GRIB, CSV o XLSX). Si un archivo excede el tamaño permitido, se pide un enlace de descarga.

**Texto para el formulario** (copiar tal cual):

> Solicito, en formato digital y en su formato original, la siguiente información en posesión de la Dirección General de Calidad del Aire:
>
> 1. El inventario de emisiones de la Zona Metropolitana del Valle de México más reciente posterior a 2018, incluidos sus anexos con las emisiones de óxidos de nitrógeno (NOx) por alcaldía y municipio, y la distribución espacial de las emisiones en malla (archivos de datos, no solo mapas).
> 2. Los perfiles temporales (horarios, por día de la semana y mensuales) utilizados para distribuir las emisiones de fuentes móviles en el inventario de emisiones o en el sistema de pronóstico de calidad del aire.
> 3. Las salidas archivadas del modelo meteorológico (WRF) del Sistema de Pronóstico de Calidad del Aire de la Ciudad de México (AQFS-Mex) en su dominio de mayor resolución (aproximadamente 1 km), con frecuencia horaria, de las variables: componentes del viento a 10 metros (u10, v10), componentes del viento en los primeros niveles verticales del modelo y altura de la capa límite planetaria. Periodos: del 1 de noviembre al 31 de diciembre de 2023 y del 15 de febrero al 31 de mayo de 2024; y, si existen, del 1 de abril al 31 de mayo de 2020. Basta con el área de la Zona Metropolitana del Valle de México. Si no se conservan salidas de esos periodos, solicito que se indique el periodo que sí se conserva y su formato.
>
> Solicito la entrega por medio electrónico. Si el volumen excede el límite de la plataforma, solicito un enlace de descarga.

**Plazo:** la ley de transparencia de la CDMX fija un plazo de respuesta en días hábiles, prorrogable. ⚠️ No verifiqué el número exacto de días; revísalo al registrar la solicitud, porque la plataforma lo muestra con la fecha límite.

## Carta 3. UNAM-ICAyCC y LSCE: propuesta de colaboración

**Para:** Dr. Michel Grutter de la Mora (⚠️ verificar correo)
**CC:** Dr. Agustín García-Reynoso (⚠️ correo por confirmar); pedir que se reenvíe a Michel Ramonet y Thomas Lauvaux (LSCE / Univ. de Reims)
**Asunto:** Propuesta de colaboración: viento de 1 km de MERCI-CO₂ para estimar emisiones de NOₓ con TEMPO en la ZMVM

> Estimado Dr. Grutter:
>
> Le escribo para proponerle una colaboración académica. Desarrollamos un método para estimar las emisiones de NOₓ de la ZMVM a partir de las estaciones de SIMAT y del NO₂ horario del satélite TEMPO, con un modelo de transporte y una inversión bayesiana. El trabajo no tiene fines comerciales y los resultados son abiertos.
>
> Conocemos el trabajo de su grupo y del LSCE en MERCI-CO₂: la simulación WRF-Chem a 1 km con dosel urbano (Xu et al., EGU 2021) y la inversión de CO₂ a 1 km y 1 h con FTIR y OCO-3 (Che et al., EGU 2023). Nuestras pruebas muestran que el viento es lo que limita nuestro método: interpolar las estaciones de REDMET da un error de dirección de 28–32° (mediana) y ERA5, de 55°. En experimentos sintéticos, bajar ese error a ±10° permite recuperar las fuentes grandes (Acolman, AICM, AIFA) dentro de 25 %, algo que hoy no logramos.
>
> **Lo que le pediríamos:**
> - Campos horarios de viento (10 m y niveles bajos) y altura de capa límite de su WRF de 1 km, para los periodos que tengan simulados. Nos interesan nov–dic 2023 y feb–may 2024, pero cualquier periodo con datos de TEMPO (desde agosto de 2023) nos sirve.
> - Si fuera posible, la configuración de WRF (namelists, esquema urbano, asimilación) para reproducir periodos nuevos.
>
> **Lo que ofrecemos:**
> - Nuestro pipeline abierto: descarga y control de calidad de TEMPO, SIMAT y REDMET (incluida la corrección de unidades del viento de REDMET 2024, reportado en mph como m/s), y la inversión lineal con validación cruzada.
> - Resultados de emisiones de NOₓ por zona y tipo de día. Pueden servir como restricción independiente de las emisiones de combustión en sus inversiones de CO₂, porque el cociente NO₂/CO₂ ayuda a separar tipos de fuente.
> - Coautoría en las publicaciones que resulten y uso compartido de todos los datos procesados.
>
> Con gusto le presento los resultados en una reunión breve. Agradecería también si nos puede poner en contacto con el Dr. Ramonet y el Dr. Lauvaux.
>
> Saludos cordiales,
> [Nombre]
> [Institución o afiliación]
> [Correo y teléfono]

## Carta 4. ADIP: datos de tráfico posteriores a 2019 (ahora prioritaria)

**Para:** infoadip@cdmx.gob.mx
**Asunto:** Consulta sobre datos abiertos de aforos y velocidades viales posteriores a 2019

> Estimado equipo de Datos Abiertos de la Ciudad de México:
>
> Usamos el conjunto Infovial (conteos vehiculares por clase y velocidades en vialidades primarias), disponible en el portal para 2016–2019, en un proyecto de investigación sin fines comerciales que estima las emisiones de NOₓ de la ciudad a partir de mediciones. Los conteos nos sirven para fijar el perfil horario y semanal del tráfico y para validar nuestros resultados.
>
> Quisiéramos saber:
> 1. Si existen datos de Infovial o de aforos equivalentes (SEMOVI, C5) posteriores a 2019, y cómo obtenerlos.
> 2. Si los datos del convenio de la Ciudad con Waze (2019), u otros datos de velocidades por tramo, pueden compartirse con fines de investigación.
> 3. A qué área debemos dirigirnos si la información no está en el portal.
>
> Citaremos la fuente y compartiremos los resultados.
>
> Atentamente,
> [Nombre, afiliación, correo]

## Calendario sugerido

| Cuándo | Acción |
|---|---|
| Día 1 | Enviar la carta 1 (correo a SEDEMA), registrar la carta 2 en la PNT y enviar la carta 4 a la ADIP, todo el mismo día. Los datos de tráfico ahora son la primera prioridad. |
| Día 1–2 | Enviar la carta 3 a Grutter y García-Reynoso, después de verificar sus correos. |
| Semana 2 | Seguimiento por correo a SEDEMA y a UNAM si no hubo respuesta; ofrecer una llamada de 20 minutos. |
| Al vencer el plazo de la PNT | Revisar la respuesta. Si declaran inexistencia o reservan la información, se puede interponer un recurso de revisión ante el INFOCDMX. |
| Semana 4 | No correr WRF propio: la prueba de puffs + HRRR en LA no mostró mejora por el viento de superficie. Si SEDEMA o UNAM comparten su campo, usarlo por la capa límite y el viento en altura. |
| Al recibir datos | Validar el viento con `scripts/wind_loo.py` (meta: mediana ≤ 20–25°) y repetir los gemelos con el error medido. |

## Fuentes (páginas abiertas)

- [SEDEMA, directorio](https://www.sedema.cdmx.gob.mx/secretaria/directorio)
- [SEDEMA, estructura y atención ciudadana](https://www.sedema.cdmx.gob.mx/secretaria/estructura)
- [Datos Abiertos CDMX (ADIP)](https://datos.cdmx.gob.mx/)
- [ANR, proyecto MERCI-CO₂ (ANR-17-CE04-0013)](https://anr.fr/Project-ANR-17-CE04-0013)
- [Xu et al., EGU21-15117: WRF-Chem a 1 km en la CDMX](https://meetingorganizer.copernicus.org/EGU21/EGU21-15117.html?EGUSphere)
- [Che et al., EGU23-16636: inversión de CO₂ a 1 km con FTIR y OCO-3](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html)
- [Perfil de Michel Grutter, Fundación Humboldt](https://www.humboldt-foundation.de/en/connect/explore-the-humboldt-network/singleview/1129025/prof-dr-michel-grutter-de-la-mora)
- [Plataforma Nacional de Transparencia](https://www.plataformadetransparencia.org.mx/) (la portada no mostró los pasos; se describen de forma general)

Vistas solo en resultados de búsqueda, sin abrir: la [resolución INFOCDMX RR.IP.0551/2025](https://documentosobligaciones.infocdmx.org.mx/ST/LTAIPRC-2016-OT/Art133/Fr01/2025/T01/INFOCDMX.RR.IP.0551.2025.pdf) (ejemplo de solicitud a SEDEMA por la PNT), la [presentación IWAWFR 2021 del ICAyCC](https://congresos.cuaieed.unam.mx/event/5/contributions/16/attachments/6/94/IWAWFR_2021.pdf) y el CV de Grutter de 2021 (origen del correo por verificar).
