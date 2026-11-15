---
title: Interfaz y flujos de uso del sistema de emisión de NOₓ
subtitle: Cómo imaginamos la interfaz y cómo realizarían sus tareas los usuarios. Proyecto Integrador, equipo 39
author: Isabella Arango Restrepo (A01796305), Isaí Ambrocio (A01625101) y Manuel Alejandro Vázquez Meza (A01796404)
---

<!--
Fecha: 15 de noviembre de 2026. Basado en context/knowledge/casos_de_uso.md (usuarios, casos de uso y mapa de
pantallas) y en las capacidades de Capacidades.39.md. Es un diseño propuesto: no está construido ni validado
con usuarios.
-->

# Interfaz y flujos de uso

## Idea general

El sistema llega a sus usuarios por tres canales, en este orden:

1. **Boletín mensual** (fase 1): una página pública que se publica sola a mediados de cada mes. Nadie tiene que pedirla.
2. **Datos abiertos con DOI** (fase 1): para investigadores y para quien quiera repetir el análisis.
3. **Aplicación web** (fase 2, condicionada): para hacer preguntas propias, como un episodio, una medida o un piloto.

En la fase 1 los análisis a pedido los hace el responsable con la línea de comandos; la aplicación web los pone en manos del usuario.

## Principios

1. **Toda cifra con su incertidumbre:** rango, placebo y cambio mínimo detectable junto a cada resultado.
2. **Veredicto en lenguaje llano y en pocos estados.** En las medidas: "baja detectada", "no detectable (menor a X %)" o "no evaluable". En los episodios: "el clima lo explica", "lo explica en parte", "el clima no lo explica" o "normal". Nunca "no tuvo efecto" ni "fue la emisión".
3. **Cocientes antes que toneladas.** Las toneladas no se muestran.
4. **Los datos a la vista:** cuántas estaciones, cuántas horas de satélite y qué días se usaron o se descartaron, y por qué.
5. **Rápido en primer plano, lento precalculado:** las fichas y los episodios responden en segundos o minutos; la inversión física se calcula una vez por temporada.
6. **Todo exportable y citable:** cada resultado se descarga en PDF y CSV, con la versión del código y de los datos.

## Usuarios

| Usuario | Qué busca | Canal principal |
|---|---|---|
| Autoridad ambiental y Comisión Ambiental de la Megalópolis | Explicar episodios, diseñar contingencias y pilotos | Boletín y aplicación |
| Operador de la red de monitoreo | Saber qué estaciones fallaron | Reporte mensual de calidad |
| Periodista de datos | Explicar un episodio o contrastar un anuncio | Boletín y ficha citable |
| Organización civil o evaluador | Verificar si una medida anunciada cambió la emisión | Aplicación (ficha de medida) |
| Planeador de transporte | Saber cuánto tiempo medir un proyecto | Aplicación (planear piloto) |
| Equipo de inventario | Contrastar el reparto por zonas | Reporte por edición del inventario |
| Investigador | Series reproducibles con su incertidumbre | Datos abiertos |

## Pantallas

### 1. Inicio: el boletín del mes

```
┌───────────────────────────────────────────────────────────────────┐
│ NOₓ de la ZMVM · Octubre de 2026            [Descargar PDF] [CSV] │
├───────────────────────────────────────────────────────────────────┤
│ Emisión corregida por clima        ▁▂▂▃▂▂▃▂ (semanas)             │
│   Octubre frente a septiembre: sin cambio detectable (±30 %)      │
├───────────────────────────────────────────────────────────────────┤
│ Semanas del mes           Concentración  Clima   Veredicto        │
│   28 sep–2 oct            0.96           0.95    Normal           │
│   5–9 oct                 1.33           1.54    Normal           │
│   12–16 oct               1.20           1.12    Normal           │
│   19–23 oct               1.09           0.94    Normal (3 días)  │
├───────────────────────────────────────────────────────────────────┤
│ Calidad de las redes: 21 estaciones, 81 % de horas, 6 huecos      │
│ Ozono (feb–jun): centro limitado por COV · mapa de régimen        │
└───────────────────────────────────────────────────────────────────┘
```

Las semanas, sus cocientes y la calidad de las redes son las del prototipo con octubre de 2026; la línea de emisión del mes es ilustrativa. Cada fila de episodio abre su diagnóstico.

### 2. Episodio: ¿fue el clima?

```
┌───────────────────────────────────────────────────────────────────┐
│ Episodio  [18 dic 2023] a [22 dic 2023]   o [elegir contingencia] │
├───────────────────────────────────────────────────────────────────┤
│ EL CLIMA NO LO EXPLICA · fondo regional alto                      │
│                                                                   │
│ Concentración 1.59  ████████████|      días normales 0.81–1.23    │
│ Clima         1.12  ██████|            días normales 0.70–1.58    │
│ Fondo regional 2.09 ██████████████|    días normales 0.60–1.60    │
│                                                                   │
│ Lectura: la concentración subió 59 % y la ventilación no lo       │
│ explica; el fondo regional también subió (acumulación posible).   │
│ Días de referencia, placebos y estaciones usadas: [ver detalle]   │
│                                        [Exportar ficha] [Anotar]  │
└───────────────────────────────────────────────────────────────────┘
```

Las cifras son las de la semana previa a Navidad de 2023 con el código actual (`results/runs/episodes/pre_christmas.json`).

### 3. Evaluar una medida

```
┌───────────────────────────────────────────────────────────────────┐
│ Medida: [Hoy No Circula sabatino]   Días: [__] a [__]             │
│ Efecto anunciado (opcional): [−20 %]                              │
├───────────────────────────────────────────────────────────────────┤
│ NO DETECTABLE · el cambio fue menor que 31 %                      │
│ Cambio estimado −8 % (rango −29 % a +18 %)                        │
│ El −20 % anunciado cabe en el rango: no se puede confirmar        │
│ ni descartar con estos días.                                      │
│ Segunda opinión del satélite: −5 % (−24 % a +17 %)                │
│                       [¿Cuántos días harían falta?] [Exportar]    │
└───────────────────────────────────────────────────────────────────┘
```

Las cifras de esta pantalla son ilustrativas.

### 4. Planear un piloto

```
┌───────────────────────────────────────────────────────────────────┐
│ Efecto esperado: [10 %]   Temporada: [feb–may]                    │
│ Diseño: (•) semanas alternas   ( ) continuo                       │
├───────────────────────────────────────────────────────────────────┤
│ Con semanas alternas: detectable en ~6 temporadas                 │
│ Continuo: ~20 temporadas                                          │
│ [curva: efecto detectable frente a semanas de medida]             │
│ Advertencia: si el efecto persiste en la semana sin medida,       │
│ deje una semana de separación.                                    │
└───────────────────────────────────────────────────────────────────┘
```

Las duraciones vienen de `ficha-dias` (feb–may 2025, medida continua) y de la exploración de diseños alternados; la curva es ilustrativa.

### 5. Otras pantallas

- **Ozono:** mapa de régimen de la temporada (cociente formaldehído/NO₂ del satélite) y efecto de domingo por estación.
- **Calidad de las redes:** cortes y huecos por estación y mes, descargables para el operador.
- **Zonas:** reparto relativo de la emisión entre 6 zonas, junto al inventario.
- **Datos y método:** fuentes, cobertura, versión y limitaciones, con enlace al conjunto de datos con DOI.

## Cómo realizarían sus tareas

### Una periodista explica una semana de mala calidad del aire

1. Abre el boletín del mes o la pantalla **Episodio** y elige las fechas.
2. Lee el veredicto: por ejemplo, "el clima lo explica: la ventilación fue 2.3 veces peor que en días normales".
3. Exporta la ficha y la cita en su nota. La ficha dice qué días se compararon y con qué incertidumbre.

Hoy lo hace el responsable con `nox-ml episode --days INICIO:FIN --data INICIO:FIN`, en segundos.

### La Comisión Ambiental revisa el programa de contingencias

1. Antes de la temporada de ozono recibe la sección de ozono del boletín: el mapa de régimen y el efecto de domingo por estación.
2. Ve que en el centro recortar NOₓ no baja el ozono y que la orilla sur-poniente se acerca a estar limitada por NOₓ.
3. Con eso valora agregar medidas sobre compuestos orgánicos volátiles (vapores de combustible, solventes, gas LP) en los días de activación.
4. Después de cada contingencia, abre el episodio para ver si el clima explica su fin.

### Una organización civil verifica un anuncio

1. En **Evaluar medida** escribe las fechas de la medida y el efecto anunciado.
2. Obtiene el cambio estimado con su rango, el veredicto y si el anuncio cabe en el rango, más la segunda opinión del satélite.
3. Si el resultado es "no detectable", la ficha lo dice así ("menor a X %") y no como "no funcionó".

Hoy: `nox-ml ficha-medida --days INICIO:FIN --data INICIO:FIN --claim -0.2`.

### Un planeador diseña un piloto medible

1. En **Planear piloto** escribe el efecto que espera y la temporada.
2. Compara el diseño continuo con el de semanas alternas y ve cuántas semanas o temporadas necesita.
3. Elige el diseño y exporta la tabla para su propuesta de financiamiento.

Hoy: `nox-ml ficha-dias --data INICIO:FIN --drops 0.1`; los diseños alternados entran en la fase 1.

### El operador de la red recibe el reporte de calidad

1. A mediados de mes recibe la sección de calidad del boletín: cortes de red, estaciones con huecos o valores repetidos y diferencias con la fuente oficial.
2. Corrige o documenta las fallas; el boletín siguiente muestra si se resolvieron.

### Un investigador reutiliza los datos

1. Descarga el conjunto de datos con DOI: estaciones con sus correcciones de calidad, recortes de TEMPO, contingencias y cortes de red.
2. Repite cualquier cifra con el repositorio y cita el conjunto en su trabajo.

## Qué se construye en cada fase

| Elemento | Fase 1 (12 meses) | Fase 2 (condicionada) |
|---|---|---|
| Boletín mensual | Página estática generada cada mes | Integrado en la aplicación como inicio |
| Datos con DOI | Publicación anual en Zenodo | Actualización por temporada |
| Episodio, medida y piloto | Línea de comandos, operada por el responsable | Pantallas de la aplicación |
| Ozono y calidad de redes | Secciones del boletín | Pantallas propias |
| Zonas | Reporte por edición del inventario | Pantalla propia |

Antes de construir la fase 2 hay que probar las pantallas con al menos un usuario de cada perfil: autoridad, periodista, organización civil e investigador.
