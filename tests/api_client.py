"""In-process HTTP client using the application's real lifespan context."""

from contextlib import AsyncExitStack, asynccontextmanager

from httpx import ASGITransport, AsyncClient


@asynccontextmanager
async def api_client(app):
    # HTTPX does not run lifespan. Enter it explicitly so readiness, model loading
    # and shutdown remain covered without Starlette 0.37.2 TestClient streams.
    lifespan = AsyncExitStack()
    try:
        await lifespan.enter_async_context(app.router.lifespan_context(app))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client
    finally:
        # As with TestClient, request failures propagate to the test, not to the
        # independent lifespan task. aclose() performs normal shutdown even when
        # an application places its cleanup after yield without a finally block.
        await lifespan.aclose()
