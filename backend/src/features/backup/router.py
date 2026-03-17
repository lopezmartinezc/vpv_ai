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
