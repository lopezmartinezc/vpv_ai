import asyncio
from unittest.mock import AsyncMock

import pytest

from .. import history, service
from ..engine import Progress
from ..errors import AssistantError
from ..schemas import Answer, History, Usage, ViewContext
from ..stream import events
from ..tools import Toolset
from .factories import request, snapshot


def answer() -> Answer:
    data = snapshot()
    return service.build_answer(data, Toolset(data, 11, ViewContext()), None, request(), Usage())


@pytest.mark.asyncio
async def test_stream_progress_and_done() -> None:
    async def work(progress: Progress) -> Answer:
        await progress("Checking")
        return answer()

    frames = [frame async for frame in events(work)]
    assert '"name": "Checking"' in frames[0]
    assert frames[-1].startswith("event: done")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [AssistantError("BUSY", "Busy", 409), TimeoutError(), RuntimeError("secret")]
)
async def test_stream_safe_errors(error: Exception) -> None:
    async def work(progress: Progress) -> Answer:
        raise error

    frames = [frame async for frame in events(work)]
    assert "event: error" in frames[-1]
    assert "secret" not in frames[-1]


@pytest.mark.asyncio
async def test_disconnect_awaits_worker_cleanup() -> None:
    cleaned = asyncio.Event()

    async def work(progress: Progress) -> Answer:
        try:
            await progress("Started")
            await asyncio.Event().wait()
            return answer()
        finally:
            cleaned.set()

    stream = events(work)
    await anext(stream)
    await stream.aclose()
    assert cleaned.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [None, RuntimeError("failure"), asyncio.CancelledError()])
async def test_ask_always_releases_lease(
    monkeypatch: pytest.MonkeyPatch, error: BaseException | None
) -> None:
    monkeypatch.setattr(service, "validate_provider", lambda *args: None)
    acquire, release, save = AsyncMock(return_value="lease"), AsyncMock(), AsyncMock()
    monkeypatch.setattr(history, "acquire", acquire)
    monkeypatch.setattr(history, "release", release)
    monkeypatch.setattr(history, "save", save)
    monkeypatch.setattr(service, "analyze", AsyncMock(return_value=answer(), side_effect=error))
    if error:
        with pytest.raises(type(error)):
            await service.ask(1, 11, request(), AsyncMock())
        save.assert_not_awaited()
    else:
        await service.ask(1, 11, request(), AsyncMock())
        save.assert_awaited_once()
    release.assert_awaited_once_with(11, 1, "lease")


@pytest.mark.asyncio
async def test_analyze_reloads_after_provider_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    load = AsyncMock(return_value=snapshot())
    monkeypatch.setattr(service, "load_snapshot", load)
    monkeypatch.setattr(history, "read_history", AsyncMock(return_value=History()))
    monkeypatch.setattr(service, "run_engine", AsyncMock(side_effect=TimeoutError()))
    result = await service.analyze(1, 11, request(), AsyncMock())
    assert result.status == "incomplete"
    assert load.await_count == 2


@pytest.mark.asyncio
async def test_empty_question_never_acquires_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    acquire = AsyncMock()
    monkeypatch.setattr(history, "acquire", acquire)
    with pytest.raises(AssistantError, match="Escribe"):
        await service.ask(1, 11, request().model_copy(update={"question": " "}), AsyncMock())
    acquire.assert_not_awaited()
