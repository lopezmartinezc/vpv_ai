"""Operation registry — every runnable production operation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

BASE_PATH = os.environ.get("VPV_ROOT", "/opt/vpv")


@dataclass(frozen=True)
class Parameter:
    name: str  # "--matchdays" or "season_id" (positional)
    label: str
    param_type: str  # "int", "str", "csv_int"
    required: bool = True
    default: str = ""


@dataclass(frozen=True)
class Operation:
    id: str
    category: str
    name: str
    description: str
    command_template: str  # "{python} migrate.py {args}"
    connections: list[str] = field(default_factory=list)
    destructive: bool = False
    dry_run_flag: str | None = None
    venv: str = ""  # relative to BASE_PATH, e.g. "migration/.venv"
    cwd: str = ""  # relative to BASE_PATH, e.g. "migration/scripts"
    env_extra: dict[str, str] = field(default_factory=dict)
    parameters: list[Parameter] = field(default_factory=list)
    shell: bool = False  # True for raw shell commands (systemctl, curl, etc.)

    @property
    def python(self) -> str:
        if not self.venv:
            return "python3"
        return os.path.join(BASE_PATH, self.venv, "bin", "python")

    @property
    def abs_cwd(self) -> str:
        if not self.cwd:
            return BASE_PATH
        return os.path.join(BASE_PATH, self.cwd)

    @property
    def resolved_env(self) -> dict[str, str]:
        env = dict(os.environ)
        for k, v in self.env_extra.items():
            env[k] = v.replace("{base}", BASE_PATH)
        return env


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
CAT_MIGRATION = "Migración"
CAT_BACKEND = "Backend Scripts"
CAT_SCRAPING = "Scraping"
CAT_SERVICES = "Servicios"
CAT_DATABASE = "Database"

# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------
OPERATIONS: list[Operation] = [
    # --- Migración ---
    Operation(
        id="migration.full",
        category=CAT_MIGRATION,
        name="Migración completa",
        description="MySQL → PostgreSQL (15 pasos). Destruye y recrea el schema.",
        command_template="{python} migrate.py {args}",
        connections=["mysql", "pg"],
        destructive=True,
        dry_run_flag="--dry-run",
        venv="migration/.venv",
        cwd="migration/scripts",
        parameters=[
            Parameter("--step", "Empezar desde paso", "int", required=False, default="0"),
        ],
    ),
    Operation(
        id="migration.incremental_sync",
        category=CAT_MIGRATION,
        name="Sync incremental",
        description="Sincroniza jornadas desde MySQL sin destruir datos.",
        command_template="{python} incremental_sync.py {args}",
        connections=["mysql", "pg"],
        destructive=True,
        dry_run_flag="--dry-run",
        venv="migration/.venv",
        cwd="migration/scripts",
        parameters=[
            Parameter("--matchdays", "Jornadas (ej: 25,26,27)", "csv_int", required=False),
        ],
    ),
    Operation(
        id="migration.draft_economy",
        category=CAT_MIGRATION,
        name="Draft + Economy seed",
        description="Genera draft picks y transacciones para temporada 8.",
        command_template="{python} generate_draft_economy_seed.py {args}",
        connections=["mysql", "pg"],
        destructive=True,
        venv="migration/.venv",
        cwd="migration/scripts",
    ),
    # --- Backend Scripts ---
    Operation(
        id="backend.weekly_payments",
        category=CAT_BACKEND,
        name="Backfill pagos semanales",
        description="Genera transacciones de pago semanal por posición.",
        command_template="{python} -m scripts.backfill_weekly_payments {args}",
        connections=["pg"],
        destructive=True,
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
        parameters=[
            Parameter("--season-id", "Season ID", "int", required=False, default="8"),
        ],
    ),
    Operation(
        id="backend.fix_winter_drops",
        category=CAT_BACKEND,
        name="Fix winter draft drops",
        description="Libera jugadores dropeados en draft de invierno.",
        command_template="{python} -m scripts.fix_winter_draft_drops {args}",
        connections=["mysql", "pg"],
        destructive=True,
        dry_run_flag="--apply",  # special: dry-run is default, --apply is destructive
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
        parameters=[
            Parameter("--season", "Temporada (ej: 2025-2026)", "str", required=False),
        ],
    ),
    Operation(
        id="backend.ownership_log",
        category=CAT_BACKEND,
        name="Populate ownership log",
        description="Historial de propiedad de jugadores (todas las temporadas).",
        command_template="{python} -m scripts.populate_ownership_log {args}",
        connections=["mysql", "pg"],
        destructive=True,
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
    ),
    # --- Scraping ---
    Operation(
        id="scraping.matchday",
        category=CAT_SCRAPING,
        name="Scrape jornada",
        description="Scrape stats de todos los partidos de una jornada.",
        command_template="{python} -m src.features.scraping.cli scrape-matchday {args}",
        connections=["pg"],
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
        parameters=[
            Parameter("season_id", "Season ID", "int"),
            Parameter("matchday_number", "Jornada (1-38)", "int"),
        ],
    ),
    Operation(
        id="scraping.match",
        category=CAT_SCRAPING,
        name="Scrape partido",
        description="Scrape stats de un partido específico.",
        command_template="{python} -m src.features.scraping.cli scrape-match {args}",
        connections=["pg"],
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
        parameters=[
            Parameter("season_id", "Season ID", "int"),
            Parameter("matchday_number", "Jornada (1-38)", "int"),
            Parameter("match_id", "Match ID", "int"),
        ],
    ),
    Operation(
        id="scraping.check_updates",
        category=CAT_SCRAPING,
        name="Check updates",
        description="Comprueba CRC de la homepage para detectar cambios.",
        command_template="{python} -m src.features.scraping.cli check-updates",
        connections=["pg"],
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
    ),
    Operation(
        id="scraping.calendar",
        category=CAT_SCRAPING,
        name="Update calendar",
        description="Actualiza resultados y fechas desde el calendario de La Liga.",
        command_template="{python} -m src.features.scraping.cli update-calendar {args}",
        connections=["pg"],
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
        parameters=[
            Parameter("season_id", "Season ID", "int"),
        ],
    ),
    Operation(
        id="scraping.photos",
        category=CAT_SCRAPING,
        name="Download photos",
        description="Descarga fotos de jugadores en WebP 200x200.",
        command_template="{python} -m src.features.scraping.cli download-photos {args}",
        connections=["pg"],
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
        parameters=[
            Parameter("season_id", "Season ID", "int"),
        ],
    ),
    Operation(
        id="scraping.current",
        category=CAT_SCRAPING,
        name="Scrape current",
        description="Scrape la jornada actual de la temporada activa.",
        command_template="{python} -m src.features.scraping.cli scrape-current",
        connections=["pg"],
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
    ),
    # --- Servicios ---
    Operation(
        id="services.alembic",
        category=CAT_SERVICES,
        name="Alembic upgrade head",
        description="Ejecuta migraciones de esquema pendientes.",
        command_template="{python} -m alembic upgrade head",
        connections=["pg"],
        destructive=True,
        venv="backend/.venv",
        cwd="backend",
        env_extra={"PYTHONPATH": "{base}/backend"},
    ),
    Operation(
        id="services.restart_backend",
        category=CAT_SERVICES,
        name="Restart backend",
        description="systemctl restart vpv-backend",
        command_template="sudo systemctl restart vpv-backend",
        destructive=True,
        shell=True,
    ),
    Operation(
        id="services.restart_frontend",
        category=CAT_SERVICES,
        name="Restart frontend",
        description="pm2 restart vpv-frontend",
        command_template="pm2 restart vpv-frontend",
        destructive=True,
        shell=True,
    ),
    Operation(
        id="services.restart_all",
        category=CAT_SERVICES,
        name="Restart all",
        description="Reinicia backend (systemctl) y frontend (pm2).",
        command_template="sudo systemctl restart vpv-backend && echo 'Backend reiniciado' && pm2 restart vpv-frontend && echo 'Frontend reiniciado'",
        destructive=True,
        shell=True,
    ),
    Operation(
        id="services.build_frontend",
        category=CAT_SERVICES,
        name="Build + restart frontend",
        description="npm run build en frontend y reinicia con pm2.",
        command_template="cd /opt/vpv/frontend && npm run build && pm2 restart vpv-frontend",
        destructive=True,
        shell=True,
    ),
    Operation(
        id="services.deploy",
        category=CAT_SERVICES,
        name="Deploy (pull + build + restart)",
        description="git pull, build frontend, restart backend y frontend.",
        command_template="cd /opt/vpv && git pull && cd frontend && npm run build && pm2 restart vpv-frontend && sudo systemctl restart vpv-backend && echo 'Deploy completado'",
        destructive=True,
        shell=True,
    ),
    # --- Database ---
    Operation(
        id="db.health_check",
        category=CAT_DATABASE,
        name="Health check",
        description="Verifica que backend y frontend responden.",
        command_template='echo "Backend:" && curl -sf http://localhost:8000/api/health && echo && echo "Frontend:" && curl -sf -o /dev/null -w "HTTP %{http_code}" http://localhost:3000 && echo',
        shell=True,
    ),
    Operation(
        id="db.backup",
        category=CAT_DATABASE,
        name="Backup database",
        description="pg_dump de la base de datos ligavpv.",
        command_template="pg_dump -U vpv -h 127.0.0.1 ligavpv | gzip > /opt/vpv/backups/ligavpv_$(date +%Y%m%d_%H%M%S).sql.gz",
        connections=["pg"],
        shell=True,
    ),
]


def get_categories() -> list[str]:
    """Return unique categories in order of first appearance."""
    seen: set[str] = set()
    cats: list[str] = []
    for op in OPERATIONS:
        if op.category not in seen:
            seen.add(op.category)
            cats.append(op.category)
    return cats


def get_operations_by_category(category: str) -> list[Operation]:
    return [op for op in OPERATIONS if op.category == category]
