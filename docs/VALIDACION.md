# Validación · LaLiga masculina

Comprobaciones con Python 3.12 y las dependencias de `uv.lock`, documentadas por fecha.
La consulta vigente del **03/11/2026** contiene **447 perfiles de los 20 clubes**.

## Preparación del repositorio · 03/11/2026

Comprobación local en Windows con Python **3.12.14** y uv **0.12.12**:

- **199 pruebas superadas**, con fixtures y caché en una carpeta temporal propia.
- Ruff sin errores y **70 archivos Python** con formato correcto.
- `uv.lock` comprobado sin red: **50 paquetes** resueltos.
- Wheel y archivo fuente construidos; plantilla individual incluida y archivos
  necesarios para ejecutar el proyecto presentes en la distribución fuente.
- Contenido revisado: **43 entradas en el wheel y 101 en el archivo fuente**,
  sin directorios de datos locales, informes generados ni archivos de secretos.
- Wheel instalado con dependencias del lockfile en otro entorno: importación
  desde `site-packages`, ayuda de la CLI y renderizado HTML correctos.
- La instalación de comprobación copia las dependencias para evitar heredar
  bloqueos de DLL o permisos de la caché en Windows; su temporal se elimina al terminar.
- Enlaces locales de **16 documentos Markdown** comprobados y exclusiones de Git
  verificadas para datos, cuaderno, informes y archivos de entorno.

La CI queda configurada con cuatro combinaciones: Windows/Linux y Python
3.11/3.12. Estos resultados corresponden a la comprobación local; el estado de
las ejecuciones remotas se consulta en [GitHub Actions](https://github.com/miguelshv/ScoutFit/actions).
No se cambiaron funciones de la aplicación ni se generaron valoraciones humanas
de scouting.

## Consulta inicial · 28/10/2026

Fuente: [ESPN LaLiga](https://www.espn.com/soccer/league/_/name/esp.1), servicios
JSON públicos. Temporada confirmada por el catálogo y las plantillas: **2026/27**.
Consulta iniciada a las **17:09 (Madrid)**. Snapshot: `20261028T160919586953Z`.

| Comprobación | Resultado |
| --- | --- |
| Equipos consultados | 20 |
| Equipos con perfiles utilizables | 20 |
| Perfiles masculinos con datos completos | 441 |
| Perfiles con al menos 450 minutos | 192 |
| Grupos de posición | 161 defensas, 143 mediocentros y 137 delanteros |
| Métricas de comparación | 12 |
| Identificadores | Únicos |
| Métricas de comparación ausentes | Ninguna en los perfiles admitidos |

Se excluyen 104 registros de campo: 102 sin apariciones o estadísticas de liga
disponibles, uno con cero minutos y uno sin dos de las métricas requeridas.
No se sustituyen esos datos por cero. Los porteros no se incorporan al ranking.
Cada consulta conserva su informe completo en `quality_report.json` dentro de su
carpeta procesada. `data/processed/active.json` indica cuál es la consulta vigente.

El equipo es el de la plantilla consultada, mientras las estadísticas se refieren
al jugador, liga y temporada. En un traspaso entre clubes pueden incluir minutos
del equipo anterior. La fecha de consulta no certifica que la fuente ya haya
incorporado todos los movimientos de mercado.

## Versión 0.12 · Observaciones e informe individual · 03/11/2026

- **199 pruebas superadas**: 177 anteriores y 22 nuevas. Ruff y el lock comprobados.
- Historial que añade registros y conserva nota general, seguimiento y conclusión.
  Fechas de observación/registro independientes, orden cronológico y consulta de contexto.
- Validación de fechas, longitud de texto, motivos de la conclusión y enlaces/posiciones
  de vídeo. Los errores no modifican el archivo anterior ni borran el borrador del formulario.
- Ficha de una sola persona, con estadísticas de su fuente/liga/temporada e ID estable
  tras un cambio de equipo. Otra temporada, identidad ambigua o perfil ausente dejan
  las estadísticas sin mostrar. Un mínimo no alcanzado no se reduce automáticamente.
- Texto de observaciones, contexto, firma, proyecto y nombres escapado en HTML;
  sin scripts o activos externos. Enlace original conservado con su posición anotada.
- AppTest comprueba dos observaciones sucesivas, conservación de nota general,
  recuperación tras iniciar otra sesión, conclusión sin motivos rechazada y firma persistente.
- Wheel construido y verificado: contiene `scoutfit/templates/individual.html`.
- Comprobación en navegador del formulario y descarga HTML, sobre una vista previa
  aislada de Ratiu con datos reales y ningún registro de valoración inventado.

La ficha muestra las aportaciones humanas separadas de los cálculos. La demo pública
no recibe notas, firmas o proyectos locales. No se ha completado la evaluación futbolística.

## Versión 0.11 · Identidad editorial · 03/11/2026

- 34 pruebas de interfaz y dos pruebas de informes superadas. Se comprueba el acceso
  a las herramientas tras agruparlas en Archivo de trabajo.
- 1.119 búsquedas de la demo conservan orden, distancias y contribuciones respecto a
  Python. La consulta publicada continúa siendo `20261103T144404526587Z`.
- Ruff y dependencias bloqueadas comprobados; paquete ScoutFit 0.11.0.
- Verificación en navegador de la nueva cabecera, selección de referencia y comparativa
  Pedri/Pablo Fornals. La demo no desborda el ancho normal de la página.
- Publicación Sites versión 2 confirmada, con el acceso público existente y sin
  incluir notas, proyectos o valoraciones del usuario. Captura real enlazada en README.

La revisión de diseño no sustituye la evaluación futbolística humana pendiente.

## Versión 0.10 · Seguimiento, muestra y fichas de cambios · 03/11/2026

- **177 pruebas superadas**, con 12 nuevas de cálculo e interfaz. Ruff verifica
  importaciones y formato. Dependencias sincronizadas con ScoutFit 0.10.0.
- Seguimiento desde la consulta exacta al guardar, ID estable tras cambio de club,
  conservación de las notas, rechazo de otras temporadas, bases ausentes y consulta
  activa anterior al origen. Los datos ausentes no se convierten en ceros.
- Comparación de participación con umbrales 450/600/900 y mínimo actual. Se verifica
  que los filtros no alteran la población estadística, que las restricciones se
  mantienen y que una referencia con minutos insuficientes no se fuerza a participar.
- Modo objetivo: se mantienen los mínimos deseados y la exigencia estricta; una
  lista vacía no se relaja. Jaccard queda ausente si no hay candidatos en ambas listas.
- Interfaz: análisis de muestra que se invalida al cambiar prioridades, jugador de
  evolución independiente de la referencia y selección de fechas con orden temporal
  estricto. El seguimiento no modifica el archivo de proyectos.
- Se repiten las 12 pruebas de las funciones nuevas tras reforzar el estado de
  valores incompletos: no se etiquetan como «Sin cambios».
- Comprobación sobre las cuatro consultas reales guardadas: Ratiu pasa de 540 minutos
  y 6 partidos a 630 y 7, con 11 métricas modificadas, entre el 29/10 y el 03/11.
  No se hacen consultas nuevas de red ni se fabrican registros de usuario.
- Verificación visual de la búsqueda de Ratiu: 84 perfiles a 450 minutos, 60 a 600,
  tres candidatos conservados y Jaccard 0,43. El caso 900 se marca como no comparable
  porque la referencia tiene 630 minutos. La ficha muestra los valores anteriores,
  actuales y sus diferencias con las fechas correctas.

Los tramos son agregados de temporada; no se presentan como partidos individuales.
El contexto de participación no constituye un intervalo estadístico de confianza.

## Versión 0.9 · Evaluación guiada y demo pública · 03/11/2026

- **165 pruebas superadas**. Incluyen congelación y detección de cambios de campaña,
  informes sin valoraciones inventadas, separación de otras consultas, exclusión de
  notas/alias, exportación de demo por lista permitida y recorrido del formulario.
- Tras reforzar la invalidación de informes por edición de notas de relevancia,
  se repiten las tres pruebas del módulo y las dos pruebas del recorrido guiado.
- Paridad real Python/JavaScript: **1.119 búsquedas** sobre el conjunto de 447 perfiles,
  tres prioridades y tres mínimos de minutos. Se comprueban orden, distancias con
  tolerancia 1e-9, contribuciones, filtrado sin reescalar y percentiles con empates.
- Campaña real preparada: **20 referencias, 302 parejas**, consulta
  `20261103T144404526587Z`. Estado humano: **pending_review**. Las pruebas usan
  valoraciones sintéticas únicamente en carpetas temporales; no se añaden al proyecto.
- Publicación Sites versión 1: despliegue confirmado como `succeeded`, público.
  Se verifica en navegador que carga los 447 perfiles. La demo excluye los archivos
  locales de proyectos, notas, favoritos y revisiones.
- Ruff comprueba formato e importaciones. `uv.lock` identifica ScoutFit 0.9.0.

La evaluación humana no está completada: se necesita revisar las parejas con criterio
futbolístico. La demo hace pública esa limitación y no muestra una precisión ficticia.

## Versión 0.8 · Actualización desde la aplicación · 29/10–03/11/2026

- **160 pruebas superadas**: 144 anteriores y 16 nuevas para actualización, resumen,
  bloqueo, conservación de datos y acciones de interfaz.
- El recorrido completo se prueba con un proveedor simulado de 20 clubes y 40 jugadores:
  descarga, construcción sin activación, validación, informe y publicación de la consulta.
- Se simulan fallos de red, construcción, validación y activación. Se conservan el
  puntero activo, el anterior catálogo raw y los registros del usuario; no se sirven
  carpetas parciales. Las carpetas temporales se limpian tras cada intento.
- Se comprueban cobertura inferior al 85 %, caída superior al 20 %, métricas no finitas,
  clubes incompletos y exclusión de actualizaciones simultáneas. El bloqueo se libera
  aunque falle un proceso y no depende de borrar manualmente un archivo de bloqueo.
- La comparación sigue el ID de jugador y separa altas/bajas de perfiles, cambios de
  equipo en las plantillas, cambios de identidad publicada y variaciones numéricas.
  Una consulta idéntica informa cero cambios; al cambiar temporada no inventa traspasos.
- Las pruebas de interfaz cubren el botón en una instalación sin datos, recuperación
  de errores, recarga automática y conservación de referencia/proyectos. Un cambio
  externo de la consulta activa durante la descarga impide sobrescribir ese estado.
- En la primera prueba real, el proceso local sin permiso de red devolvió WinError 10013.
  La interfaz informó el fallo y conservó la consulta del 29/10/2026 a las 18:50 (Madrid),
  con sus 441 perfiles.
- La segunda prueba real, con acceso de red autorizado, terminó correctamente el
  **29/10/2026 a las 20:28 (Madrid)**. Consultó 20 clubes y estadísticas de 471 jugadores;
  validó y activó **441 perfiles** y excluyó 105 registros por cobertura o calidad.
  Snapshot: `20261029T192735329144Z`, consulta iniciada a las 20:27 (Madrid).
  El informe comparado con la consulta de las 18:50 contiene **cero altas, bajas,
  cambios de equipo, variaciones estadísticas y ajustes de identidad**.
- Nueva comprobación real el **03/11/2026**: consulta a las **15:44 (Madrid)** y
  activación a las **15:45**. Se consultaron 486 jugadores de los 20 clubes y se
  activaron **447 perfiles**, con 112 registros excluidos por cobertura o calidad.
  Snapshot: `20261103T144404526587Z`. El resumen registra **6 altas de perfiles,
  0 bajas, 0 cambios de equipo, 289 perfiles con estadísticas modificadas y
  1 ajuste de identidad** respecto a la consulta del 29/10 a las 20:27.
- La descarga real con variaciones detectó un booleano NumPy no serializable en el
  indicador de corrección; se convierte a booleano nativo. Una prueba de dos
  actualizaciones completas comprueba aumentos y reducciones de minutos, activación
  y lectura del informe JSON persistido. La suite completa vuelve a pasar.
- En el navegador, Andrei Ratiu sigue seleccionado tras la actualización y pasa
  de 540 minutos/6 partidos a 630 minutos/7 partidos. El resumen se distribuye en
  dos columnas en la vista estrecha. Captura: [ScoutFit 0.8](../assets/scoutfit-v08-update.jpg).

El resumen refleja los datos publicados por ESPN: las altas/bajas de perfiles no
son confirmaciones de fichajes y los cambios de tasas pueden incluir correcciones.
El botón hace una consulta nueva al pulsarlo; no configura una actualización periódica.

## Versión 0.7 · Biografías y proyectos de scouting · 29/10/2026

- **144 pruebas superadas**: 128 anteriores y 16 nuevas para biografías, proyectos,
  persistencia y recuperación de búsquedas. Ruff y el lock de dependencias comprobados.
- La biografía conserva el snapshot estadístico activo: 441 perfiles, 434 con edad
  y nacionalidad, 428 con altura, 441 con escudo y 13 con fotografía publicada.
  No hay registros de pie dominante y se indica como no disponible.
- La edad se calcula al día de la consulta, sin usar la fecha actual del navegador.
  Pedri: 23 años en la consulta del 29/10/2026, nacimiento 25/11/2002 y altura convertida
  de 69 pulgadas a aproximadamente 175 cm. La nacionalidad se muestra tal como figura
  en la fuente. No se inventa una fotografía si no consta en la plantilla.
- Se comprueban conversión y ausencias, URLs de imágenes del proveedor, SHA-256
  de catálogo/plantilla y aislamiento de equipo/temporada. Un fallo biográfico no
  elimina al jugador del ranking ni rellena métricas con valores inventados.
- Se prueban proyectos separados, escritura atómica, límites de nombres/notas,
  candidatos sin duplicados, conservación de estado tras traspasos y recuperación
  de configuraciones por parecido/objetivo. Configuraciones incompatibles se rechazan
  antes de modificar el archivo o el estado de los controles.
- Pruebas de interfaz: creación, notas y estados conservados en una nueva sesión,
  recuperación exacta de filtros/pesos y recuperación de objetivos desde el otro modo.
- Los proyectos reales del usuario no se usan como datos de prueba. Cada prueba de
  persistencia se ejecuta en una carpeta temporal; no se insertan seguimientos ficticios.
- Verificación en navegador de la ficha de Andrei Ratiu: fotografía del proveedor
  cargada correctamente, escudo, edad en consulta, nacionalidad y altura. Gestor de
  proyectos abierto con formulario de creación; no se crea un proyecto ficticio en
  el espacio del usuario para obtener una captura.

## Versión 0.6 · Objetivos y filtros de candidatos · 29/10/2026

- **128 pruebas superadas**, incluyendo 21 nuevas para cálculo por objetivo,
  filtros, intersección/exclusión de clubes, intervalos inclusivos y acciones de interfaz.
- El cálculo por objetivo no requiere un ID de referencia ni crea perfiles sintéticos.
  La brecha se reconstruye a partir de los déficits e importancias por métrica.
  Se comprueban el cumplimiento estricto, los objetivos inválidos, datos incompletos,
  población de percentiles y aislamiento por posición/temporada/fuente.
- Los filtros se aplican antes del top-k, sin alterar distancias ni percentiles
  de quienes permanecen. Las pruebas cubren referencia fuera del intervalo de
  candidatos, clubes simultáneamente incluidos/excluidos y filtros sin resultados.
- Los dos modos conservan filtros compartidos. Se prueban personalización de
  objetivos, limpieza de intervalos inválidos, favoritos con identidades reales,
  comparación entre candidatos y transición de un candidato a referencia.
- La sensibilidad técnica respeta los filtros. La evaluación manual mantiene su
  benchmark equilibrado de liga y la interfaz distingue ambos ámbitos.
- Comprobación en navegador con datos reales: objetivo «Recuperación y distribución»,
  posición Mediocentro y mínimo de muestra 450. Los percentiles se calculan sobre
  67 jugadores. Al incluir solo Real Betis y limitar a 650 minutos, aparecen cuatro
  candidatos y Marc Roca conserva la brecha **4,388161 pp** que tenía sin esos filtros.
  Al limpiar filtros vuelve el ranking general y se conserva la inspección si sigue válida.
- Se mantienen la consulta real, las plantillas y el histórico del 29/10/2026.
  No se han añadido edades, valoraciones de mercado ni datos deportivos inventados.

La brecha mide déficit frente a mínimos estadísticos, no probabilidad ni calidad
del fichaje. Un objetivo puede tener varios candidatos con brecha cero. El mínimo
de muestra determina la población; el intervalo de candidatos se aplica además.

## Versión 0.5 · Diseño y exploración visual · 29/10/2026

- **107 pruebas superadas**: 96 anteriores y 11 nuevas para la proyección ponderada,
  aislamiento de grupos, pesos inválidos, grupos pequeños/sin variación y acciones de interfaz.
- El mapa ajusta PCA sobre la posición elegible completa. Cambiar los candidatos
  resaltados no altera las coordenadas. Se comprueban distancias exactas en el caso
  de dos métricas, pesos cero y separación por fuente/temporada/posición.
- Los accesos directos abren la comparativa con el candidato correcto. Usar un
  jugador del mapa como referencia limpia los filtros dependientes y vuelve al ranking.
- La interfaz detiene el ranking si todos los pesos son cero y permite restablecerlos
  sin perder el jugador seleccionado. El radar permite alternar a diferencias estandarizadas.
- Verificación en el navegador local: búsqueda de Pedri, comparativa rápida con
  Pablo Fornals y cambio a Alberto Moleiro desde el mapa. En el mapa de los 67
  mediocentros elegibles, los dos ejes conservan aproximadamente el 51,1 % de variación
  con pesos equilibrados. Esta proporción no mide precisión futbolística.
- Se conservan la consulta real del 29/10/2026, el histórico y los archivos del usuario.
  Esta versión añade presentación y exploración; no vuelve a descargar estadísticas.

## Versión 0.4 · Evaluación, comparativa y evolución · 29/10/2026

- **96 pruebas superadas**, incluyendo 23 pruebas de percentiles, informes,
  favoritos, importación, métricas de ranking, coseno e históricos.
- Pruebas de interfaz para tres jugadores, persistencia de favoritos entre
  sesiones, edición de notas, formularios de revisión, sensibilidad y evolución.
- Comparativa real de Pedri, Pablo Fornals e Iván Martín exportada a HTML autónomo
  en `reports/scoutfit-pedri.html`, con fuente, consulta, percentiles y límites.
- Plantilla real de 20 referencias con relevancias vacías. El informe de evaluación
  permanece en `pending_review`: no hay valoraciones humanas inventadas.
- Prueba técnica para Pedri: Jaccard medio **0,90** en 30 perturbaciones de pesos,
  semilla 7, mínimo 450 minutos, otros equipos y mismo perfil inferido. Es una
  medida de estabilidad ante ese experimento, no precisión futbolística.
- Dos consultas reales: 28 y 29 de octubre de 2026. Pedri mantiene 711 minutos y
  85,063291 pases/90 en ambas; el tramo se marca «Sin minutos nuevos» y no se
  fabrica una tasa por partido.
- La consulta activa del 29/10 conserva 441 perfiles y los 20 equipos. Las notas,
  favoritos, revisiones y reportes locales se excluyen de Git.

La fuente es de agregados de temporada: no se han añadido estadísticas por partido
ni ajustes por posesión sin contar con los datos necesarios.

## Versión 0.3 · Buscador y perfiles inferidos

Verificación sobre el mismo snapshot, sin volver a descargar estadísticas:

- **68 pruebas pasan**; formato e importaciones comprobados con Ruff.
- Controles de equipo, posición, nombre y jugador en el contenido principal.
- Regresiones de selección: cambiar de jugador, prioridades, número de
  candidatos, filtros dependientes y recarga mantiene una selección válida.
- Búsqueda literal por nombre, insensible a mayúsculas, tildes y orden de palabras;
  búsqueda sin resultados y borrado no pierden la referencia anterior si sigue válida.
- Verificación en navegador a 390 × 844: búsqueda de Mbappé sin tilde, cambio de prioridad,
  borrado de búsqueda y apertura/cierre del selector conservan la referencia.
- Nueve perfiles de estilo. Los 192 jugadores con al menos 450 minutos reciben
  etiqueta en este snapshot; los demás conservan su posición sin inferencia.
- Se comprueban arquetipos, empates/sin señal, grupos insuficientes, aislamiento
  por liga/temporada, valores no finitos y reproducibilidad al reordenar filas.
- Filtrar por perfil mantiene las distancias del grupo amplio y no introduce
  candidatos de otros estilos si se vacía la lista.

Las etiquetas son reglas estadísticas orientativas, no posiciones tácticas
validadas. La prueba de los cálculos no sustituye una evaluación futbolística.
Consulta [las reglas del modelo](PERFILES_INFERIDOS.md).

## Pruebas de software de la versión 0.2

- **46 pruebas pasan**, sin consultas de red.
- Se verifican cálculo /90, porcentajes, temporada, jugador y género, rechazo
  de estadísticas ausentes y conservación del conjunto anterior si falla una carga.
- Las contribuciones explicadas suman el cuadrado de la distancia.
- La interfaz se prueba con datos actuales e históricos, filtros de equipo,
  cambios de prioridad y conjuntos vacíos.
- Ruff comprueba importaciones y formato.
- Se ejecutó además Streamlit AppTest con los datos reales: carga inicial,
  selección de Real Madrid y prioridad de creación, sin excepciones.
- Se comprobó la pestaña abierta: muestra LaLiga masculina 2026/27, consulta,
  referencia Pedri y candidatos calculados con ESPN.

## Ejemplo reproducible

```powershell
uv run scoutfit recommend "espn:250465:83" --min-minutes 450 --top-k 5
```

Referencia: Pedri. Pesos equilibrados, otros equipos y al menos 450 minutos.

| Candidato | Equipo de plantilla | Distancia |
| --- | --- | --- |
| Pablo Fornals | Real Betis | 1.133187 |
| Daniel Lorenzo | Málaga | 1.164321 |
| Marc Roca | Real Betis | 1.202467 |
| Marcos Llorente | Atlético Madrid | 1.214726 |
| Iván Martín | Racing Santander | 1.235565 |

Los resultados describen este snapshot y cambiarán al actualizar la temporada.
Este ejemplo verifica el flujo; no valida la adecuación de esos posibles fichajes.
Falta evaluar relevancia futbolística y estabilidad del ranking.

La [validación de la versión histórica de StatsBomb](VALIDACION_STATSBOMB.md)
se conserva separada del conjunto activo.
