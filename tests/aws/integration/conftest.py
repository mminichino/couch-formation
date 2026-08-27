from collections.abc import Callable
import pytest

@pytest.fixture
def cleanup(request):
    handlers: list[Callable[[], None]] = []

    def register(fn: Callable[[], None]) -> None:
        handlers.append(fn)

    def _run_cleanup() -> None:
        for fn in reversed(handlers):
            try:
                fn()
            except Exception:
                pass

    request.addfinalizer(_run_cleanup)
    return register
