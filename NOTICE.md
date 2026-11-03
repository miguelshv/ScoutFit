# Fuentes de datos y atribución

El código de ScoutFit se distribuye bajo MIT. Esa licencia no se aplica a datos,
logotipos ni marcas de terceros. ScoutFit es un proyecto independiente.

## ESPN · LaLiga masculina actual

Fuente: [ESPN LaLiga](https://www.espn.com/soccer/league/_/name/esp.1).
Se consultan sus servicios JSON públicos para las plantillas y estadísticas
por jugador, liga y temporada. Las URLs exactas, fechas y hashes se guardan
con cada descarga. No se utiliza un contrato de API con estabilidad garantizada.
Los archivos obtenidos y las tablas derivadas se excluyen del repositorio de código
de ScoutFit. La demo pública muestra una selección de estadísticas numéricas derivadas
y su atribución, con fecha de consulta; no publica respuestas JSON originales,
fotografías ni logotipos de ESPN. No se aplica una licencia propia a los datos o marcas.

## StatsBomb · Conjunto histórico opcional

Fuente: [StatsBomb Open Data](https://github.com/hudl/open-data).
Consulta sus [condiciones](https://github.com/hudl/open-data/blob/master/LICENSE.pdf)
y [requisitos de atribución](https://github.com/hudl/open-data#terms--conditions).
El logotipo del modo histórico procede del directorio `img` del repositorio oficial.

Los datos de ambas fuentes se procesan por separado, con sus identificadores
y definiciones. No se atribuyen a una fuente métricas calculadas con la otra.
