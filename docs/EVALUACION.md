# Evaluación de ScoutFit

## Dos preguntas distintas

1. ¿El ranking es estable si cambian un poco los pesos o los minutos mínimos?
2. ¿Los candidatos tienen sentido como sustitutos de estilo según una persona?

La primera se comprueba con experimentos reproducibles. La segunda necesita
valoraciones humanas; las pruebas de software no la sustituyen.

## Sensibilidad técnica

La pestaña Evaluación ejecuta 30 perturbaciones multiplicativas de los pesos
con distribución lognormal, sigma 0,15 y semilla 7. Compara cada top-k con el
ranking base mediante Jaccard: tamaño de la intersección dividido por el de
la unión. Muestra también la frecuencia con que aparece cada candidato.

Se prueban por separado los umbrales 450, 600 y 900 minutos, además del actual.
Si la referencia no alcanza un mínimo, ese caso se indica como no comparable.
Las etiquetas de estilo permanecen fijas durante el experimento.

Un Jaccard alto indica poca sensibilidad a estas perturbaciones concretas.
No mide relevancia futbolística ni una probabilidad de que funcione un fichaje.

## Dos distancias

La app usa distancia euclídea ponderada sobre variables estandarizadas.
El laboratorio permite compararla con coseno sobre esas mismas variables
ponderadas. Los valores de ambas distancias tienen escalas distintas; se
comparan listas y posiciones, no sus magnitudes directamente.

Un vector nulo no tiene ángulo definido. En ese caso el laboratorio omite el
método para la referencia o excluye ese candidato y lo explica, en lugar de
inventar una distancia de coseno.

## Construir el benchmark

### Campaña guiada de la versión 0.9

1. Abre **Evaluación guiada · 20 referencias**, encima de los proyectos de scouting.
2. Pulsa **Preparar o continuar evaluación**. La consulta del 03/11/2026 contiene
   20 referencias y 302 parejas propuestas; todas empiezan sin valorar.
3. Elige referencia y pareja pendientes. Contrasta las estadísticas, funciones y,
   cuando sea posible, vídeo. El formulario no enseña distancias ni orden del ranking.
4. Introduce relevancia 0/1/2, nombre o alias y justificación. **Guardar y seguir con
   pendientes** guarda la valoración local y retira esa pareja de la cola pendiente.
   Para omitir una pareja, elige otra; no le asignes 0 por desconocimiento.
5. Pulsa **Generar informe de evidencia**. Puedes descargar el JSON sin notas ni
   identidades de los revisores. El CSV vacío permite repartir las parejas y luego
   importar las revisiones mediante las herramientas de la pestaña Evaluación.

La campaña se guarda en `data/evaluation/campaigns/`, con selección de parejas,
SHA-256 del CSV, consulta exacta, métricas, mínimo de 450 minutos, k=5 y semilla 7.
Se reutiliza al volver a entrar; no cambia al tocar los filtros o actualizar el código.
Una consulta nueva tiene otra campaña y no hereda las valoraciones de la anterior.

El informe utiliza únicamente las parejas de la campaña y la consulta correspondiente:

- `pending_review`: todavía no hay referencias con valoraciones suficientes para métricas.
- `partial_review`: existen resultados evaluables, pero la campaña sigue incompleta.
- `evaluated`: todas las parejas están revisadas y ambas distancias son evaluables
  para todas las referencias. Esto no certifica relevancia en toda la liga.

Si se edita una nota de relevancia, el informe anterior se invalida aunque el número
de parejas revisadas no cambie. Las etiquetas no se generan con IA ni con las propias
distancias del modelo. **La valoración humana real está pendiente de completarse.**

### Plantilla y comandos existentes

Pulsa «Crear plantilla de 20 referencias» o ejecuta:

```powershell
uv run scoutfit benchmark --queries 20
```

La selección alterna grupos de posición y prioriza minutos altos. Para cada
referencia reúne candidatos de ambos métodos y algunos controles de la misma
posición, liga y temporada. El orden de las filas no es un ranking de relevancia.
Todos los campos de relevancia quedan vacíos.

Esta selección constituye un conjunto de candidatos a revisar, no una muestra
aleatoria representativa de toda la liga. Las métricas deben interpretarse con
ese sesgo de selección.

## Rúbrica humana

- **0:** no es adecuado como sustituto de estilo para esta referencia.
- **1:** comparte rasgos, pero hay diferencias importantes de función o estilo.
- **2:** es un candidato razonable como sustituto de estilo.

Justifica la nota con comportamientos concretos. No uses fama, precio o goles
como sustituto automático de compatibilidad. Si no sabes valorar una pareja,
deja la relevancia vacía. Puedes usar el formulario para una pareja o completar
el CSV y subirlo desde la app. También puedes ejecutar:

```powershell
uv run scoutfit import-reviews RUTA_AL_CSV_REVISADO.csv
uv run scoutfit evaluate
```

La importación valida todo el archivo antes de escribir: consulta exacta,
jugadores existentes del mismo grupo, nota y valor entre 0 y 2. Los campos sin
valorar se omiten. No se transfieren juicios a otra consulta automáticamente.

## Qué miden los resultados

Para cada referencia se reordena **solo el conjunto revisado** según cada
método, con pesos equilibrados y sin filtro de perfil inferido. Se exige al
menos dos candidatos válidos con relevancias diferentes.

- **nDCG@k:** calidad del orden en ese conjunto, usando relevancia graduada 0/1/2
  y descuento logarítmico. Se utiliza `sklearn.metrics.ndcg_score`.
- **Precisión@k:** proporción de candidatos con nota mayor que 0 en los primeros
  `min(k, tamaño del conjunto revisado)`.
- **Recuperación@k:** fracción de los candidatos positivos revisados que aparece
  en esos primeros puestos.
- **Cobertura del top-k:** qué proporción del top-k completo tiene revisión humana.

No se trata a los candidatos sin valorar como negativos. Los resultados se
promedian por referencia y se indica el número de referencias evaluadas.
No equivalen a precisión sobre todos los posibles jugadores de la liga.

Sin revisión suficiente, el estado es **pending_review** y no se muestra una
cifra de calidad inventada. Las valoraciones se guardan en archivos locales
excluidos de Git; decide qué notas quieres publicar al documentar un caso.

## Evolución y contexto

El histórico usa consultas reales del mismo proveedor, liga, temporada y
versión de métricas. Sigue el ID del jugador aunque cambie de equipo. Para
un conteo /90 se puede recuperar el conteo acumulado y calcular su incremento
entre consultas si los minutos y conteos aumentan de forma coherente.

El resultado corresponde a un tramo entre fechas, que puede contener varios
partidos. Si no hay minutos nuevos no se calcula una tasa; si disminuyen
minutos o conteos se señala una posible corrección del proveedor. Los huecos
no se rellenan ni se unen para inventar continuidad.

La fuente actual no proporciona aquí un desglose validado por partido ni
posesión del equipo. No se afirma haber medido regularidad por partido,
efectos causales ni un rendimiento ajustado por posesión.
