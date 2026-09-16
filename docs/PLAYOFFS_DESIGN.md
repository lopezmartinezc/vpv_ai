# Playoffs — Diseño y estado

> **Nombre (16/09/2026):** en la Liga, los playoffs se llaman **DAVID Cup**
> (DAVID Cup Apertura, DAVID Cup Clausura), en memoria de David Silva. Las
> competiciones siguen llamándose «Apertura» y «Clausura» en la base de datos;
> el nombre visible sale de `frontend/src/lib/playoff-name.ts` y, para el chat,
> de `backend/src/shared/playoff_name.py`. Para renombrarla se cambian esas dos
> constantes. Los torneos siguen diciendo «Playoff».

> **Estado (15/09/2026):** en producción con tres formatos.
> - La **Liga 2026-27** usa `liga_berger_ko8_bo3` para la Apertura y la Clausura.
> - El **Mundial 2026** usó `balanced_ko4`.
>
> El motor admite formatos como piezas: uno nuevo es un fichero en
> [`backend/src/features/competitions/formats/`](../backend/src/features/competitions/formats/)
> registrado en `FORMAT_REGISTRY`.

Otros documentos:
- [PLAYOFFS_RUNBOOK.md](PLAYOFFS_RUNBOOK.md): operación paso a paso (crear, generar, problemas).
- [PLAYOFFS_API.md](PLAYOFFS_API.md): endpoints y esquemas.
- [PLAYOFFS_DEV_GUIDE.md](PLAYOFFS_DEV_GUIDE.md): cómo añadir un formato.

---

## Qué es un playoff VPV

No es una clasificación acumulada. Es una **liguilla de cruces directos entre participantes**: en cada jornada VPV, cada cruce compara los puntos VPV de los dos en esa jornada. Tras la liguilla, los mejores juegan **eliminatorias**.

- **Liga:** 2 playoffs por temporada, **Apertura** y **Clausura**, distinguidos por `name`.
- **Torneo** (Mundial, Eurocopa): 1 playoff.

## Formatos

| `format_id` | Para | Liguilla | Eliminatorias | Final |
|---|---|---|---|---|
| `liga_berger_ko8_bo3` | **Liga 2026-27** | Todos contra todos: `N` jornadas si N es impar (cada jornada descansa uno), `N-1` si es par | Top-8: cuartos y semis | **3 jornadas, al mejor de 3** |
| `liga_berger_ko8` | Liga con final de una jornada | Igual | Top-8: cuartos y semis | 1 jornada |
| `balanced_ko4` | Mundial (13 participantes exactos) | 6 jornadas, 4 cruces cada uno (5, 5, 5, 5, 3, 3) | Top-4: semis | 1 jornada |

## Reglas de la Liga 2026-27 (`liga_berger_ko8_bo3`, 11 participantes)

| Fase | Regla |
|---|---|
| **Liguilla** | 11 jornadas con 5 cruces; cada participante juega 10 y descansa 1. Victoria 3, empate 1, derrota 0; el descanso da 0 y no cuenta en la diferencia. |
| **Clasificación** | Puntos. A igualdad de puntos: **1)** enfrentamiento directo (entre dos, su cruce; entre tres o más, una minitabla con los cruces entre ellos, a 3 la victoria y 1 el empate); **2)** diferencia acumulada (puntos a favor − en contra), que es lo que decide si empataron su cruce. Si aun así siguen igualados, comparten puesto y las eliminatorias no arrancan hasta resolverlo. |
| **Cuartos** (1 jornada) | 1-8, 4-5, 2-7, 3-6. Empate → pasa el mejor clasificado de la liguilla. |
| **Semis** (1 jornada) | Ganador 1-8 contra ganador 4-5; ganador 2-7 contra ganador 3-6. Mismo desempate. |
| **Final** (3 jornadas) | Gana quien gane 2. Si alguien gana las dos primeras, la tercera no se disputa. Una jornada empatada la gana quien tenga mejor **diferencia en las otras dos jornadas de la final**, así que un empate siempre lleva la final a la tercera. Si también hay igualdad ahí, gana el mejor clasificado de la liguilla. |

**Ejemplos de la final (A contra B):**
- **A gana la 1.ª por 3 y B la 2.ª por 10; la 3.ª acaba en empate.** La decide la diferencia de la 1.ª y la 2.ª: B va +7, así que se lleva la 3.ª y gana 2-1.
- **A gana la 1.ª y la 2.ª es empate.** Se espera a la 3.ª. Si la gana A, campeón. Si la gana B, la 2.ª la decide la diferencia de la 1.ª y la 3.ª.
- **Las tres jornadas empatadas:** campeón el mejor clasificado.

**Calendario:**

| Playoff | Liguilla | Cuartos | Semis | Final |
|---|---|---|---|---|
| Apertura | J6–J16 | J17 | J18 | J19–J21 |
| Clausura | J22–J32 | J33 | J34 | J35–J37 |

La J38 queda libre.

## Reglas de los otros formatos

- **Clasificación:** puntos → diferencia acumulada, y nada más. Se acordó con Oscar para el Mundial 2026: como no se juega todos contra todos, la diferencia resuelve directamente. `liga_berger_ko8` sigue la misma regla.
- **Empate en eliminatoria, final incluida:** pasa el mejor clasificado de la liguilla.

---

## Cómo funciona el motor

- **Formato como pieza:** `competitions.config.format_id` elige la clase de `FORMAT_REGISTRY`. El motor (`service.py`) no conoce formatos concretos. Un formato activa lo que necesita con atributos:
  - `final_legs = 3`: final a varias jornadas;
  - `head_to_head_tiebreak = True`: enfrentamiento directo antes que la diferencia.
- **Ciclo de vida:** `pending` → `regular` → `ko` → `completed`.
  - **Crear:** `pending`.
  - **Generar liguilla (`start-regular`):** sorteo aleatorio del orden (`config.seed`) y todos los cruces, con su jornada, de una vez. Si se pasan las jornadas KO, se guardan en `config.planned_ko_matchday_numbers`.
  - **Eliminatorias:** arrancan solas al resolverse el último cruce de liguilla, o a mano con `start-ko`. La clasificación queda congelada en `config.regular_standings_snapshot` para los desempates de la eliminatoria.
  - **`completed`:** cuando hay campeón.
- **Resultados:** cada vez que se agrega una jornada, `ScoreAggregator.aggregate_matchday` llama a `CompetitionService.recalculate_matchups_for_matchday`. Este:
  - pone marcador y ganador a los cruces de esa jornada;
  - escribe los ganadores en los cruces siguientes, que tienen alimentadores;
  - arranca las eliminatorias y cierra el playoff cuando toca.
- **Retroactivo:** al generar la liguilla se recalculan las jornadas del rango ya puntuadas. Un playoff creado tarde no pierde jornadas.
- **Final a 3:**
  - Son tres cruces con `round_label="final"`, uno por jornada y alimentados por las dos semis.
  - La serie la resuelve `ko_series.resolve_best_of_three`. Se calcula en cada lectura y se expone como `final_series` en `GET /competitions/{id}/matchups`; no se guarda aparte.
  - Una jornada empatada de la final deja `winner_participant_id = NULL` en su fila.
- **Clasificación:** `_compute_standings` la calcula en cada lectura desde los cruces resueltos; no se guarda.

## Dónde se ve

- **Admin, `/admin/temporadas`:** una tarjeta por playoff.
  - **Temporada de torneo:** «Playoffs».
  - **Temporada de Liga:** «Playoff Apertura» y «Playoff Clausura», con `liga_berger_ko8_bo3` por defecto.
  - **Jornadas propuestas:** la tarjeta pide los formatos con `?season_id=` para calcularlas con los participantes reales. La Clausura (`order={1}`) propone empezar donde acaba la final de la Apertura.
- **Pública, `/playoffs`:**
  - selector entre los playoffs de la temporada; abre el que está en juego, si no el último terminado;
  - pestañas Clasificación, Calendario y Eliminatorias;
  - la final a 3 se muestra como serie: jornadas ganadas, cada jornada, «No se disputa» y campeón.
- **Menú lateral:** «Playoffs» aparece en Liga y en torneo (`frontend/src/lib/competition-scope.ts`).
- **Portada:** el duelo de playoff de cada participante en la jornada (`components/dashboard/personal-playoff.tsx`). En la final dice «Jornada 2 de 3 · vas 1-0».

## Piezas reutilizables

- [`scheduler.py`](../backend/src/features/competitions/scheduler.py):
  - `generate_berger()`: todos contra todos, con descanso si N es impar; lo usan los dos formatos de Liga;
  - `generate_balanced_schedule()`: 13 participantes, 4 cruces en 6 jornadas.
- [`ko_bracket.py`](../backend/src/features/competitions/ko_bracket.py):
  - `seed_classic_bracket()`: 1-N, 2-(N-1)…, en el orden que mantiene separados a los mejores;
  - `chain_winners()`: la ronda siguiente, con alimentadores.
- [`ko_series.py`](../backend/src/features/competitions/ko_series.py):
  - `resolve_best_of_three()`: la final al mejor de 3.

## Lo que no está hecho (del diseño original)

- **Premios económicos del playoff:** no hay `payment_type='playoff_prize'` ni `season_payments.competition_id`.
- **Palmarés de ganadores de playoff.**
- **Ida y vuelta configurable por ronda, y `top_n` configurable:** el tamaño del cuadro lo fija el formato.
- **Forzar a mano el orden** de un empate que ningún desempate resuelve. Hoy el KO no arranca y hay que decidirlo fuera; ver el runbook.
- **Aviso al cambiar `counts`:** si una jornada o partido cambia de «cuenta» después, basta con reagregar la jornada (runbook, «Forzar el recálculo»). Nada avisa de que hace falta.

## Historia

- **Junio de 2026, v1:** motor de formatos como piezas, `balanced_ko4` para el Mundial y la tabla `competition_matchups` (migración `2026_06_08_add_competition_matchups.sql`).
- **v1.1:** `liga_berger_ko8`, varios playoffs por temporada (Apertura y Clausura), y las eliminatorias arrancan solas.
- **Septiembre de 2026:**
  - `liga_berger_ko8_bo3`, con la final al mejor de 3 (#164);
  - pantallas con el selector de playoff y la serie final (#165);
  - desempate de la liguilla puntos → directo → diferencia;
  - los rechazos de un formato dan un 422 con el motivo, no un 500;
  - «Playoffs» visible en el menú de Liga.
