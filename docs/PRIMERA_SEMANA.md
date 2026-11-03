# Tu primera semana con ScoutFit

La meta es poder explicar y defender el proyecto. Cada sesión termina con
un resultado pequeño que puedes revisar y subir como un commit propio.

## Sesión 1 · Fuente y pregunta

Ejecuta `uv run scoutfit update` y abre la aplicación. Comprueba la temporada,
los 20 clubes y la fecha de consulta. Localiza el archivo activo a través de
`data/processed/active.json` y abre `profiles.csv`. Explica por qué el equipo
es el de la plantilla consultada y las estadísticas abarcan la temporada de liga.

## Sesión 2 · Revisar una métrica

Lee `player_profile` en `src/scoutfit/espn.py`. Busca en un JSON de estadísticas
`minutes`, `totalPasses` y `accuratePasses`. Calcula a mano pases/90 y porcentaje
de acierto. Contrástalos con el CSV. Revisa qué sucede si falta una métrica.

## Sesión 3 · Entender el recomendador

Usa a Pedri como referencia y revisa sus cinco candidatos. Cambia la prioridad
a creación y a defensa. Explica qué métricas se ponderan más y por qué cambia
el ranking. Documenta una semejanza plausible y una limitación de comparar
jugadores con una posición amplia de plantilla.

## Sesión 4 · Primer análisis propio

Calcula las correlaciones entre las doce métricas. Revisa si los pases y las
recuperaciones reflejan en parte la posesión del equipo. Añade una figura y una
decisión argumentada en una nota propia. No necesitas otra librería de ML.

## Sesión 5 · Hacerlo presentable

Graba una demo de 60 segundos: pregunta, fecha, filtros, candidato y explicación.
Añade una captura real al README, ejecuta pruebas y formato y prepara el
repositorio en GitHub con sus temas y descripción.

Frase para esta versión: «Desarrollé un pipeline reproducible de plantillas y
estadísticas de LaLiga y un sistema explicable de similitud entre jugadores,
con validación de datos, interfaz interactiva y CI». Añade cifras de rendimiento
solo después de medirlas. La estabilidad técnica ya dispone de comprobaciones;
el siguiente hito es reunir revisiones humanas suficientes y documentar casos
propios. Sigue la [guía de portafolio](PORTAFOLIO.md) para preparar la presentación.
