# Contribuir a ScoutFit

## Preparar el entorno

Instala Python 3.11 o 3.12 y uv. Desde la raíz:

```sh
uv sync --locked --extra dev --python 3.12
uv run streamlit run app.py
```

No se necesita descargar datos para ejecutar las pruebas. Para trabajar con la
fuente real, consulta [el inicio rápido](README.md#ejecutar-en-tu-equipo).

## Antes de una entrega

```sh
uv run --locked --extra dev python scripts/check.py --package
git status --short
git diff --check
```

El primer comando ejecuta las mismas comprobaciones configuradas en CI:
lockfile, lint, formato, pruebas y una instalación limpia del wheel.
Detiene la ejecución al primer fallo. Para el ciclo habitual puedes omitir
`--package`; la instalación de dependencias y la construcción pueden necesitar red.

Para aplicar el formato:

```sh
uv run ruff format .
```

Si cambias dependencias, actualiza `uv.lock` con `uv lock` y revisa el cambio.
Si cambias el motor de búsqueda de la demo, sigue también la comprobación de
paridad descrita en [DEMO_PUBLICA.md](docs/DEMO_PUBLICA.md).

## Qué incluir en un cambio

Explica el problema, el comportamiento final y cómo lo has comprobado. Añade
pruebas cuando cambies reglas, contratos de datos o corrijas un fallo reproducible.
Para ajustes pequeños de documentación o estilo no hacen falta pruebas que
repliquen la implementación. Actualiza la guía afectada y el historial si cambia
una función pública.

Usa fixtures sintéticos y rutas temporales en los tests. No añadas tus archivos
de `data/`, cuadernos, informes generados, credenciales ni respuestas originales
de los proveedores. Revisa las capturas seleccionadas antes de incluirlas en
`assets/`: son documentación pública.

## Revisar una publicación en GitHub

Comprueba el diff que vas a subir, la licencia y las atribuciones. No anuncies
la CI como superada hasta que haya terminado en el repositorio remoto. La matriz
está preparada, pero necesita un push a GitHub para ejecutarse allí.

Descripción sugerida del repositorio:

> Cuaderno de scouting de LaLiga masculina: datos reproducibles, similitud explicable y seguimiento con criterio humano.

Temas sugeridos: `python`, `football-analytics`, `streamlit`, `data-engineering`,
`scikit-learn`, `explainable-ai`. El proyecto usa un baseline estadístico y reglas;
no lo presentes como un modelo supervisado de éxito de fichajes.

Referencias del flujo de entrega: [uv en GitHub Actions](https://docs.astral.sh/uv/guides/integration/github/)
y [construcción de paquetes](https://docs.astral.sh/uv/guides/package/).
