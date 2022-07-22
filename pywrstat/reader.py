import abc
import os
from pathlib import Path
from subprocess import PIPE, Popen
from typing import List, Optional

from pywrstat.errors import CommandFailed, MissingBinary

_DEFAULT_PWRSTAT_PATH = Path("/usr/sbin/pwrstat")


def _get_default_pwrstat_path():
    pwrstat_path_override = os.environ.get("PYWRSTAT_EXECUTABLE_PATH")
    if not pwrstat_path_override:
        return _DEFAULT_PWRSTAT_PATH


class ReaderBase(abc.ABC):
    @abc.abstractmethod
    def read(self, args: List[str]) -> str:
        pass


class Reader(ReaderBase):
    def __init__(self, pwrstat_path: Optional[Path] = None):
        self._pwrstat_path = pwrstat_path or _get_default_pwrstat_path()
        if not self._pwrstat_path.is_file():
            raise MissingBinary(f"pwrstat is not installed at '{self._pwrstat_path}'")

    def read(self, args: List[str]) -> str:
        all_args = [str(self._pwrstat_path)] + args
        with Popen(all_args, stdout=PIPE, stderr=PIPE) as s:
            out, err = s.communicate()
            full_output = out.decode().strip() + err.decode().strip()
            if s.returncode != 0:
                raise CommandFailed(
                    f"Failed to run {all_args} (rc={s.returncode}). Full pwrstat output: {full_output}"
                )
            return full_output
