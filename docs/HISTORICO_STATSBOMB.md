> Archivo histórico: este documento describe la primera versión femenina; el conjunto activo es LaLiga masculina.

# ScoutFit ⚽

**Encuentra jugadores de estilo similar y entiende cada recomendación.**

![StatsBomb](../assets/statsbomb.png)

ScoutFit transforma eventos de StatsBomb en perfiles por 90 minutos, compara
jugadores del mismo rol y explica qué métricas los acercan o separan. El primer
conjunto es la **FA Women's Super League 2023/24**, con 132 partidos disponibles.
Puedes elegir otra competición del catálogo. No necesitas una clave API.

La ejecución inicial utiliza **124 partidos**, tras excluir ocho por intervalos
de alineación inconsistentes, y genera **299 perfiles jugador/equipo**. De ellos,
194 perfiles de campo cumplen el filtro de 450 minutos. Consulta el
[registro de validación](VALIDACION_STATSBOMB.md) y la
[guía de tu primera semana](PRIMERA_SEMANA.md).

## Empezar en Windows

Requisitos: [uv](https://docs.astral.sh/uv/getting-started/installation/), Python
3.11 o posterior y conexión para instalar dependencias y descargar los datos.
Ejecuta los comandos **desde la carpeta `scoutfit`**:

```powershell
uv sync --locked --extra dev
uv run scoutfit fetch --source statsbomb
uv run scoutfit build --source statsbomb
uv run streamlit run app.py
```

Abre http://localhost:8501. Selecciona un rol, una referencia y el mínimo de
minutos. La descarga completa puede ocupar cientos de MB; se guarda en caché
y se reanuda sin repetir archivos completados.

Para probar con una muestra pequeña:

```powershell
uv run scoutfit fetch --source statsbomb --limit 12
uv run scoutfit build --source statsbomb
uv run streamlit run app.py
```

La aplicación identifica la muestra como parcial y usa 90 minutos como filtro
inicial; en el conjunto completo usa 450. El límite toma los primeros partidos
por fecha: no constituye una muestra representativa de toda la temporada.
Vuelve a ejecutar `fetch` sin límite y `build` para completar el conjunto.

Otros comandos:

```powershell
uv run scoutfit competitions
uv run scoutfit fetch --source statsbomb --competition 37 --season 90
uv run scoutfit build --source statsbomb --competition 37 --season 90
uv run scoutfit recommend "ID_JUGADOR:ID_EQUIPO" --min-minutes 450 --top-k 5
```

Los identificadores están en `data/processed/profiles.csv`. Cada `build`
reemplaza las tablas procesadas de la competición activa, conservando los
datos originales en caché. No mezcla temporadas en una comparación.

## Qué incluye v0.1

- Descarga fijada a una revisión de StatsBomb, con manifiesto de procedencia.
- Minutos desde los intervalos reales de alineación, incluyendo descuento.
- Diez métricas explícitas y perfiles separados por jugador y equipo.
- Vecinos por distancia estandarizada, con prioridades equilibrada, progresión
  y defensa. La explicación descompone exactamente el cuadrado de la distancia.
- Interfaz con filtros, comparación visual y exportación CSV.
- Pruebas de cálculos y restricciones del ranking; CI sin descargas de datos.

## Cómo funciona

```text
StatsBomb JSON → caché fijada por revisión → intervalos y eventos
              → profiles.csv → grupo del mismo rol → StandardScaler
              → distancia ponderada → candidatos + explicación
```

La distancia es `sqrt(sum(w * (z_referencia - z_candidato)^2) / sum(w))`.
Una distancia menor significa mayor parecido, **no mejor jugador ni mayor
probabilidad de éxito de un fichaje**. No se presenta un porcentaje artificial
de compatibilidad. `StandardScaler` se ajusta sobre todo el grupo elegible,
incluida la referencia y antes de excluir al equipo. Las métricas constantes
no contribuyen a la distancia. Los pesos predeterminados son 1; la prioridad
de progresión eleva a 3 sus tres métricas y la de defensa hace lo mismo con
presiones y acciones defensivas.

Este primer modelo es un **baseline de vecinos más cercanos**, sin etiquetas
de fichajes exitosos. No utiliza deep learning ni contiene todavía xT.

## Definiciones

Los eventos de StatsBomb usan un campo de 120 × 80 unidades, orientado con el
equipo que actúa atacando hacia x=120. Para calcular distancias se aproxima a
105 × 68 metros. Es una convención del modelo, no la medición de cada estadio.

| Métrica | Definición |
| --- | --- |
| Pases /90 | Intentados, excluyendo córner, falta, saque de puerta, centro y banda |
| Precisión de pase | Completados / intentados de ese mismo conjunto; 0 si no hay intentos |
| Pases progresivos /90 | Completados que reducen ≥10 m la distancia al centro de la portería |
| Conducciones progresivas /90 | Conducciones que reducen ≥10 m esa distancia |
| Entradas al último tercio /90 | Pase completado o conducción con inicio x<80 y final x≥80 |
| Entradas al área /90 | Pase completado o conducción desde fuera al rectángulo x≥102, 18≤y≤62 |
| Pases bajo presión /90 | Completados con `under_pressure=true` |
| Presiones /90 | Eventos `Pressure` |
| Acciones defensivas /90 | Entradas de tipo `Tackle` e intercepciones con resultado ganado/exitoso |
| Tiros /90 | Eventos `Shot`, incluidos balón parado y penaltis durante el partido |

Entradas al tercio y al área usan los pases de juego abierto definidos arriba.
No se cuentan tandas de penaltis. Los valores /90 se calculan como
`90 * conteo / minutos`; la precisión de pase es un porcentaje y no se divide
por minutos. No se suman filas de eventos para inferir tiempo de juego.

El reloj de las alineaciones se convierte a tiempo acumulado usando la duración
observada de cada periodo. Los intervalos se unen antes de sumar minutos para
evitar duplicados. Si hay intervalos invertidos o solapados, se excluye **todo
el partido**, antes de acumular estadísticas. `data/processed/quality_report.json`
registra cada exclusión; la interfaz muestra la cobertura efectiva. Se verifica
el SHA-256 de cada archivo antes de procesarlo. Las posiciones se agrupan en central, lateral/carrilero,
mediocentro, banda, mediapunta y delantera. El rol predominante es el de más
minutos; `role_share` muestra su proporción. La interfaz excluye portería.
Un jugador que cambia de equipo conserva un perfil por equipo y nunca se
recomienda a sí mismo desde otra etapa.

## Calidad y límites

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Las pruebas usan eventos sintéticos con resultados conocidos, no requieren
red y verifican minutos, descuentos, cambios, pases fallidos, geometría,
filtros y contribuciones a la distancia. No son una validación deportiva del
ranking. Todavía no hay una evaluación externa de relevancia de candidatos.

Limitaciones: sin ajuste por posesión, contexto táctico, rival o nivel de liga;
las agrupaciones de posición son amplias y las métricas de un perfil incluyen
todo su tiempo, aunque haya cambiado de rol. El umbral de minutos reduce ruido,
pero no mide incertidumbre. La selección de métricas contiene correlaciones;
los pesos son decisiones explícitas, no parámetros aprendidos. No incorpora
precios, contratos, lesiones ni variables físicas.

## Próximos hitos para aprender y mejorar el portafolio

1. **EDA y revisión futbolística:** estudiar distribuciones, correlaciones y
   casos de jugadores de varios roles; documentar cinco comparaciones.
2. **Evaluación de estabilidad:** remuestrear partidos desde
   `player_matches.csv` y medir cuánto cambia el top-5 con intervalos de confianza.
3. **Más contexto:** ajustar por posesión e incorporar xT como experimento,
   comparando resultados con este baseline antes de sustituirlo.

## Estructura

```text
app.py                     Interfaz Streamlit
src/scoutfit/data.py        Descarga, caché y procedencia
src/scoutfit/features.py    Minutos, roles y métricas
src/scoutfit/recommender.py Distancias y explicaciones
src/scoutfit/cli.py         Comandos reproducibles
tests/                     Pruebas sin red
docs/                      Guía de aprendizaje
data/raw/                  JSON originales (ignorados por Git)
data/processed/            Perfiles y manifiesto (ignorados por Git)
```

## Datos y licencia

Fuente: **[StatsBomb Open Data](https://github.com/hudl/open-data)**.
La revisión usada se declara en `src/scoutfit/data.py` y en el manifiesto.
El código tiene licencia MIT. Los datos y el logotipo conservan las condiciones
de StatsBomb; consulta [NOTICE.md](../NOTICE.md). El proyecto no está afiliado a
StatsBomb. Antes de publicar análisis, conserva la atribución y el logotipo.
