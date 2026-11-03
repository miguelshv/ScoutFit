# Demo pública · ScoutFit 0.11

URL: [ScoutFit · Cuaderno de scouting](https://scoutfit-laliga-demo.berry-clock-7103.chatgpt.site).

Publicada en Sites el 03/11/2026. Versión de alojamiento: 2, con la identidad editorial
de cuaderno de scouting elegida por el usuario. La aplicación completa
continúa en Streamlit; la demo implementa el modo Por parecido en HTML, CSS y JavaScript
para funcionar en el navegador sin un servidor Python ni cuentas de usuario.

## Contenido y alcance

- Consulta `20261103T144404526587Z`, 447 perfiles de los 20 clubes, temporada 2026/27.
- Búsqueda por nombre sin tildes y selección por equipo, mínimos 450/600/900 minutos.
- Prioridades equilibrada, creación y defensa; mismo perfil inferido opcional.
- Candidatos de otros clubes, filtro por club, comparativa y CSV de métricas/percentiles.
- Explicación de contribuciones a la distancia euclídea y estado real de evaluación.
- Sin actualización en directo, modo por objetivo, proyectos, notas o cuentas.

La fuente y la fecha aparecen en pantalla. No se muestran métricas de calidad
futbolística hasta contar con valoraciones humanas suficientes.

## Exportar y verificar una nueva consulta

Desde la raíz del proyecto, después de actualizar y validar los datos:

```powershell
uv run python -m scoutfit.demo_export --output ..\scoutfit-demo-public
node demo/check-parity.mjs ..\scoutfit-demo-public
```

El exportador copia solo cuatro recursos de `demo/site/` y genera `data.json` y
`evidence.json` en `dist/`. Las columnas de jugadores están en una lista permitida;
no se copian carpetas locales, biografías, respuestas originales, claves ni revisiones.
Los campos de evaluación públicos empiezan sin valoraciones; publicar resultados
humanos posteriores requiere preparar y revisar expresamente otro informe agregado.

`parity.json`, fuera de `dist/`, contiene resultados calculados por Python para
contrastar JavaScript. En la primera publicación se verificaron 1.119 búsquedas.
El exportador se detiene si `dist/` contiene archivos ajenos a la demo.

## Publicación reproducible

La carpeta de alojamiento es `../scoutfit-demo-public`, separada del repositorio
Streamlit. Conserva el identificador de Sites en su `.openai/hosting.json`; reutilízalo
para futuras versiones. El directorio estático declarado es `dist`.

Tras revisar los archivos y la paridad, el flujo Sites prepara el repositorio fuente,
guarda un commit, lo sube y empaqueta los activos de ese mismo commit. Después guarda
una versión y la despliega. Las credenciales temporales se pasan por stdin, nunca
se guardan en el código. La identidad de la publicación está en `demo/DEPLOYMENT.json`.

Una actualización de Streamlit no publica automáticamente otra versión de la demo.
Es necesario exportar la consulta nueva, comprobar la paridad y desplegarla.

## Qué compartir en el portafolio

Usa el enlace público junto al repositorio de código y explica el alcance del baseline.
Un recorrido de un minuto: buscar Pedri → cambiar prioridad → abrir un candidato →
comparar percentiles → mostrar la explicación y el estado de evaluación humana.
