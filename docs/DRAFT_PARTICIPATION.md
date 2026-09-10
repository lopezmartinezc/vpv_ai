# Participación esperada — dos modelos y cómo volver atrás

La **participación** es la fracción de jornadas restantes que esperamos que un
jugador dispute. Multiplica directamente a `proj_rest_points`, que es lo que
ordena **Prioridad**: cambiarla reordena el tablero entero.

Por eso NO se ha sustituido nada. Hay un interruptor, el valor por defecto es
el comportamiento de siempre, y volver atrás es un clic.

---

## Los dos modelos

### `historico` (por defecto)

```
participación = partidos jugados / jornadas de esa temporada
```

Sobre la temporada de referencia: la actual si su muestra es suficiente
(`min_games`), si no la anterior. Es lo que el tablero ha hecho siempre.

**Su punto ciego**: cuenta apariciones, no minutos. El que sale diez minutos
cada semana aparece como titular indiscutible.

### `mixto`

```
participación = (1-w) x histórico + w x señal de esta temporada
w             = jornadas / (jornadas + 2,69)
señal         = 0,69 x cuota de minutos en su puesto + 0,31 x tasa de aparición
```

- **Cuota de minutos**: sus minutos sobre `jornadas que ha jugado su club en
  ese puesto x 90`. El grupo es **club + posición**, así que un equipo con un
  partido aplazado se juzga con las jornadas que ha jugado de verdad, no se lee
  como que todos sus jugadores se han perdido uno.
- **El peso `w`** está calibrado para que en la **jornada 5** —donde se hizo el
  backtest y donde cae el draft de Liga— la temporada actual pese 0,65 y el
  histórico 0,35. Sigue subiendo después: en el draft de invierno la temporada
  en curso es sencillamente mejor evidencia.
- **En pretemporada (0 jornadas) `w = 0`**: `mixto` e `historico` dan lo mismo.
  El 0,65 es el peso medido en la J5, no una constante.
- **Sin histórico**, se usa solo la señal actual (encogerla hacia un prior de
  cero enterraría a todo recién llegado).

**Acierto medido en temporadas de holdout, prediciendo la participación del
resto de temporada: 0,655 → 0,730.**

---

## Cómo se cambia

Interruptor **Participación: Histórico | Mixto**, visible en:

- **Estadísticas → Draft** (preparación)
- **Draft en vivo** (sobre la leyenda de admin)

La elección se guarda en `localStorage` (`vpv.participationModel`), la comparten
las dos pantallas y **también la usa el chat del draft**, para que el asistente
cite exactamente la Prioridad que tienes en la tabla delante.

## Cómo se vuelve atrás

Pulsar **Histórico**. No hay migración, ni columna nueva en base de datos, ni
despliegue que revertir:

- El parámetro por defecto de `get_draft_values` es `historico`.
- Si el interruptor está en histórico, la petición ni siquiera lleva
  `?participacion=` — es byte a byte la misma que antes de que esto existiera.
- Un test (`test_the_default_is_the_old_behaviour`) fija que el tablero por
  defecto produce exactamente la misma participación y la misma Prioridad que
  pedirle `historico` explícitamente.

## API

| Endpoint | Parámetro |
|---|---|
| `GET /stats/{season_id}/players/draft-value` | `?participacion=historico\|mixto` |
| `GET /drafts/{draft_id}/players/stats` | `?participacion=historico\|mixto` |
| `POST /draft-assistant/...` | campo `participacion` en el body |

Omitirlo = `historico`.

## Código

- `backend/src/features/stats/participation.py` — los dos modelos, aislados y
  sin dependencias de base de datos.
- `backend/tests/features/stats/test_participation_model.py` — el modelo.
- `backend/tests/features/stats/test_draft_value_participation_switch.py` — el
  interruptor sobre el tablero real.
- `frontend/src/lib/participation-model.ts` — store compartido + query.
