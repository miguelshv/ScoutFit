# Observaciones e informes individuales · ScoutFit 0.12

## Abrir el cuaderno de un jugador

En la aplicación completa, abre **Archivo de trabajo → Proyectos de scouting y búsquedas
guardadas**. Selecciona el proyecto y el candidato en **Revisar candidato del proyecto**.
Si aún no tienes candidatos, crea un proyecto y añade un jugador desde su ficha de
recomendación o desde los resultados del modo objetivo.

La nota general del candidato sigue siendo editable y no se migra automáticamente
al historial: carece de fecha de observación y partido. El historial nuevo aparece en
**Observaciones de campo · N entradas**.

## Registrar una observación

Introduce fecha y partido o contexto; anota al menos una fortaleza, duda o próxima
observación. La fecha de observación puede ser anterior al día de registro, para
trabajar con vídeo antiguo. No se aceptan observaciones futuras.

Puedes añadir un enlace http/https y una posición en formato `mm:ss` o `hh:mm:ss`.
Se conserva el enlace original, incluidos sus parámetros y fragmento. La posición se
anota al lado: no se promete que cualquier proveedor de vídeo abra automáticamente
en ese instante. El vídeo no se descarga ni se inserta en la aplicación o el informe.

**Añadir observación al historial** añade un registro con identificador propio,
fecha de observación, fecha de registro y consulta estadística del contexto, si está
disponible. Las entradas anteriores se conservan. La presentación se ordena por
fecha de observación y registro, de más reciente a más antigua. Al corregir un
análisis, puedes añadir una entrada nueva que explique qué has revisado.

Si un campo no es válido o falla la escritura, el formulario conserva el borrador.
Solo se limpia después de guardar correctamente. No hay borrado ni edición de entradas
del historial en esta versión. Todo se incluye en la exportación JSON del proyecto.

## Preparar tu conclusión

En **Informe individual · conclusión y firma**, elige una de estas opciones:

- Sin conclusión: estado inicial o borrador.
- Seguir mirando.
- Encaja parcialmente.
- Descartar.

Toda conclusión distinta de Sin conclusión requiere motivos. La firma es un nombre
o alias opcional que introduces tú. **Guardar conclusión del informe** conserva la
última conclusión, sus motivos, firma y fecha; no modifica el estado de seguimiento
del candidato. Las observaciones del historial permanecen independientes.

Los campos que estás editando son un borrador hasta guardarlos. La descarga toma la
conclusión guardada y las observaciones registradas. No hay una conclusión automática,
firma ficticia o valoración inferida a partir de las estadísticas.

## Descargar la ficha individual

El HTML conserva la identidad de cuaderno editorial y funciona sin conexión. Incluye
nombre, proyecto, equipo al guardar, conclusión y firma, estadísticas de la consulta
activa, población de percentiles, observaciones con sus fechas y nota general.
Puedes abrirlo e imprimirlo o guardarlo como PDF con la función del navegador.

El JSON contiene los mismos datos con precisión numérica completa. Ambos archivos
incluyen los contenidos personales que hayas añadido; se descargan por tu acción,
sin publicarse en la demo. El HTML no contiene scripts, fuentes externas ni imágenes
remotas. Los textos se escapan y los enlaces de vídeo se validan.

La identidad del jugador utiliza fuente, liga, temporada e ID, para conservar el
cuaderno aunque cambie de equipo. Si no hay un perfil único y comparable en la
consulta activa, la ficha conserva las notas y señala que faltan estadísticas.
No mezcla otra temporada ni convierte un perfil ausente en métricas a cero.

El umbral de percentiles se elige en **Mínimo de minutos para percentiles de la ficha**,
inicialmente 450. Si el jugador no lo alcanza, se muestran los valores sin percentiles.
Puedes bajar el umbral expresamente; no se relaja de forma automática.

## Comprobación realizada

Se han superado 199 pruebas. Las nuevas verifican conservación de notas e historial,
enlaces y posiciones, fechas, firma y justificación, identidad tras cambio de club,
separación de temporadas, ausencia de percentiles con minutos insuficientes, escape
de texto y conservación del borrador ante un error.

Se revisó en el navegador una vista previa aislada de Ratiu con los datos reales de
la consulta `20261103T144404526587Z`: 630 minutos, 7 partidos y población de 84 defensas
con al menos 450 minutos. El cuaderno de esa vista previa no contiene observaciones,
conclusión ni firma. No se han añadido registros sintéticos a los proyectos del usuario.

La plantilla HTML se incluye en el wheel instalable. Se comprobó la descarga desde
Streamlit. La valoración futbolística de los candidatos sigue requiriendo criterio humano.

Capturas: [formulario de observación](../assets/scoutfit-v012-observations.jpg) y
[ficha individual sin valoraciones añadidas](../assets/scoutfit-v012-individual.jpg).
