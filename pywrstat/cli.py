import pwd
import secrets
import subprocess
import sys
import uuid
from argparse import ArgumentParser, Namespace
from pathlib import Path
from textwrap import dedent

import jwt
from dotenv import dotenv_values

from pywrstat.client import Pywrstat
from pywrstat.constants import DEFAULT_PWRSTAT_PATH
from pywrstat.schema import BaseModel
from pywrstat.web import JwtPayload

PYWRSTAT_WEB_SERVICE_SYSTEMD_SERVICE_NAME = "pywrstat-web.service"
PYWRSTAT_WEB_DEFAULT_USER = "pywrstat_web"
PYWRSTAT_WEB_SERVICE_CONF_DIR = Path("/etc/pywrstat/")
PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH = PYWRSTAT_WEB_SERVICE_CONF_DIR / "pywrstat_web.env"
SYSTEMD_WEB_SERVICE_FILE_PATH = Path(
    f"/etc/systemd/system/{PYWRSTAT_WEB_SERVICE_SYSTEMD_SERVICE_NAME}"
)
SYSTEMD_WEB_SERVICE_TEMPLATE = """
[Unit]
Description=Pywrstat web server
After=network.target

[Service]
type=Simple
User={username}
EnvironmentFile={env_file_path}
ExecStart={python_executable_path} -m gunicorn -w 2 -b {host}:{port} {gunicorn_extra_args} 'pywrstat.web:create_app()'

[Install]
WantedBy=multi-user.target
"""


def sh(command: str):
    subprocess.run(command, shell=True, check=True)


def user_exists(user_name: str) -> bool:
    try:
        pwd.getpwnam(user_name)
        return True
    except KeyError:
        return False


def create_user(user_name: str):
    sh(f"useradd -m {user_name}")


def parse_bind_host_port(bind_expr: str) -> tuple[str, int]:
    raw_host, raw_port = bind_expr.split(":")
    host = raw_host if raw_host != "" else "0.0.0.0"
    return host, int(raw_port)


def get_server_jwt_key() -> str | None:
    try:
        conf = dotenv_values(PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH)
        return conf["PYWRSTAT_WEB_JWT_SECRET_KEY"]
    except Exception:
        return None


def print_pydantic_json(data: BaseModel):
    print(data.model_dump_json(indent=2))


def web_systemctl_install_mode(args: Namespace):
    username = args.user
    if not user_exists(username):
        print(f"User '{username}' does not exist, creating")
        create_user(username)
    PYWRSTAT_WEB_SERVICE_CONF_DIR.mkdir(mode=0o600, parents=True, exist_ok=True)
    print(f"Writing server environment file at: {PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH}")
    PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH.touch(mode=0o600)
    PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH.write_text(
        dedent(
            f"""\
    PYWRSTAT_WEB_SECRET_KEY="{secrets.token_hex(128)}"
    PYWRSTAT_WEB_JWT_SECRET_KEY="{get_server_jwt_key() or secrets.token_hex(128)}"
    PYWRSTAT_PWRSTAT_EXECUTABLE_PATH="{args.pwrstat_path}"
    PYWRSTAT_RUN_PWRSTAT_WITH_SUDO={int(args.sudo_pwrstat)}
    """
        )
    )
    gunicorn_extra_args = None
    if args.certfile and args.keyfile:
        gunicorn_extra_args = f"--certfile={args.certfile} --keyfile={args.keyfile}"
    service_already_exists = SYSTEMD_WEB_SERVICE_FILE_PATH.exists()
    service_host, service_port = args.bind
    SYSTEMD_WEB_SERVICE_FILE_PATH.write_text(
        SYSTEMD_WEB_SERVICE_TEMPLATE.format(
            python_executable_path=sys.executable,
            env_file_path=PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH,
            username=username,
            host=service_host,
            port=service_port,
            gunicorn_extra_args=gunicorn_extra_args or ""
        )
    )
    if args.edit_sudoers:
        sudoers_file_path = Path("/etc/sudoers")
        sudoers_entry = f"{username} ALL=(root) NOPASSWD: /usr/sbin/pwrstat *"
        sudoers = sudoers_file_path.read_text().strip()
        if sudoers_entry not in sudoers:
            print(f"Allowing user '{username}' to run pwrstat as 'root' (via sudoers)")
            sudoers_file_path.write_text(f"{sudoers}\n{sudoers_entry}\n")
    if service_already_exists:
        sh(f"systemctl daemon-reload")
    if args.enable_service:
        sh(f"systemctl enable {PYWRSTAT_WEB_SERVICE_SYSTEMD_SERVICE_NAME}")
    if args.start_service:
        sh(f"systemctl restart {PYWRSTAT_WEB_SERVICE_SYSTEMD_SERVICE_NAME}")


def web_api_key_get_mode():
    conf = dotenv_values(PYWRSTAT_WEB_SERVICE_ENV_FILE_PATH)
    jwt_secret_key = conf["PYWRSTAT_WEB_JWT_SECRET_KEY"]
    api_key = jwt.encode(JwtPayload(jti=str(uuid.uuid4())).model_dump(), jwt_secret_key)
    print(api_key)


def create_argument_parser():
    parser = ArgumentParser(description="Pywrstat command line interface")
    sub_parsers = parser.add_subparsers(description="Mode", dest="mode", required=True)
    sub_parsers.add_parser("ups.status")
    sub_parsers.add_parser("ups.properties")
    sub_parsers.add_parser("daemon.configuration")
    sub_parsers.add_parser("web.api_key.get")
    web_systemctl_install_parser = sub_parsers.add_parser("web.systemctl.install")
    web_systemctl_install_parser.add_argument(
        "--bind",
        type=parse_bind_host_port,
        default=":8000",
        help="Bind the pywrstat web server to <address>:<port> (default: 0.0.0.0:8000)",
    )
    web_systemctl_install_parser.add_argument(
        "--user",
        type=str,
        default=PYWRSTAT_WEB_DEFAULT_USER,
        help="User running the web server (default: current user)",
    )
    web_systemctl_install_parser.add_argument(
        "--pwrstat-path",
        default=DEFAULT_PWRSTAT_PATH,
        help=f"Path to pwrstat executable (default: {DEFAULT_PWRSTAT_PATH})",
    )
    web_systemctl_install_parser.add_argument(
        "--certfile",
        type=Path,
        default=None,
        help="Server certificate file (optional)"
    )
    web_systemctl_install_parser.add_argument(
        "--keyfile",
        type=Path,
        default=None,
        help="Server private key file (optional)"
    )
    web_systemctl_install_parser.add_argument(
        "--no-sudo-pwrstat",
        type=Path,
        default=True,
        dest="sudo_pwrstat",
        help="Don't run pwrstat using sudo",
    )
    web_systemctl_install_parser.add_argument(
        "--no-edit-sudoers",
        action="store_false",
        dest="edit_sudoers",
        default=True,
        help="Don't give user permissions to run pywrstat as root via sudoers",
    )
    web_systemctl_install_parser.add_argument(
        "--no-start-service",
        action="store_false",
        dest="start_service",
        default=True,
        help="Don't start the pywrstat web server directly after installation",
    )
    web_systemctl_install_parser.add_argument(
        "--no-enable-service",
        action="store_false",
        dest="enable_service",
        default=True,
        help="Don't automatically start the pywrstat web server on system startup",
    )
    return parser


def main():
    args = create_argument_parser().parse_args()
    mode = args.mode
    pywrstat_client = Pywrstat()
    if mode == "ups.status":
        return print_pydantic_json(pywrstat_client.get_ups_status())
    if mode == "ups.properties":
        return print_pydantic_json(pywrstat_client.get_ups_properties())
    if mode == "daemon.configuration":
        return print_pydantic_json(pywrstat_client.get_daemon_configuration())
    if mode == "web.systemctl.install":
        return web_systemctl_install_mode(args)
    if mode == "web.api_key.get":
        return web_api_key_get_mode()
    assert False


if __name__ == "__main__":
    main()
