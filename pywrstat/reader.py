import abc
import os
from pathlib import Path
from subprocess import PIPE, Popen
from typing import List, Optional

from pywrstat.constants import DEFAULT_PWRSTAT_PATH
from pywrstat.errors import CommandFailed, MissingBinary


def _get_default_pwrstat_path() -> Path:
    return Path(
        os.environ.get("PYWRSTAT_PWRSTAT_EXECUTABLE_PATH", DEFAULT_PWRSTAT_PATH)
    )


def _get_run_with_sudo_by_default(user_preference: Optional[bool]) -> bool:
    if user_preference is not None:
        return user_preference
    return bool(int(os.environ.get("PYWRSTAT_RUN_PWRSTAT_WITH_SUDO", False)))


class ReaderBase(abc.ABC):
    @abc.abstractmethod
    def read(self, args: List[str]) -> str:
        pass


class Reader(ReaderBase):
    def __init__(
        self, pwrstat_path: Optional[Path] = None, run_with_sudo: Optional[bool] = None
    ):
        self._sudo = _get_run_with_sudo_by_default(user_preference=run_with_sudo)
        self._pwrstat_path = pwrstat_path or _get_default_pwrstat_path()
        if not self._pwrstat_path.is_file():
            raise MissingBinary(f"pwrstat is not installed at '{self._pwrstat_path}'")

    def read(self, args: List[str]) -> str:
        sudo_prefix = ["sudo"] if self._sudo else []
        all_args = sudo_prefix + [str(self._pwrstat_path)] + args
        with Popen(all_args, stdout=PIPE, stderr=PIPE) as s:
            out, err = s.communicate()
            full_output = out.decode().strip() + err.decode().strip()
            if s.returncode != 0:
                raise CommandFailed(
                    f"Failed to run {all_args} (rc={s.returncode}). Full pwrstat output: {full_output}"
                )
            return full_output
