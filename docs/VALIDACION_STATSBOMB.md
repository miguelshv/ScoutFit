> Validación histórica. Para reproducir este ejemplo, activa primero StatsBomb con fetch/build --source statsbomb.

# Validación de la primera versión

Ejecutada el 28 de octubre de 2026, con Python 3.12 y las dependencias de `uv.lock`.

## Datos reales

Fuente: [StatsBomb Open Data](https://github.com/hudl/open-data), revisión
`4b73468fc5b0f1950f9f66fada70ad3a4f9327cb`.

![StatsBomb](../assets/statsbomb.png)

| Comprobación | Resultado |
| --- | --- |
| Competición | FA Women's Super League 2023/24 |
| Partidos descargados | 132 |
| Partidos utilizados | 124 |
| Partidos excluidos por intervalos inválidos/solapados | 8 |
| Equipos | 12 |
| Perfiles jugador/equipo | 299 |
| Perfiles de campo con al menos 450 minutos | 194 |
| Identificadores de perfil | Únicos |
| Minutos | Todos positivos |
| Diez métricas | Sin valores ausentes |
| Proporción de minutos en rol predominante | Entre 0 y 1 |

Partidos excluidos: `3912599`, `3913114`, `3913124`, `3913136`, `3913146`,
`3913152`, `3913150`, `3913171`. El detalle por jugador y motivo se genera en
`data/processed/quality_report.json`. Se descarta el partido entero para que
ninguno de sus conteos se acumule sobre minutos inconsistentes. La exclusión
reduce la cobertura y puede afectar al ranking: no se ha medido ese sesgo.

## Pruebas de software

- 32 pruebas pasan: transformaciones de eventos, geometría, minutos,
  sustituciones, descuentos, prórroga, exclusión de tandas, integridad de
  archivos, descarte de partidos y restricciones del recomendador.
- Se comprueba que las contribuciones explicadas suman el cuadrado de la distancia.
- La interfaz se prueba sin datos, con candidatos, con cambio de prioridad y
  con un mínimo de minutos que deja el conjunto vacío.
- Ruff comprueba formato e importaciones. Las pruebas sintéticas no usan red.
- Se ejecuta además Streamlit AppTest con el conjunto real: carga inicial y
  cambio a prioridad de progresión sin excepciones.

## Ejemplo reproducible

```powershell
uv run scoutfit recommend "15616:968" --min-minutes 450 --top-k 5
```

Referencia: Kim Little. Prioridad equilibrada y candidatos de otros equipos.

| Candidato | Equipo | Distancia |
| --- | --- | --- |
| Jordan Nobbs | Aston Villa W | 0.724132 |
| Jill Roord | Manchester City WFC | 0.952956 |
| Ingrid Filippa Angeldal | Manchester City WFC | 0.988792 |
| Yuka Momiki | Leicester City WFC | 1.052138 |
| Marie Therese Höbinger | Liverpool WFC | 1.172970 |

Este ejemplo demuestra que el flujo funciona y permite inspeccionar sus
resultados. No valida que estos fichajes fueran adecuados. Falta evaluar la
relevancia futbolística y la estabilidad al remuestrear partidos.
