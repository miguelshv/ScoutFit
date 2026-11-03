# Seguimiento y contexto de muestra · ScoutFit 0.10

## Cambios en un proyecto

Abre **Proyectos de scouting y búsquedas guardadas**, elige proyecto y candidato y
despliega **Qué ha cambiado en mis candidatos → Mostrar seguimiento del proyecto**.
La tabla compara cada candidato con el snapshot exacto que tenía cuando se guardó.

Se sigue el ID del jugador dentro de la misma fuente, liga y temporada. Un cambio
de equipo puede modificar `profile_id`, pero no rompe el seguimiento. Las consultas
deben usar las mismas métricas. No se comparan temporadas distintas ni se sustituye
una consulta de origen ausente por otra aproximada.

La tabla muestra minutos, partidos y métricas modificadas; no incluye las notas en
su CSV de cambios. Las notas y estados originales permanecen en el proyecto.
Si todavía es la misma consulta de origen, no se presenta una variación ficticia.
Si la consulta activa es anterior a la guardada, se indica y no se calcula el cambio.

## Contexto de muestra

En Recomendaciones y Resultados del objetivo está **Contexto de muestra · minutos
y población**. Informa de la población que se usa para estandarizar métricas y
calcular percentiles, antes de restringir los clubes o minutos de los candidatos.
Incluye tamaño, clubes y mediana de minutos. Una población inferior a 20 perfiles
recibe un aviso descriptivo: el umbral no es una prueba de significación estadística.

La participación se describe con reglas orientativas:

- Menos de 450 minutos: participación reducida.
- De 450 a 899: participación intermedia.
- Desde 900: mayor participación acumulada.

Estas etiquetas no son niveles de confianza ni garantías de estabilidad. La fuente
no aporta aquí observaciones por partido para estimar intervalos de confianza.

**Comparar mínimos de minutos** recalcula la búsqueda con el mínimo actual y los
umbrales 450, 600 y 900. Mantiene pesos, exclusión del mismo club, perfil inferido,
clubes y rango de minutos de candidatos; en modo objetivo conserva objetivos,
importancias y cumplimiento estricto. No cambia los controles de la búsqueda activa.

Se muestra población, candidatos, coincidencias con el top actual y Jaccard. Si no
hay candidatos en ninguna de las listas, el Jaccard queda sin calcular. Si la
referencia no alcanza el mínimo, el caso se marca como no comparable. El resultado
se invalida cuando cambian la consulta o los parámetros, para evitar mostrar un
experimento antiguo como si perteneciera a una búsqueda nueva.

## Ficha de diferencias

En **Evolución**, el selector **Jugador de evolución** permite examinar un jugador
sin cambiar la referencia de la búsqueda. El gráfico temporal y la tabla existentes
siguen mostrando las consultas reales. Debajo, **Qué ha cambiado entre dos consultas**
permite elegir una consulta final y otra estrictamente anterior.

La ficha muestra variaciones de minutos y partidos, equipos publicados, métricas
modificadas y la tabla Antes/Después/Variación. Las barras incluyen solo métricas /90;
el porcentaje de pase usa puntos porcentuales y aparece en la tabla. No se mezclan
esas dos unidades en un eje. CSV redondeado para lectura y JSON con valores completos.

Si faltan perfiles, no se calculan variaciones. Si faltan valores, permanecen vacíos
y el estado indica datos incompletos. Si disminuyen minutos, partidos o un conteo
acumulado reconstruido, se advierte de una posible corrección del proveedor. Una
tasa /90 menor con más minutos no es por sí sola una corrección: puede ser un cambio
normal del agregado de temporada. Los aumentos no se interpretan como mejora.

## Comprobación real

Hay cuatro consultas guardadas de LaLiga masculina 2026/27. Para Andrei Ratiu,
entre `20261029T192735329144Z` y `20261103T144404526587Z`, se verifican **+90 minutos,
+1 partido y 11 métricas modificadas**, sin señal de corrección del proveedor.
No se han añadido candidatos o notas ficticias al espacio del usuario.

En el navegador, su población a 450 minutos contiene 84 defensas de 20 clubes,
con mediana de 690 minutos. Al elevar el mínimo a 600, la población pasa a 60 y
se conservan tres de los cinco candidatos del top actual: Jaccard 0,43. A 900,
Ratiu no alcanza el mínimo y no se calcula una similitud entre listas.

Capturas verificadas: [contexto de muestra](../assets/scoutfit-v010-sample.jpg) y
[ficha de cambios](../assets/scoutfit-v010-changes.jpg).
