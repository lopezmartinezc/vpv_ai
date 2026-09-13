"""Every route that writes must say who may call it, and say it out loud.

§9 of docs/AUDITORIA_ADMIN.md asks for a matrix per action — actor, context,
preconditions, impact, risk, recovery. The "actor" column is the only one that
protects anything by itself, and it is the only one that can be derived from the
code instead of transcribed by hand, which means it is the only one that cannot
quietly fall out of date.

This is that column. It walks every write route in the application, reads its
gate out of the dependency tree, and fails when one has none — which is how
`/stats/{season_id}/fixtures` reached production readable by every participant
(PR #135), and how it would have been caught the day it was written.

Exceptions are listed here rather than tolerated silently. A route that writes
and is open, or writes and asks only for a login, is a decision someone should
make deliberately and be able to defend; the list is where that defence lives.

Run with `-s` to print the whole inventory.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from src.app import create_app
from src.shared.permissions import Perm

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Open to the world. Each of these either predates authentication by necessity
# or writes nothing at all.
PUBLIC_BY_DESIGN: dict[str, str] = {
    "POST /api/auth/login": "cómo se obtiene un token",
    "POST /api/auth/register": "alta por invitación; la invitación es la credencial",
    "POST /api/tournaments/third-place-assignments": (
        "sin estado: resuelve la tabla del Anexo C del Mundial 2026 y no toca la base. "
        "Es POST sólo porque recibe los grupos en el cuerpo"
    ),
}

# Any logged-in user may call these. Either they act on the caller's own data, or
# the authorisation needs state a dependency cannot see and lives in the service.
AUTHENTICATED_BY_DESIGN: dict[str, str] = {
    "POST /api/auth/refresh": "renueva el token del propio usuario",
    "PUT /api/auth/change-password": "cambia su propia contraseña",
    "POST /api/notifications/subscribe": "su propio dispositivo",
    "POST /api/notifications/unsubscribe": "su propio dispositivo",
    "POST /api/lineups/{season_id}/{matchday_number}": "su propia alineación",
    "PUT /api/tournaments/{season_id}/predictions/me": "sus propias predicciones",
    "PUT /api/drafts/{draft_id}/wishlist": "su propia lista",
    "POST /api/drafts/{draft_id}/wishlist/toggle": "su propia lista",
    "POST /api/drafts/{draft_id}/picks": (
        "el servicio comprueba que es su turno; hace falta el estado del draft"
    ),
    "DELETE /api/drafts/{draft_id}/picks/{pick_number}": (
        "el servicio autoriza: admin o Perm.DRAFT borran cualquiera, un participante "
        "sólo su último pick y si nadie ha elegido después"
    ),
}


def gates(dependant: Dependant) -> Iterator[Callable[..., Any]]:
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from gates(dep)


def gate_of(route: APIRoute) -> str:
    """What the route demands, as a label: a Perm, ADMIN, AUTENTICADO or PÚBLICO."""
    names: set[str] = set()
    perms: set[str] = set()
    for gate in gates(route.dependant):
        name = getattr(gate, "__name__", "")
        names.add(name)
        if name != "checker":
            continue
        # require_perm closes over the Perm tuple it was built with.
        for cell in getattr(gate, "__closure__", None) or ():
            value = cell.cell_contents
            if isinstance(value, tuple):
                perms.update(p.name for p in value if isinstance(p, Perm))
    if perms:
        return "|".join(sorted(perms))
    if "get_current_admin" in names:
        return "ADMIN"
    if "admin_id" in names:  # draft_assistant_v2 resolves the admin itself
        return "ADMIN"
    if "get_current_user" in names:
        return "AUTENTICADO"
    return "PÚBLICO"


def write_routes() -> list[tuple[str, str, APIRoute]]:
    """(label, gate, route) for every write route in the app."""
    out = []
    for route in create_app().routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods & WRITE_METHODS):
            out.append((f"{method} {route.path}", gate_of(route), route))
    assert len(out) > 50, "a route table this small means the walk broke, not that the app shrank"
    return sorted(out)


ROUTES = write_routes()


@pytest.mark.parametrize(
    ("label", "gate"), [(lbl, g) for lbl, g, _ in ROUTES], ids=[lbl for lbl, _, _ in ROUTES]
)
def test_a_write_route_is_never_open(label: str, gate: str) -> None:
    if gate != "PÚBLICO":
        return
    assert label in PUBLIC_BY_DESIGN, (
        f"{label} writes and asks for nothing. If that is deliberate, add it to "
        "PUBLIC_BY_DESIGN with the reason; if not, gate it."
    )


@pytest.mark.parametrize(
    ("label", "gate"), [(lbl, g) for lbl, g, _ in ROUTES], ids=[lbl for lbl, _, _ in ROUTES]
)
def test_a_write_route_open_to_any_user_is_a_deliberate_choice(label: str, gate: str) -> None:
    if gate != "AUTENTICADO":
        return
    assert label in AUTHENTICATED_BY_DESIGN, (
        f"{label} writes and only asks for a login. That is right for a route acting "
        "on the caller's own data, or one whose authorisation needs state and lives in "
        "the service — say which in AUTHENTICATED_BY_DESIGN. Otherwise it needs a Perm."
    )


def test_the_exception_lists_do_not_outlive_their_routes() -> None:
    """An exception left behind after its route is renamed protects nothing and
    hides the next one that takes that name."""
    labels = {lbl for lbl, _, _ in ROUTES}
    stale = (set(PUBLIC_BY_DESIGN) | set(AUTHENTICATED_BY_DESIGN)) - labels
    assert not stale, f"exceptions for routes that no longer exist: {sorted(stale)}"


def test_print_the_inventory() -> None:
    """The §9 'actor' column, always current. `pytest -s` to read it."""
    by_gate: dict[str, list[str]] = {}
    for label, gate, _ in ROUTES:
        by_gate.setdefault(gate, []).append(label)
    print(f"\n\n{len(ROUTES)} rutas de escritura\n" + "=" * 60)
    for gate in sorted(by_gate, key=lambda g: (-len(by_gate[g]), g)):
        print(f"\n{gate}  ({len(by_gate[gate])})")
        for label in by_gate[gate]:
            print(f"    {label}")
