import os
from datetime import timedelta
from functools import wraps
from http import HTTPStatus
from pathlib import Path
from typing import Literal

import jwt
from flask import Flask, abort, request

from pywrstat.client import Pywrstat
from pywrstat.reader import Reader
from pywrstat.schema import BaseModel

app = Flask(__name__)


class ServerConfig(BaseModel):
    secret_key: str
    jwt_secret_key: str | None
    sudo_pwrstat: bool
    pwrstat_path: Path | None

    @staticmethod
    def from_env() -> "ServerConfig":
        return ServerConfig(
            secret_key=os.environ["PYWRSTAT_WEB_SECRET_KEY"],
            jwt_secret_key=os.getenv("PYWRSTAT_WEB_JWT_SECRET_KEY"),
            sudo_pwrstat=os.getenv("PYWRSTAT_RUN_PWRSTAT_WITH_SUDO", True),
            pwrstat_path=os.getenv("PYWRSTAT_PWRSTAT_EXECUTABLE_PATH", None),
        )


class JwtPayload(BaseModel):
    iss: Literal["pywrstat_web"] = "pywrstat_web"
    jti: str


def get_server_config() -> ServerConfig:
    return app.config["server_config"]


def pydantic_json_response(data: BaseModel, status: int = 200):
    return app.response_class(
        response=data.model_dump_json(), status=status, mimetype="application/json"
    )


def get_pywrstat_client() -> Pywrstat:
    server_config = get_server_config()
    reader = Reader(
        run_with_sudo=server_config.sudo_pwrstat,
        pwrstat_path=server_config.pwrstat_path,
    )
    return Pywrstat(reader)


def require_jwt(func):
    @wraps(func)
    def impl(*args, **kwargs):
        if jwt_secret_key := get_server_config().jwt_secret_key:
            try:
                _, jwt_token = request.headers["Authorization"].split(" ", maxsplit=1)
                JwtPayload.model_validate(
                    jwt.decode(jwt_token, jwt_secret_key, "HS256")
                )
            except Exception:
                return abort(HTTPStatus.UNAUTHORIZED)
        return func(*args, **kwargs)

    return impl


@app.route("/pywrstat/ups/status")
@require_jwt
def get_ups_status():
    return pydantic_json_response(get_pywrstat_client().get_ups_status())


@app.route("/pywrstat/ups/status/monitor")
@require_jwt
def monitor_ups_status():
    def monitor(poll_every: timedelta):
        for event in get_pywrstat_client().monitor_ups_status(poll_every):
            yield f"data: {event.model_dump_json()}\n\n"

    return app.response_class(
        response=monitor(
            poll_every=timedelta(seconds=float(request.args.get("pollEvery", 5.0)))
        ),
        mimetype="text/event-stream",
    )


@app.route("/pywrstat/ups/properties")
def get_ups_properties():
    return pydantic_json_response(get_pywrstat_client().get_ups_properties())


@app.route("/pywrstat/daemon/configuration")
def get_daemon_configuration():
    return pydantic_json_response(get_pywrstat_client().get_daemon_configuration())


def create_app():
    server_config = ServerConfig.from_env()
    app.secret_key = server_config.secret_key
    app.config["server_config"] = server_config
    return app


def main():
    create_app().run()


if __name__ == "__main__":
    main()
