from __future__ import annotations

import asyncio
import logging
import zlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

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

CHUNK_BYTES = 64 * 1024
GZIP_WBITS = 16 + zlib.MAX_WBITS  # zlib's deflate, wrapped in a gzip container
GZIP_LEVEL = 6


async def _start_pg_dump() -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(
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


async def _gzipped(
    process: asyncio.subprocess.Process,
    stderr: asyncio.Task[bytes],
    first: bytes,
    filename: str,
) -> AsyncIterator[bytes]:
    """Compress pg_dump's output as it arrives, never holding the dump in memory.

    A dump that fails partway through must not reach the admin looking whole. We
    cannot take back a response already in flight, so instead the gzip trailer —
    the CRC and length that close the container — is simply never written. Any
    tool that opens the file reports it as corrupt, which is the honest outcome.
    """
    assert process.stdout is not None
    compressor = zlib.compressobj(GZIP_LEVEL, zlib.DEFLATED, GZIP_WBITS)
    total = 0
    chunk = first
    while chunk:
        total += len(chunk)
        if block := compressor.compress(chunk):
            yield block
        chunk = await process.stdout.read(CHUNK_BYTES)

    await process.wait()
    if process.returncode != 0:
        logger.error("pg_dump failed mid-dump: %s", (await stderr).decode())
        raise RuntimeError("pg_dump failed after the download had started")

    yield compressor.flush()
    logger.info("Backup generated: %s (%d bytes of SQL)", filename, total)


@router.post("/admin/download", response_model=None)
@limiter.limit("3/hour")
async def download_backup(
    request: Request,
    _admin: dict = Depends(get_current_admin),
) -> StreamingResponse | JSONResponse:
    """Stream a gzipped pg_dump of the database as a download."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"ligavpv_{timestamp}.sql.gz"

    process = await _start_pg_dump()
    assert process.stdout is not None and process.stderr is not None
    # Drained concurrently: pg_dump blocks once it fills the stderr pipe, and it
    # would then never finish writing the stdout we are reading. That deadlocks.
    stderr = asyncio.create_task(process.stderr.read())

    # Whatever fails before a single byte of SQL — permissions, auth, a missing
    # database — still gets a clean 500 with the reason, as it did before.
    first = await process.stdout.read(CHUNK_BYTES)
    if not first:
        await process.wait()
        message = (await stderr).decode() or "pg_dump produced no output"
        logger.error("pg_dump failed: %s", message)
        return JSONResponse(status_code=500, content={"message": f"Backup failed: {message}"})

    return StreamingResponse(
        _gzipped(process, stderr, first, filename),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
