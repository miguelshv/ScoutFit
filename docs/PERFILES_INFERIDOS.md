# Perfiles futbolísticos inferidos · archetypes-v1

ScoutFit conserva la posición publicada por ESPN y añade una interpretación de
estilo basada en estadísticas. No afirma haber observado dónde juega un futbolista.
Un perfil de finalización puede describir tanto a un extremo como a un delantero.

## Método

1. Separar por proveedor, liga, temporada y posición de la fuente.
2. Usar únicamente jugadores con al menos 450 minutos, métricas finitas y un
   mínimo de ocho compañeros de grupo. El umbral es una decisión del MVP, sin
   validación deportiva externa.
3. Calcular rangos percentiles con empates promediados. Las métricas constantes
   se fijan en 0,5, pues no distinguen estilos.
4. Obtener la afinidad de cada arquetipo como la media ponderada de sus percentiles.
5. Elegir la afinidad mayor; si la diferencia entre las dos primeras es menor
   de 0,05, indicar «Mixto» y mostrar la alternativa. Sin diferencia entre todos
   los arquetipos no se asigna una etiqueta. Las afinidades no son probabilidades.

Las reglas se definen en `src/scoutfit/roles.py`. Son arquetipos diseñados a mano,
no clusters aprendidos ni un modelo entrenado con etiquetas de entrenadores.
No dependen de los pesos elegidos en la interfaz ni de los filtros de búsqueda.
Una nueva descarga puede cambiar los percentiles y por tanto las etiquetas.

## Arquetipos y pesos

Los valores entre paréntesis son pesos. Todas las métricas de volumen son /90.

| Posición publicada | Perfil inferido | Métricas |
| --- | --- | --- |
| Defensa | Defensa distribuidor | Pases (2), precisión (1), pases largos (2) |
| Defensa | Defensa recuperador | Recuperaciones (1), entradas ganadas (2), intercepciones (2), duelos ganados (1) |
| Defensa | Defensa de proyección | Centros (2), conducciones progresivas (2), pases de tiro (1), toques en área (1) |
| Mediocentro | Mediocentro organizador | Pases (2), precisión (1), pases largos (2) |
| Mediocentro | Mediocentro recuperador | Recuperaciones (1), entradas ganadas (2), intercepciones (2), duelos ganados (1) |
| Mediocentro | Mediocentro creador | Pases de tiro (2), conducciones progresivas (2), toques en área (1) |
| Delantera | Atacante finalizador | Tiros (2), toques en área (2) |
| Delantera | Atacante creador | Pases de tiro (2), pases (1), precisión (1), pases largos (1) |
| Delantera | Atacante de conducción y centro | Conducciones progresivas (2), centros (2), duelos ganados (1) |

Los prototipos utilizan intensidades altas: explican qué comportamientos tienen
más presencia relativa, sin asegurar la función táctica ni que sean mejores.
La evidencia muestra hasta tres métricas del arquetipo con sus percentiles.

## Efecto en las recomendaciones

Con la casilla de mismo perfil activada, un mediocentro creador se compara con
otros mediocentros etiquetados como creadores de la misma liga y temporada.
Los perfiles mixtos se agrupan por su afinidad principal y muestran la alternativa.
La estandarización del ranking sigue utilizando el grupo amplio de posición;
activar la casilla filtra candidatos sin alterar sus distancias individuales.

Si la referencia no tiene perfil por falta de minutos, tamaño de grupo o señal,
la app lo explica y mantiene la comparación por posición. Si tiene perfil pero
no hay candidatos con los filtros elegidos, la lista queda vacía con un mensaje;
no se sustituyen candidatos por otros estilos sin indicarlo.

## Límites

No se han validado estas etiquetas con analistas deportivos. Posesión, equipo,
rival y definición del proveedor influyen en las estadísticas. No deben confundirse
con una clasificación confirmada de centrales, laterales, extremos o interiores.
Se mantiene un mínimo fijo para reducir cambios causados por los controles de
la interfaz, pero no se ha medido la incertidumbre de las etiquetas.
