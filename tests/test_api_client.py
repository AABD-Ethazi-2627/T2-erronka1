import unittest
from contextlib import asynccontextmanager

from api_client import api_client
from fastapi import FastAPI


class ApiClientTests(unittest.IsolatedAsyncioTestCase):
    async def check_lifecycle(self, fail_request):
        events = []

        @asynccontextmanager
        async def lifespan(app):
            events.append("startup")
            yield
            events.append("shutdown")

        app = FastAPI(lifespan=lifespan)

        @app.get("/")
        async def root():
            if fail_request:
                raise ValueError("request failed")
            return {"ready": events == ["startup"]}

        async def request():
            async with api_client(app) as client:
                self.assertEqual(events, ["startup"])
                try:
                    response = await client.get("/")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {"ready": True})
                finally:
                    self.client = client

        if fail_request:
            with self.assertRaisesRegex(ValueError, "request failed"):
                await request()
        else:
            await request()
        self.assertTrue(self.client.is_closed)
        self.assertEqual(events, ["startup", "shutdown"])

    async def test_client_and_lifespan_close_after_request(self):
        await self.check_lifecycle(fail_request=False)

    async def test_client_and_lifespan_close_after_request_error(self):
        await self.check_lifecycle(fail_request=True)
