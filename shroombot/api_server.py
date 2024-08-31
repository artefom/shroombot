"""
Serving of the API
"""

import logging
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import RedirectResponse
from prometheus_client import Counter
from starlette_exporter import PrometheusMiddleware, handle_metrics

logger = logging.getLogger(__name__)


RESULT_COUNTER = Counter(
    "num_results_shown", "Number of results shown to users", ("instance_id",)
)

# Reset so it shows 0
RESULT_COUNTER.reset()

# This needs to be unique on every deployment
INSTANCE_ID = str(uuid4())[:8]


def make_app(root_path: str):
    app = FastAPI(root_path=root_path)

    app.add_middleware(
        PrometheusMiddleware,
        filter_unhandled_paths=True,
        group_paths=True,
        app_name="python-backend-example",
        buckets=[
            0.01,
            0.025,
            0.05,
            0.075,
            0.1,
            0.25,
            0.5,
            0.75,
            1.0,
            2.5,
            5.0,
            7.5,
            10.0,
        ],
        skip_paths=[
            f"{root_path}{path}"
            for path in ["/health", "/metrics", "/", "/docs", "/openapi.json"]
        ],
    )

    app.add_route("/metrics", handle_metrics)

    # Health check endpoint
    @app.get("/health", include_in_schema=False)
    async def health() -> str:
        """Checks health of application, including database and all systems"""

        return "OK"

    @app.post("/record-result-stats")
    async def record_result_stats() -> str:
        """
        Increments counter of test results shown
        """
        RESULT_COUNTER.labels(INSTANCE_ID).inc()

        return "OK"

    @app.get("/", include_in_schema=False)
    async def index(request: Request) -> RedirectResponse:
        # the redirect must be absolute (start with /) because
        # it needs to handle both trailing slash and no trailing slash
        # /app -> /app/docs
        # /app/ -> /app/docs
        return RedirectResponse(f"{str(request.base_url).rstrip('/')}/docs")

    # We need to specify custom OpenAPI to add app.root_path to servers
    def custom_openapi() -> Any:
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title="Example Backend service",
            version="0.1.0",
            description="Can be used as a clean tempalte for new services",
            routes=app.routes,
        )
        openapi_schema["servers"] = [{"url": app.root_path}]
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi  # noqa

    return app


async def run_api_server(bind: str, root_path: str):
    host, port = bind.split(":")

    port = int(port)

    app = make_app(root_path)
    config = uvicorn.Config(app, host, port, log_config=None, access_log=False)
    api_server = uvicorn.Server(config)
    logging.info("Serving on http://%s:%s", host, port)
    await api_server.serve()
