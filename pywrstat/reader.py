import abc
import os
from subprocess import PIPE, Popen
from textwrap import dedent
from pathlib import Path
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


class FakeReader(ReaderBase):
    def __init__(self, reachable: bool = True):
        self._reachable = reachable

    def read(self, args: List[str]) -> str:
        if args == ["-status"] and self._reachable:
            return dedent(
                """
                The UPS information shows as following:
                
                    Properties:
                        Model Name................... CP1500EPFCLCD
                        Firmware Number.............. CR01505B481
                        Rating Voltage............... 230 V
                        Rating Power................. 900 Watt
                
                    Current UPS status:
                        State........................ Normal
                        Power Supply by.............. Utility Power
                        Utility Voltage.............. 233 V
                        Output Voltage............... 233 V
                        Battery Capacity............. 100 %
                        Remaining Runtime............ 129 min.
                        Load......................... 27 Watt(3 %)
                        Line Interaction............. None
                        Test Result.................. Passed at 2022/07/21 16:16:42
                        Last Power Event............. Blackout at 2022/07/21 15:10:43 for 24 sec.
            """
            ).strip()

        if args == ["-status"] and not self._reachable:
            return dedent(
                """
                The UPS information shows as following:
                
                    Properties:
                        Model Name................... CP1500EPFCLCD
                        Firmware Number.............. CR01505B481
                        Rating Voltage............... 230 V
                        Rating Power................. 900 Watt
                
                    Current UPS status:
                        State........................ Lost Communication
                        Test Result.................. Passed at 2022/07/21 16:16:42
                        Last Power Event............. Blackout at 2022/07/21 15:10:43 for 24 sec.
            """
            )

        if args == ["-test"]:
            return 'The UPS test is initiated, checking the result by command "pwrstat -status".'

        if args == ["-config"]:
            return dedent(
                """
                Daemon Configuration:
                
                Alarm .............................................. Off
                Hibernate .......................................... Off
                Cloud .............................................. Off
                
                Action for Power Failure:
                
                    Delay time since Power failure ............. 600 sec.
                    Run script command ......................... On
                    Path of script command ..................... /etc/pwrstatd-powerfail.sh
                    Duration of command running ................ 0 sec.
                    Enable shutdown system ..................... On
                
                Action for Battery Low:
                
                    Remaining runtime threshold ................ 600 sec.
                    Battery capacity threshold ................. 35 %.
                    Run script command ......................... On
                    Path of command ............................ /etc/pwrstatd-lowbatt.sh
                    Duration of command running ................ 0 sec.
                    Enable shutdown system ..................... On
            """
            ).strip()

        raise RuntimeError(f"Bad arguments: {args}")
