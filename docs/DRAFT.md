# Draft — Guía operativa

## Auto-pick wishlist

Permite a un participante dejar una lista priorizada de jugadores para que el sistema haga su pick automáticamente cuando le toque el turno y no esté conectado al draft en vivo.

### Cómo funciona

- Cada participante puede mantener UNA wishlist por draft (`draft_wishlists` UNIQUE `(draft_id, participant_id)`).
- La lista es persistente durante todo el draft. No hay que reconfigurar entre turnos.
- Toggle `enabled` para pausarla sin perder la lista (p. ej., entras al draft a pickear manualmente esta ronda).
- Máximo **50 jugadores** por lista.

### Cuándo dispara

Inmediatamente después de cualquier pick que deje el turno en manos de un participante con wishlist activa. El hook está en [backend/src/features/drafts/service.py](backend/src/features/drafts/service.py) `_maybe_auto_pick` y se invoca:

1. Al final de `add_pick(origin="manual")` — un pick humano (o admin) puede encadenar uno o más auto-picks si los siguientes en turno tienen wishlist.
2. Al final de `delete_pick` — si el admin borra un pick y el participante que vuelve a tener turno tiene wishlist, dispara.

El bucle es iterativo (no recursivo) con tope `MAX_AUTO_PICK_CHAIN = 30`.

### Resolución de candidato

`WishlistRepository.get_next_available_player(draft_id, participant_id)` devuelve el `player_id` con menor `priority` que cumple:

- `players.is_available = TRUE` (no fue cortado del oficial).
- NO aparece en `draft_picks` para ese `draft_id`.

Si no hay candidato (lista vacía, todo pickeado, o `enabled=false`), el turno queda esperando manual.

### Concurrencia

- El draft es secuencial por construcción (un solo turno activo en cada momento).
- El `UNIQUE (draft_id, player_id)` en `draft_picks` protege la ventana entre SELECT y INSERT. Si dos coroutines llegaran al mismo `player_id` a la vez (caso teórico), la perdedora obtiene `BusinessRuleError` y el bucle reintenta con el siguiente candidato.
- No se requiere lock distribuido.

### Visibilidad

- **Participante**: ve sólo su propia wishlist en `/drafts/live/{id}` bajo el `<details>` "Mi auto-pick".
- **Admin / `Perm.DRAFT`**: ve todas las wishlists en `/drafts/gestionar` bajo "Wishlists (auto-pick)" (read-only, audit).

### Origen de pick

La columna `draft_picks.origin` (`'manual' | 'auto'`) distingue picks. Se propaga en:

- Response REST de `POST /drafts/{id}/picks`.
- Payload WebSocket de `pick_added` (campo `pick.origin`).
- UI: el participante recibe un toast cuando su propio auto-pick se ejecuta.

### Endpoints

| Método | Path | Auth | Descripción |
|---|---|---|---|
| GET | `/drafts/{draft_id}/wishlist` | participante del draft | Mi wishlist con `is_already_picked` calculado. |
| PUT | `/drafts/{draft_id}/wishlist` | participante del draft | Reemplaza la wishlist con `{enabled, player_ids: [...]}`. |
| POST | `/drafts/{draft_id}/wishlist/toggle` | participante del draft | Activa/pausa sin tocar la lista. |
| GET | `/drafts/admin/{draft_id}/wishlists` | admin o `Perm.DRAFT` | Vista agregada de todas las wishlists. |

### Migraciones

- `2026_06_04_add_draft_wishlists.sql` — tablas `draft_wishlists` y `draft_wishlist_players` + índices.
- `2026_06_04_add_draft_picks_origin.sql` — columna `draft_picks.origin VARCHAR(10) NOT NULL DEFAULT 'manual'`.

### Edge cases verificados

| Caso | Comportamiento |
|---|---|
| Wishlist vacía | `_maybe_auto_pick` retorna; turno queda manual. |
| Todos los jugadores ya pickeados | Mismo que el caso anterior. |
| Jugador en wishlist marcado `is_available=false` (lesión, fuera del Mundial) | El query lo excluye con `JOIN players ON is_available = TRUE`. |
| Cadena de N participantes con wishlist | El loop resuelve hasta agotar o llegar a `MAX_AUTO_PICK_CHAIN`. |
| Admin pickea por un participante con wishlist | Manual gana; el siguiente turno corre el auto-pick si aplica. |
| Cancelar pick → vuelve el turno | `delete_pick` invoca `_maybe_auto_pick`. |
| Dos consecutivos con el mismo `priority=0` | El primero recibe el jugador (UNIQUE); el segundo recibe su `priority=1`. |

### Pruebas E2E sugeridas

1. Configurar wishlist con 5 jugadores; cerrar la pestaña; pedir a otro participante que pickee al "anterior" → ver pick automático en "Últimos picks" con tag implícito en el payload WS (`pick.origin === 'auto'`).
2. Borrar el último pick desde `/drafts/gestionar` cuando el siguiente turno corresponde a un participante con wishlist → ver que se dispara auto-pick.
3. PUT con 51 entradas → 422; con duplicados → 422; con un `player_id` que no existe en la temporada → 422 con detalle.
