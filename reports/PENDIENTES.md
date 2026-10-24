# Estado al cierre de la fase de investigación (2026-10-24)

El detalle de cada resultado está en `RESUMEN.md` (cronológico) y en el reporte citado. El resumen ejecutivo publicado es https://claude.ai/artifact/XeQA1FdokQaYXQJfvhHbYb (versión 3); la copia local es `resumen_ejecutivo.html`.

## Configuración estándar vigente

| Componente | Valor | Reporte |
|---|---|---|
| Transporte | Puffs de 24 h | `puffs_cdmx.md`, `vida_quimica.md` |
| Química | Vida del NOₓ por OH (mes y hora) | `vida_quimica.md` |
| Zonas | 13 grupos de alcaldías y municipios (`REGION_SCHEME="admin_grupos"`) | `zonas_admin.md` |
| Viento | Promedio del dominio, ensamble σθ = 30°, piso `U_MIN = 2.0` m/s | `base_sigma30.md`, `estancamiento.md` |
| Satélite | TEMPO con σ ×3 (un tercio de peso) | `peso_tempo.md` |
| Restricción | Cociente de tráfico de Infovial (día completo) | `sesgo_domingos.md` |
| Capa límite | ERA5 + MERRA-2 | `capa_limite.md` |
| Salida principal | Estimador normalizado por meteorología | `validacion_2020.md` |
| Centrales | A priori de Climate TRACE; no identificables | `centrales_generacion.md` |

## Resultados principales

- **Domingo frente a hábil:** 0.65–0.69, frente a 0.65–0.73 del tráfico contado.
- **Confinamiento 2020:** −41 a −42 %.
- **Contingencias 2024:** sin baja en NOₓ ni en CO.
- **Placebos:**
  - días al azar: ±10–20 %;
  - días estancados: pasan;
  - dentro de primavera: pasa;
  - invierno frente a primavera: falla.
- **Patrón espacial:** coincide con EDGAR (Spearman 0.75) y con el cociente CDMX/Edomex del inventario.
- **Bogotá, Día sin carro:** CO −23 %, NOₓ sin cambio, placebo ±9 %.
- **Los Ángeles:** el domingo da 0.52 frente a 0.67 de la literatura. No pasa limpio como control positivo.
- **Banco de datos:** el cambio mínimo detectable lo fija el transporte, no el número de estaciones. El reparto por zona depende del satélite.
- **Totales absolutos:** no son confiables. Se movieron entre 40 % y 100 % del inventario según la configuración.

## Pendientes

### Dependen del usuario

- [ ] Enviar las solicitudes a SEDEMA (correo + PNT) y a la ADIP. Instrucciones en `solicitudes_datos.md`.
- [ ] Verificar los correos de UNAM antes de enviar la carta 3.
- [ ] Crear la cuenta de PeMS (validación de Los Ángeles).
- [ ] Opcional: bajar EMFAC a mano; el portal bloquea las descargas automáticas.

### Técnicos (por valor)

1. **Exceso de efecto de la capa límite en invierno.** Es la causa común del cuartil ventilado en 1.15 y del placebo invierno-primavera que falla (`estancamiento.md`, `vida_quimica.md`).
2. **Los Ángeles:**
   - separar los festivos de los domingos;
   - repetir con PeMS cuando haya cuenta (`otras_ciudades.md`).
3. **Degradación inversa en Los Ángeles** (banco de datos; no se corrió).
4. **Pruebas del plan de validación sin datos externos:** combustible por entidad (5), experimentos naturales (6) y TROPOMI (7) (`plan_validacion.md`).
5. **La PINN sigue con pluma estacionaria:** la referencia es el modelo lineal con puffs.
6. **Separar el origen de la emisión** (tráfico, industria, área). Queda para después y no va en el resumen ejecutivo (`mejoras.md`).
7. **Bogotá completa,** después de que se estabilice el núcleo (`bogota.md`).
8. **Capa límite de dos capas, GEOS-CF y HCHO:** solo si un problema medido lo pide (`multifisica.md`).

### Documentos que quedaron desactualizados

- `explainer.html` y `como_funciona.html`: no tienen la configuración estándar vigente.
- `caso_de_uso.md`: no tiene CO en contingencias, el piso de viento ni las zonas administrativas.
