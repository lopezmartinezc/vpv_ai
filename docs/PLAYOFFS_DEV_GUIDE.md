# Playoffs — Guía de desarrollo: añadir un formato nuevo

Para implementadores.
- Uso operativo: [PLAYOFFS_RUNBOOK.md](PLAYOFFS_RUNBOOK.md).
- API HTTP: [PLAYOFFS_API.md](PLAYOFFS_API.md).
- Reglas: [PLAYOFFS_DESIGN.md](PLAYOFFS_DESIGN.md).

---

## Arquitectura

El motor de playoffs vive en `backend/src/features/competitions/` y nunca importa un formato concreto. Busca en `FORMAT_REGISTRY` la implementación que indique `competitions.config.format_id`:

```
features/competitions/
├── formats/
│   ├── __init__.py              # FORMAT_REGISTRY: dict[str, FormatPlugin]
│   ├── base.py                  # FormatPlugin (ABC)
│   ├── balanced_ko4.py          # Mundial: 6 jornadas balanced + KO top-4
│   ├── liga_berger_ko8.py       # todos contra todos + KO top-8, final de 1 jornada
│   └── liga_berger_ko8_bo3.py   # Liga 2026-27: igual, con final al mejor de 3
├── scheduler.py                 # calendarios puros (Berger, balanced)
├── ko_bracket.py                # cuadros KO (seed_classic_bracket, chain_winners)
├── ko_series.py                 # final al mejor de 3 (resolve_best_of_three)
├── service.py                   # MOTOR — no conoce formatos concretos
├── repository.py
├── router.py
└── schemas.py
```

Un formato nuevo suele ser **un fichero y una línea en el registro**. Si necesita algo que el motor no hace, se añade como opción del motor que el formato activa, igual que la final a 3 o el enfrentamiento directo.

---

## Formatos existentes

| `format_id` | Liga | KO | Final | Desempate de la liga |
|---|---|---|---|---|
| `balanced_ko4` | 6 jornadas, 4 cruces cada uno (13 participantes exactos) | top-4: semis + final | 1 jornada | puntos → diferencia |
| `liga_berger_ko8` | Berger completo: `N` jornadas si impar, `N-1` si par | top-8: cuartos + semis + final | 1 jornada | puntos → diferencia |
| `liga_berger_ko8_bo3` | Berger completo | top-8: cuartos + semis + final | 3 jornadas, al mejor de 3 | puntos → directo → diferencia |

---

## El contrato `FormatPlugin`

`backend/src/features/competitions/formats/base.py`:

```python
class FormatPlugin(ABC):
    format_id: str = ""
    display_name: str = ""
    #: Jornadas de la final: 1, o 3 para una final al mejor de 3 (ko_series).
    final_legs: int = 1
    #: Si un empate a puntos en la liga se resuelve primero por enfrentamiento
    #: directo y después por diferencia (si no, directamente por diferencia).
    head_to_head_tiebreak: bool = False

    @abstractmethod
    def required_rounds_regular(self, n_participants: int) -> int: ...

    @abstractmethod
    def required_rounds_ko(self) -> int: ...

    @abstractmethod
    def generate_regular_phase(
        self, participants: list[int], matchday_ids: list[int], seed: int
    ) -> list[MatchupDraft]: ...

    @abstractmethod
    def generate_ko_phase(
        self, standings: list[StandingEntry], matchday_ids: list[int], n_regular_rounds: int
    ) -> list[MatchupDraft]: ...

    @abstractmethod
    def resolve_ko_tie(
        self, participant_a_id: int, participant_b_id: int, standings_snapshot: list[StandingEntry]
    ) -> int: ...

    def standings_groups(self) -> list[str]:
        return ["overall"]
```

**Parámetros que no son evidentes:**
- **`required_rounds_regular(n_participants)`:** recibe el nº de participantes activos. Un todos contra todos depende de él; los demás pueden devolver una constante.
- **`generate_ko_phase(..., n_regular_rounds)`:** los cruces de eliminatoria llevan `round_number` consecutivos tras la liga. Tras 11 jornadas, los cuartos son la ronda 12.
- **`final_legs > 1`:**
  - El formato genera `final_legs` cruces con `round_label="final"`, uno por jornada y todos con los mismos alimentadores (las dos semis).
  - El motor resuelve la serie con `ko_series.resolve_best_of_three`.
  - Hoy solo está implementado 3.
- **`head_to_head_tiebreak = True`:** activa en `_compute_standings` la minitabla entre los empatados a puntos, antes de la diferencia.

---

## Piezas reutilizables

| Función | Qué hace |
|---|---|
| `scheduler.generate_berger(participants)` | Todos contra todos clásico. Con N impar añade un descanso (`None` en la ronda). Devuelve `list[list[Pair \| None]]`. |
| `scheduler.generate_balanced_schedule(participants, n_rounds, games_per_player, seed)` | Calendario en el que todos juegan exactamente `games_per_player`. Solo para `(13, 4, 6)`. |
| `ko_bracket.seed_classic_bracket(top_n_pids, round_label, round_number)` | Primera ronda KO. Top-4: `[1-4, 2-3]`. Top-8: `[1-8, 4-5, 2-7, 3-6]`; el orden importa porque la ronda siguiente empareja 0-1 y 2-3. |
| `ko_bracket.chain_winners(feeders, round_number, round_label, feeder_offset)` | Siguiente ronda: el ganador del slot 0 contra el del 1, el del 2 contra el del 3… |
| `ko_series.resolve_best_of_three(legs, better_seed)` | Estado de una final a 3: jornadas ganadas, resultado de cada jornada y campeón. |
| `LigaBergerKo8Plugin.top8(standings)` | Los 8 que pasan, o `ValueError` si hay un empate sin resolver en el corte. |

---

## Tutorial: `groups67_ko8`

Ejemplo de un formato con **dos grupos (6 y 7) y cuartos cruzados entre grupos**.

### 1. Crear el fichero

`backend/src/features/competitions/formats/groups67_ko8.py`:

```python
"""Format: 2 grupos (6+7) + KO cruzado top-4 de cada grupo."""

from __future__ import annotations

import random

from src.features.competitions.formats.base import FormatPlugin
from src.features.competitions.ko_bracket import KoSlot, chain_winners
from src.features.competitions.scheduler import generate_berger
from src.features.competitions.schemas import MatchupDraft, StandingEntry


class Groups67Ko8Plugin(FormatPlugin):
    format_id = "groups67_ko8"
    display_name = "2 grupos (6+7) + KO cruzado top-8"

    def required_rounds_regular(self, n_participants: int) -> int:
        # Grupo A (6): 5 rondas. Grupo B (7): primeras 5 de 7. En paralelo.
        return 5

    def required_rounds_ko(self) -> int:
        return 3  # cuartos + semis + final

    def generate_regular_phase(
        self, participants: list[int], matchday_ids: list[int], seed: int
    ) -> list[MatchupDraft]:
        if len(participants) != 13:
            raise ValueError(f"groups67_ko8 espera 13 participantes, recibidos {len(participants)}")
        shuffled = participants[:]
        random.Random(seed).shuffle(shuffled)

        drafts: list[MatchupDraft] = []
        for label, group in (("A", shuffled[:6]), ("B", shuffled[6:])):
            for r_idx, rnd in enumerate(generate_berger(group)[:5]):
                for pair in rnd:
                    if pair is None:  # descanso
                        continue
                    drafts.append(
                        MatchupDraft(
                            phase="regular",
                            round_number=r_idx + 1,
                            matchday_id=matchday_ids[r_idx],
                            participant_a_id=pair.a,
                            participant_b_id=pair.b,
                            group_label=label,
                        )
                    )
        return drafts

    def generate_ko_phase(
        self, standings: list[StandingEntry], matchday_ids: list[int], n_regular_rounds: int
    ) -> list[MatchupDraft]:
        top_a = [s.participant_id for s in standings if s.group_label == "A"][:4]
        top_b = [s.participant_id for s in standings if s.group_label == "B"][:4]
        quarter = n_regular_rounds + 1
        # Cuartos cruzados: A1-B4, A2-B3, A3-B2, A4-B1.
        quarters = [
            KoSlot(quarter, "quarter", top_a[i], top_b[3 - i]) for i in range(4)
        ]
        semis = chain_winners(quarters, round_number=quarter + 1, round_label="semi", feeder_offset=0)
        final = chain_winners(semis, round_number=quarter + 2, round_label="final", feeder_offset=4)

        return [
            MatchupDraft(
                phase="ko",
                round_number=slot.round_number,
                matchday_id=matchday_ids[slot.round_number - quarter],
                participant_a_id=slot.a_pid,
                participant_b_id=slot.b_pid,
                feeder_a_index=slot.feeder_a,
                feeder_b_index=slot.feeder_b,
                round_label=slot.round_label,
            )
            for slot in quarters + semis + final
        ]

    def resolve_ko_tie(
        self, participant_a_id: int, participant_b_id: int, standings_snapshot: list[StandingEntry]
    ) -> int:
        # Gana el mejor rank de la clasificación congelada al empezar el KO.
        ranks = {s.participant_id: s.rank for s in standings_snapshot}
        return min((participant_a_id, participant_b_id), key=lambda pid: ranks.get(pid, 10_000))

    def standings_groups(self) -> list[str]:
        return ["A", "B"]
```

### 2. Registrarlo

`backend/src/features/competitions/formats/__init__.py`:

```python
FORMAT_REGISTRY: dict[str, FormatPlugin] = {
    "balanced_ko4": BalancedKo4Plugin(),
    "liga_berger_ko8": LigaBergerKo8Plugin(),
    "liga_berger_ko8_bo3": LigaBergerKo8Bo3Plugin(),
    "groups67_ko8": Groups67Ko8Plugin(),  # NUEVO
}
```

### 3. Comprobar que el admin lo ofrece

```bash
curl -sf "https://new.ligavpv.com/api/competitions/formats?season_id=<ID>" | jq
```

El desplegable de `/admin/temporadas` lo ofrece sin tocar la UI.

### 4. Tests

Van en `backend/tests/features/competitions/`. Toma como modelo los existentes:

| Fichero | Qué cubre |
|---|---|
| `test_formats.py` | La forma de un formato sin BD: cruces, descansos, cuadro y alimentadores |
| `test_ko_series.py` | Reglas puras de la final al mejor de 3 |
| `test_liga_playoff.py` | Un playoff completo por el motor con BD (fixture `liga`): calendario, recálculo retroactivo, arranque automático del KO, final y desempates con cruces hechos a mano (`standings_for`) |

Como mínimo, un formato nuevo debería probar:
- nº de cruces y de descansos;
- que cada pareja se enfrenta lo que toca;
- los emparejamientos del KO;
- los alimentadores;
- que rechaza un nº de participantes o de jornadas incorrecto.

---

## Reglas para todo formato

1. **`format_id`** en snake_case ASCII y único en el registro.
2. **`generate_regular_phase` debe ser determinista** dados `(participants, matchday_ids, seed)`. Si el algoritmo reintenta, que use la `seed`.
3. **Sin acceso a BD:** el formato solo devuelve `list[MatchupDraft]` y el motor persiste.
4. **Validar las entradas** y lanzar `ValueError` con un mensaje claro. El motor lo convierte en `BusinessRuleError`, y el admin ve un `422` con ese mensaje.
5. **`feeder_a_index` / `feeder_b_index`** son **índices en la lista de drafts** que devuelves; el motor los traduce a ids reales.
6. **`resolve_ko_tie`** solo se llama en un empate de eliminatoria, salvo en las jornadas de una final con `final_legs > 1`, que resuelve la serie. Recibe la clasificación congelada en `config.regular_standings_snapshot`.
7. **`standings_groups()`** decide cuántas tablas se muestran.

---

## Lo que ya está centralizado (no lo repitas en el formato)

| Funcionalidad | Dónde |
|---|---|
| Persistir cruces con alimentadores | `service._persist_drafts` |
| Clasificación y desempates (incluido el directo si el formato lo pide) | `service._compute_standings`, `service._head_to_head` |
| Recalcular resultados tras puntuar una jornada | `service.recalculate_matchups_for_matchday` |
| Recalcular jornadas ya puntuadas al generar la liga | `service.start_regular_phase` |
| Arrancar el KO al acabar la liga | `service._maybe_auto_start_ko` |
| Serie de una final a varias jornadas | `service._final_series` → `ko_series.resolve_best_of_three` |
| Marcar el playoff como terminado | `service._maybe_mark_completed` |
| Listar formatos con las jornadas de cada temporada | `service.list_formats`, `GET /formats?season_id=` |

---

## Cuándo el frontend sí necesita cambios

`/playoffs` y la tarjeta del admin se adaptan a 1 o N grupos y a finales de una o tres jornadas. Hay que tocarlos si:

- **Hay etiquetas de ronda nuevas** (`play-in`, `tercer-puesto`…). Van en dos sitios:
  - `KoView` en `frontend/src/app/playoffs/page.tsx`;
  - `ROUND_LABELS` en `frontend/src/components/dashboard/personal-playoff.tsx`, el duelo de la portada.
- **La final no es al mejor de 3.** `FinalSeriesView` y `seriesLine` (`frontend/src/components/playoffs/final-series.tsx`) pintan lo que llega en `final_series`. Otras reglas de serie necesitan su texto.
- **El cuadro no es estándar.** Considera reutilizar `CompactMatchCard` de `/bracket`.

---

## Checklist antes de hacer merge

- [ ] mypy y ruff limpios.
- [ ] `format_id` único y descriptivo; `display_name` en español.
- [ ] `generate_regular_phase` valida participantes y jornadas.
- [ ] Los cruces caen dentro de los `matchday_ids` recibidos.
- [ ] `generate_ko_phase` cubre todas las rondas y usa bien los alimentadores.
- [ ] `resolve_ko_tie` tiene una política clara y documentada.
- [ ] Registrado en `FORMAT_REGISTRY`.
- [ ] Tests en `backend/tests/features/competitions/`, y una mutación por cada regla nueva.
- [ ] `docs/PLAYOFFS_*.md` actualizados: formato, reglas y jornadas.
