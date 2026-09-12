from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from src.core.config import settings
from src.core.rate_limit import limiter
from src.shared.dependencies import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["backup"])

# Ad-hoc snapshot tables — `<table>_snap_<YYYYMMDD_HHMMSS>` — are manual safety
# copies left behind by past migrations and re-syncs. They hold nothing the real
# tables do not, and they are not part of the schema.
#
# They must be excluded rather than merely skipped: pg_dump takes an ACCESS SHARE
# lock on every table it dumps, in a single LOCK TABLE statement. One snapshot
# created by another role (psql as `postgres`, say) is therefore enough to fail
# the *whole* backup with "permiso denegado a la tabla ...". Leaving them out
# also keeps the download from carrying a duplicate copy of player_stats.
SNAPSHOT_TABLES = "*_snap_[0-9]*"


@router.post("/admin/download")
@limiter.limit("3/hour")
async def download_backup(
    request: Request,
    _admin: dict = Depends(get_current_admin),
) -> StreamingResponse:
    """Run pg_dump and stream the result as a downloadable .sql file."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"ligavpv_{timestamp}.sql"

    process = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h",
        settings.pg_host,
        "-p",
        str(settings.pg_port),
        "-U",
        settings.pg_user,
        "-d",
        settings.pg_database,
        "--no-password",
        "--clean",
        "--if-exists",
        f"--exclude-table={SNAPSHOT_TABLES}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"PGPASSWORD": settings.pg_password, "PATH": "/usr/bin:/usr/local/bin"},
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        logger.error("pg_dump failed: %s", error_msg)
        from fastapi.responses import JSONResponse

        return JSONResponse(  # type: ignore[return-value]
            status_code=500,
            content={"message": f"Backup failed: {error_msg}"},
        )

    logger.info("Backup generated: %s (%d bytes)", filename, len(stdout))

    return StreamingResponse(
        iter([stdout]),
        media_type="application/sql",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
