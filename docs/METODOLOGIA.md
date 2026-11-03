# Datos y metodología

Estas definiciones corresponden al conjunto actual de ESPN. Para el conjunto
histórico consulta [StatsBomb](HISTORICO_STATSBOMB.md).

## Qué significa que los equipos estén actualizados

- La lista de clubes procede del catálogo de la temporada de ESPN, validando
  que sean 20 equipos distintos de LaLiga.
- Cada plantilla se consulta para esa misma temporada. Se verifican liga,
  temporada, equipo, jugador y género masculino.
- El equipo mostrado es el de la plantilla consultada. Las estadísticas son
  agregados del jugador en LaLiga y la temporada: un traspaso entre dos clubes
  puede dejar minutos de ambos en un único perfil asociado a su plantilla.
- La fecha indica cuándo se consultó la fuente. No garantiza que ESPN ya haya
  incorporado todos los fichajes. La app avisa si la consulta supera siete días.
- Se usan grupos amplios de posición: defensa, mediocentro y delantera. La
  fuente consultada no permite afirmar qué porcentaje de minutos jugó en cada
  subrol; no se inventa ese dato.

## Las doce métricas del conjunto actual

Los minutos proceden de ESPN. Cada conteo se transforma con `90 * conteo / minutos`.
La precisión de pase es un porcentaje que se calcula aparte.

| Métrica | Campo ESPN |
| --- | --- |
| Pases intentados /90 | `totalPasses` |
| Pases completados (%) | `100 * accuratePasses / totalPasses` |
| Pases de tiro /90 | `shotAssists` |
| Conducciones progresivas (ESPN) /90 | `progressiveCarries` |
| Centros intentados /90 | `totalCrosses` |
| Pases largos intentados /90 | `totalLongBalls` |
| Recuperaciones /90 | `recoveries` |
| Entradas ganadas /90 | `effectiveTackles` |
| Intercepciones /90 | `interceptions` |
| Tiros /90 | `totalShots` |
| Duelos ganados /90 | `duelsWon` |
| Toques en área rival /90 | `touchesInOppBox` |

Las conducciones progresivas siguen la definición del proveedor. No equivalen
al umbral geométrico de 10 m del experimento histórico de StatsBomb. Los pases
son los totales de ESPN, sin reconstruir el filtro de juego abierto. No hay
coordenadas de eventos para calcular xT, presiones ni entradas al área.

## Cómo se calcula el parecido

Se filtra por posición, liga, temporada y minutos. `StandardScaler` estandariza
cada métrica sobre ese grupo, incluida la referencia. Se calcula:

```text
distancia = sqrt(sum(peso * (z_referencia - z_candidato)^2) / sum(pesos))
```

Menor distancia significa mayor parecido en estas métricas. No es una
probabilidad de éxito ni una valoración global de calidad. La explicación
muestra la contribución exacta de cada métrica al cuadrado de la distancia.

Todos los pesos valen 1 en modo equilibrado. Creación eleva a 3 los pases de
tiro, las conducciones progresivas y los toques en área rival. Defensa eleva
a 3 las recuperaciones, las entradas ganadas y las intercepciones.

Limitaciones: sin ajuste por posesión, rival, contexto táctico o posiciones
finas. Métricas correlacionadas pueden contar un comportamiento varias veces.
Los pesos son decisiones explícitas, no parámetros aprendidos. El modelo
inicial es un baseline de vecinos más cercanos, sin etiquetas de fichajes
exitosos. La inferencia de estilos es un módulo de reglas separado del ranking. La estabilidad técnica se estudia con perturbaciones y umbrales de minutos. Sigue pendiente la evaluación externa de relevancia futbolística; estabilidad no equivale a acierto.

## Descarga, calidad y reproducción

Cada actualización guarda los JSON originales en una carpeta nueva, con URLs,
fecha de consulta y hashes SHA-256. No se sustituyen valores ausentes por ceros.
Un registro incompleto, sin minutos, con conteos incoherentes o presente en más
de una plantilla se excluye y se explica en `quality_report.json`.

Los nuevos perfiles se activan mediante un puntero que solo cambia después de
terminar el procesamiento. Una descarga fallida o un archivo modificado no
sustituyen el conjunto activo. `active.json` identifica la carpeta utilizada:

```text
data/raw/espn/<consulta>/manifest.json
data/processed/espn/<consulta>/profiles.csv
data/processed/espn/<consulta>/metadata.json
data/processed/espn/<consulta>/quality_report.json
data/processed/active.json
```

Para separar descarga y procesamiento:

```powershell
uv run scoutfit fetch --refresh
uv run scoutfit build
uv run scoutfit recommend "espn:250465:83" --min-minutes 450 --top-k 5
```

El último comando ilustra el ID de Pedri en la consulta inicial; comprueba que siga presente en tu conjunto activo. Los IDs
vigentes se encuentran en el CSV activo. `fetch` sin `--refresh` reutiliza la
última descarga; `update` siempre vuelve a consultar la fuente y procesa.


## Evaluación y búsqueda por objetivos

La búsqueda por objetivos calcula el déficit ponderado respecto a percentiles
solicitados; no predice el rendimiento futuro. Las condiciones estrictas son opcionales.
Los filtros de clubes y minutos de candidatos no cambian la población utilizada
para calcular la escala del ranking.

Los nueve perfiles inferidos son reglas de afinidad a arquetipos, no clustering
aprendido. Consulta [las reglas](PERFILES_INFERIDOS.md),
[la evaluación](EVALUACION.md) y [el contexto de muestra](SEGUIMIENTO_Y_MUESTRA.md).
La precisión futbolística sigue pendiente de valoraciones humanas suficientes.
