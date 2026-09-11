# Participación esperada — dos modelos y cómo volver atrás

La **participación** es la fracción de jornadas restantes que esperamos que un
jugador dispute. Multiplica directamente a `proj_rest_points`, que es lo que
ordena **Prioridad**: cambiarla reordena el tablero entero.

Hay un interruptor. **El valor por defecto es `mixto`**, que ganó el backtest;
`historico` sigue reproduciendo exactamente el tablero anterior y está a un
clic. Medido sobre una temporada real, cambiar de modelo mueve **un tercio del
top-30**, así que no es un ajuste cosmético.

---

## Los dos modelos

### `historico`

```
participación = partidos jugados / jornadas de esa temporada
```

Sobre la temporada de referencia: la actual si su muestra es suficiente
(`min_games`), si no la anterior. Es lo que el tablero ha hecho siempre.

**Su punto ciego**: cuenta apariciones, no minutos. El que sale diez minutos
cada semana aparece como titular indiscutible.

### `mixto` (por defecto)

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

**Medido sobre una temporada real (J1-J5 para predecir, resto como
resultado), 439 jugadores:**

| | Histórico | Mixto |
|---|---|---|
| Todos (439) | error 0,245 · corr 0,392 | **0,232 · 0,464** |
| Drafteables (225) | error 0,213 · corr 0,199 | **0,180 · 0,271** |

Gana en las dos métricas y en los dos cortes, que es lo que le da el puesto de
valor por defecto. La muestra es una sola transición de temporada: es la mejor
evidencia disponible, no una certeza.

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

- `historico` no se ha retirado: es un valor del mismo parámetro.
- Un test (`test_historico_still_reproduces_the_old_board`) fija que pedirlo
  devuelve exactamente lo de siempre — partidos entre jornadas, nada más.
- Otro (`test_the_default_is_mixto`) fija cuál es el valor por defecto, para
  que cambiarlo sea deliberado y no un descuido.

## API

| Endpoint | Parámetro |
|---|---|
| `GET /stats/{season_id}/players/draft-value` | `?participacion=historico\|mixto` |
| `GET /drafts/{draft_id}/players/stats` | `?participacion=historico\|mixto` |
| `POST /draft-assistant/...` | campo `participacion` en el body |

Omitirlo = `mixto`.

## Código

- `backend/src/features/stats/participation.py` — los dos modelos, aislados y
  sin dependencias de base de datos.
- `backend/tests/features/stats/test_participation_model.py` — el modelo.
- `backend/tests/features/stats/test_draft_value_participation_switch.py` — el
  interruptor sobre el tablero real.
- `frontend/src/lib/participation-model.ts` — store compartido + query.

## El tag `Competirá`

Para el jugador que **apenas ha jugado** pero del que esperas que pelee por ser
titular. Es la clase donde el modelo más se equivoca, y está medido: los de una
o dos jornadas se proyectaban en **0,33** de participación y acabaron la
temporada en **0,51**.

Es un tag de **rol**, así que sustituye la suposición de riesgo de banquillo del
modelo (×0,75) — que es exactamente lo que tu criterio contradice — y aplica un
**suelo de participación de 0,55**: por encima del 0,51 real porque etiquetarlo
es apostar por él, y por debajo del 0,65 de un suplente asentado de equipo
grande, porque todavía no se ha ganado el puesto. Suelo, nunca techo: si el
modelo ya dice más, manda el modelo.

El suelo se aplica **solo a Prioridad**. `participation`, `exp_games_remaining`
y `priority_base` siguen siendo la visión del modelo; un tag que los reescribiera
destruiría lo único para lo que sirve la columna Base: ver qué ha cambiado tu
criterio.

**Lo que el tag no puede hacer:** un jugador sin histórico y sin datos de esta
temporada no tiene valor por partido, y la participación multiplica a ese valor.
No hay nada que escalar. Para esos hace falta un **valor manual**; el tag no
inventa puntos de la nada.
