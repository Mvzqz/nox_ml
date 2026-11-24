# Presentación NOx·ML · cómo verla y editarla

## Verla

Abre `index.html` en Chrome, Edge o Firefox (doble clic basta; no necesita servidor). Las fuentes Jost y Montserrat se cargan de Google Fonts, así que sin internet se ven con una fuente de respaldo.

| Tecla | Acción |
|---|---|
| → · espacio · clic en la parte derecha | Siguiente paso (primero lo que aparece con clic, luego la siguiente diapositiva) |
| ← · clic en el tercio izquierdo | Paso anterior |
| N | Mostrar u ocultar las notas del presentador |
| F | Pantalla completa |
| Inicio / Fin | Primera / última diapositiva |

La URL guarda la diapositiva actual (`index.html#7`), útil para abrir directo en una.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `index.html` | Las 14 diapositivas, una por `<section>`, en orden. Un comentario marca cada diapositiva y cada parte |
| `deck.css` | Colores, tipografía, componentes y animaciones de las diapositivas |
| `visor.css`, `visor.js` | El visor: escala, navegación, fragmentos y notas. No hace falta tocarlos para editar contenido |
| `assets/` | Fotos, logo y captura del boletín |

## Editar

- **Texto:** búscalo en `index.html` y cámbialo directamente.
- **Posición y tamaño:** cada diapositiva mide 1920 × 1080 px. Los elementos con clase `pin` se colocan con `left`, `top` y `width` en píxeles en su atributo `style`.
- **Notas del presentador:** el `<aside>` al final de cada `<section>`.
- **Lo que aparece con clic:** `class="... fragment"` con `data-fragment-index="1"`, `"2"`, … en el orden en que aparece.
- **Animación de entrada:** clase `rise` (sube) o `fade` (aparece) con `--i:n` en el `style` para el retraso escalonado.
- **Colores por parte:** al final de `deck.css`. Problema en rojo coral (`#F0604D`, texto `#FF8F7A`), solución en verde (`#7FD15A`, texto `#B6EA7E`), impacto y futuro en azul claro (`#5FB4FF`, texto `#9FD3FA`). El fondo es azul noche `#0B1424` con brillos de cielo.
- **Imágenes:** reemplaza el archivo en `assets/` con el mismo nombre, o cambia el `src` del `<img>`.
- **Fondos:** cada diapositiva empieza con un `<svg>` de 1920 × 1080 con degradados radiales deformados (filtro `-warp`) y grano (filtro `-grain`). Cambia `cx`, `cy` y `r` del `radialGradient` para mover o agrandar un brillo.
- **Agregar una diapositiva:** copia un `<section>` completo, cámbiale el `id` (y el prefijo de los `id` de su SVG para que no choquen) y ajusta los números de página.

## Créditos de las imágenes

- Ciudad de México en un día despejado: Ukaizen, Wikimedia Commons, CC BY-SA 4.0.
- Ciudad de México con bruma: Fidel Gonzalez, Wikimedia Commons, CC BY-SA 3.0.
- Avenida Juárez, 6 de abril de 2020: EneasMx, Wikimedia Commons, CC BY-SA 4.0.
- Captura del boletín, logo, mapas, diagramas e íconos: Equipo 39.
