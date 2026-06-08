# Playoffs — Guía de desarrollo: añadir un formato nuevo

Esta guía es para implementadores. Para uso operativo ver [PLAYOFFS_RUNBOOK.md](PLAYOFFS_RUNBOOK.md), para la API HTTP ver [PLAYOFFS_API.md](PLAYOFFS_API.md).

---

## Arquitectura pluggable en 30 segundos

El motor de playoffs vive en `features/competitions/` y nunca importa un formato concreto. En su lugar consulta `FORMAT_REGISTRY` para obtener la implementación que toque según `competitions.config.format_id`:

```
features/competitions/
├── formats/
│   ├── __init__.py             # FORMAT_REGISTRY: dict[str, FormatPlugin]
│   ├── base.py                 # FormatPlugin (ABC)
│   ├── balanced_ko4.py         # v1: 6 RR balanced + KO top-4
│   └── (tu formato nuevo aquí)
├── scheduler.py                # algoritmos puros (Berger, balanced) reutilizables
├── ko_bracket.py               # helpers KO (seed_classic_bracket, chain_winners)
├── service.py                  # ENGINE — no toca formatos directamente
├── repository.py
├── router.py
└── schemas.py
```

Añadir un formato es **1 fichero + 1 línea en el registry**. Cero cambios en service, repository, router, schemas, esquema BD o frontend.

---

## El contrato `FormatPlugin`

`backend/src/features/competitions/formats/base.py`:

```python
class FormatPlugin(ABC):
    format_id: str = ""
    display_name: str = ""

    @abstractmethod
    def required_rounds_regular(self) -> int: ...

    @abstractmethod
    def required_rounds_ko(self) -> int: ...

    @abstractmethod
    def generate_regular_phase(
        self,
        participants: list[int],
        matchday_ids: list[int],
        seed: int,
    ) -> list[MatchupDraft]: ...

    @abstractmethod
    def generate_ko_phase(
        self,
        standings: list[StandingEntry],
        matchday_ids: list[int],
    ) -> list[MatchupDraft]: ...

    @abstractmethod
    def resolve_ko_tie(
        self,
        participant_a_id: int,
        participant_b_id: int,
        standings_snapshot: list[StandingEntry],
    ) -> int: ...

    def standings_groups(self) -> list[str]:
        return ["overall"]
```

---

## Reutilizables (¡úsalos!)

### `scheduler.generate_balanced_schedule(participants, n_rounds, games_per_player, seed)`

Calendario simétrico: todos juegan exactamente `games_per_player`. Sólo soporta `(13, 4, 6)` ahora — para otras shapes añade tu función al lado.

### `scheduler.generate_berger(participants)`

Round-robin clásico de N (impar añade `BYE`). Devuelve `list[list[Pair | None]]`.

### `ko_bracket.seed_classic_bracket(top_n_pids, round_label, round_number)`

Genera el primer corte de un KO con cruces 1-vs-N, 2-vs-N-1, etc. Soporta `top_n ∈ {4, 8}`.

### `ko_bracket.chain_winners(feeders, round_number, round_label, feeder_offset)`

Encadena 2 slots a un único matchup siguiente vía `feeder_a_index` / `feeder_b_index`.

---

## Tutorial: añadir `groups67_ko8`

Ejemplo guiado para crear el formato "2 grupos 6+7 con KO top-8 cruzado".

### 1. Crear el fichero

`backend/src/features/competitions/formats/groups67_ko8.py`:

```python
"""Format: 2 grupos (6+7) + KO cruzado top-4 de cada grupo."""

from __future__ import annotations

import random

from src.features.competitions.formats.base import FormatPlugin
from src.features.competitions.ko_bracket import chain_winners, KoSlot
from src.features.competitions.scheduler import generate_berger
from src.features.competitions.schemas import MatchupDraft, StandingEntry


class Groups67Ko8Plugin(FormatPlugin):
    format_id = "groups67_ko8"
    display_name = "2 grupos (6+7) + KO cruzado top-8"

    def required_rounds_regular(self) -> int:
        # Grupo A (6): 5 rondas full. Grupo B (7): 5 rondas truncado.
        # En paralelo: 5 jornadas.
        return 5

    def required_rounds_ko(self) -> int:
        # Cuartos + semis + final = 3 jornadas.
        return 3

    def generate_regular_phase(
        self,
        participants: list[int],
        matchday_ids: list[int],
        seed: int,
    ) -> list[MatchupDraft]:
        if len(participants) != 13:
            raise ValueError(
                f"groups67_ko8 espera 13 participantes, recibidos {len(participants)}"
            )
        rng = random.Random(seed)
        shuffled = participants[:]
        rng.shuffle(shuffled)

        group_a = shuffled[:6]
        group_b = shuffled[6:]

        drafts: list[MatchupDraft] = []

        # Grupo A: Berger full (5 rondas).
        rounds_a = generate_berger(group_a)[:5]
        for r_idx, rnd in enumerate(rounds_a):
            for pair in rnd:
                if pair is None:
                    continue
                drafts.append(
                    MatchupDraft(
                        phase="regular",
                        round_number=r_idx + 1,
                        matchday_id=matchday_ids[r_idx],
                        participant_a_id=pair.a,
                        participant_b_id=pair.b,
                        group_label="A",
                    )
                )

        # Grupo B: Berger truncado (de 7 → primeras 5 rondas).
        rounds_b = generate_berger(group_b)[:5]
        for r_idx, rnd in enumerate(rounds_b):
            for pair in rnd:
                if pair is None:
                    continue
                drafts.append(
                    MatchupDraft(
                        phase="regular",
                        round_number=r_idx + 1,
                        matchday_id=matchday_ids[r_idx],
                        participant_a_id=pair.a,
                        participant_b_id=pair.b,
                        group_label="B",
                    )
                )

        return drafts

    def generate_ko_phase(
        self,
        standings: list[StandingEntry],
        matchday_ids: list[int],
    ) -> list[MatchupDraft]:
        # Standings vienen ya ordenadas globalmente — separa por grupo.
        top_a = [s for s in standings if s.group_label == "A"][:4]
        top_b = [s for s in standings if s.group_label == "B"][:4]

        # Cuartos cruzados: A1-B4, A2-B3, A3-B2, A4-B1.
        quarters = [
            KoSlot(round_number=6, round_label="quarter",
                   a_pid=top_a[0].participant_id, b_pid=top_b[3].participant_id),
            KoSlot(round_number=6, round_label="quarter",
                   a_pid=top_a[1].participant_id, b_pid=top_b[2].participant_id),
            KoSlot(round_number=6, round_label="quarter",
                   a_pid=top_a[2].participant_id, b_pid=top_b[1].participant_id),
            KoSlot(round_number=6, round_label="quarter",
                   a_pid=top_a[3].participant_id, b_pid=top_b[0].participant_id),
        ]
        semis = chain_winners(quarters, round_number=7, round_label="semi", feeder_offset=0)
        final = chain_winners(semis, round_number=8, round_label="final", feeder_offset=4)

        slots = quarters + semis + final
        drafts: list[MatchupDraft] = []
        for slot in slots:
            md_id = matchday_ids[slot.round_number - 6]
            drafts.append(
                MatchupDraft(
                    phase="ko",
                    round_number=slot.round_number,
                    matchday_id=md_id,
                    participant_a_id=slot.a_pid,
                    participant_b_id=slot.b_pid,
                    feeder_a_index=slot.feeder_a,
                    feeder_b_index=slot.feeder_b,
                    round_label=slot.round_label,
                )
            )
        return drafts

    def resolve_ko_tie(
        self,
        participant_a_id: int,
        participant_b_id: int,
        standings_snapshot: list[StandingEntry],
    ) -> int:
        # Gana el mejor `rank` GLOBAL (considera ambos grupos).
        ranks = {s.participant_id: s.rank for s in standings_snapshot}
        return min(
            (participant_a_id, participant_b_id),
            key=lambda pid: ranks.get(pid, 10_000),
        )

    def standings_groups(self) -> list[str]:
        return ["A", "B"]
```

### 2. Registrar

`backend/src/features/competitions/formats/__init__.py`:

```python
from src.features.competitions.formats.balanced_ko4 import BalancedKo4Plugin
from src.features.competitions.formats.groups67_ko8 import Groups67Ko8Plugin   # NUEVO
from src.features.competitions.formats.base import FormatPlugin

FORMAT_REGISTRY: dict[str, FormatPlugin] = {
    "balanced_ko4": BalancedKo4Plugin(),
    "groups67_ko8": Groups67Ko8Plugin(),                                       # NUEVO
}
```

### 3. Verificar que el frontend lo recoge

```bash
curl -sf https://new.ligavpv.com/api/competitions/formats | jq
# Debe listar ambos formatos.
```

Refresca `/admin/temporadas` → el desplegable de formato ofrece el nuevo automáticamente. **Sin tocar UI alguna.**

### 4. Pruebas unitarias mínimas

Crear `backend/tests/test_groups67_ko8.py`:

```python
from src.features.competitions.formats.groups67_ko8 import Groups67Ko8Plugin

def test_generate_regular_phase_creates_30_cruces():
    plugin = Groups67Ko8Plugin()
    participants = list(range(1, 14))
    matchday_ids = list(range(101, 106))
    drafts = plugin.generate_regular_phase(participants, matchday_ids, seed=42)
    assert len(drafts) == 30                                  # 3×5 + 3×5
    # Cada participante de A juega 5 partidos; cada uno de B juega 4 o 5.
    counts = {}
    for d in drafts:
        counts[d.participant_a_id] = counts.get(d.participant_a_id, 0) + 1
        counts[d.participant_b_id] = counts.get(d.participant_b_id, 0) + 1
    a_counts = sorted(c for pid, c in counts.items() if any(
        d.group_label == "A" and d.participant_a_id == pid for d in drafts
    ))
    assert all(c == 5 for c in a_counts)
```

(En este repo no hay tests todavía — añadir según haga falta.)

---

## Convenciones y reglas que debe cumplir TODO plugin

1. **`format_id`** kebab-case ASCII, único en el registry.
2. **`generate_regular_phase` debe ser determinista** dado `(participants, matchday_ids, seed)`. Si tu algoritmo es greedy con reintentos (como `generate_balanced_schedule`), usa la `seed` para reproducibilidad.
3. **No tocar BD desde el plugin**. Sólo devolver `list[MatchupDraft]`. El motor persiste.
4. **Validar entradas** y lanzar `ValueError` con mensaje claro si no se cumplen. El motor lo convierte en `400 BusinessRuleError`.
5. **`feeder_a_index` / `feeder_b_index`** se refieren al ÍNDICE en la lista de drafts que devuelves. El motor los resuelve a `competition_matchups.id` reales.
6. **`resolve_ko_tie`** se llama sólo en empates KO (score_a == score_b). Recibe el snapshot de standings cacheado en `competitions.config.regular_standings_snapshot`.
7. **`standings_groups()`** decide cuántas tablas se muestran en la UI. Si tu formato tiene grupos, devuelve sus labels (ej. `["A", "B"]`).

---

## Cosas que ya están centralizadas (no las repliques en tu plugin)

| Funcionalidad | Sitio único |
|---|---|
| Persistir matchups (incluyendo feeders) | `service._persist_drafts` |
| Calcular standings con tiebreakers | `service._compute_standings` |
| Recalcular resultados tras scraping | `service.recalculate_matchups_for_matchday` |
| Auto-completar al ganar la final | `service._maybe_mark_completed` |
| Listar formatos | `service.list_formats` |

Si necesitas alterar alguno de estos comportamientos para tu formato, primero discútelo: probablemente sea una extensión del motor, no del plugin.

---

## Cuando el frontend SÍ necesita cambios

La página `/playoffs` y la tarjeta admin son **adaptativas** — soportan formatos con 1 o N grupos automáticamente. Pero hay casos donde un cambio mínimo en frontend ayuda:

- **Nuevas etiquetas KO** (ej. `round_label='play-in'` o `'tercer-puesto'`): añade el caso al objeto de labels en `frontend/src/app/playoffs/page.tsx::KoView`.
- **Visualización custom de bracket**: si tu formato tiene cruces no estándar, considera reusar `CompactMatchCard` de `/bracket`.

---

## Checklist antes de merge

- [ ] Plugin importa sin warnings (mypy + ruff).
- [ ] `format_id` único y descriptivo.
- [ ] `display_name` legible en español.
- [ ] `generate_regular_phase` valida nº de participantes y matchdays.
- [ ] Cruces generados están dentro del `matchday_ids` recibido (no se inventan ids).
- [ ] `generate_ko_phase` cubre todas las rondas necesarias y usa feeders correctamente.
- [ ] `resolve_ko_tie` tiene política clara y documentada.
- [ ] Plugin añadido a `FORMAT_REGISTRY`.
- [ ] Probado end-to-end con season real (o copia): create → start-regular → scrape → start-ko → final.
