import re
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Union

from dateutil.parser import parse as parse_time

from pywrstat.dto import (
    DaemonConfiguration,
    LowBatteryAction,
    PowerEvent,
    PowerFailureAction,
    TestResult,
    TestStatus,
    UPSProperties,
    UPSStatus,
)
from pywrstat.errors import CommandFailed, NotReady, SetupFailed, Timeout, Unreachable
from pywrstat.reader import Reader, ReaderBase

_PywrstatSectionType = str
_PywrstatPropertyType = str
_PywrstatValueType = str
_PywrstatParsedOutputType = Dict[
    _PywrstatSectionType, Dict[_PywrstatPropertyType, _PywrstatValueType]
]


PropertyBag = Dict[str, str]


def _parse_pwrstat_output(output: str) -> _PywrstatParsedOutputType:
    current_section: Optional[str] = None
    parsed_output: _PywrstatParsedOutputType = defaultdict(dict)
    for line in output.splitlines(keepends=False):
        match = re.search(r"^\s*([^:]+):$", line)
        if match:
            current_section = match.group(1)
            continue
        match = re.search(r"^\s*([^.]+)\.+\s+(.+)$", line)
        if match:
            assert current_section
            current_prop = match.group(1).strip()
            current_value = match.group(2).strip()
            parsed_output[current_section][current_prop] = current_value
    return parsed_output


def _parse_load_percent(raw_load: str) -> float:
    match = re.search(r"^\d+\s*Watt\((\d+)\s*%\)$", raw_load)
    if not match:
        raise ValueError(f"could not parse load (%) from '{raw_load}'")
    return float(match.group(1)) / 100.0


def _parse_test_result(raw_test_result: str) -> Optional[TestResult]:
    raw_test_result = raw_test_result.strip()
    if raw_test_result == "None":
        return None
    if raw_test_result == "In progress":
        return TestResult(status=TestStatus.InProgress, test_time=None)
    match = re.search(
        r"^([^\s]+)\s+at\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})$", raw_test_result
    )
    if match:
        return TestResult(
            status=(
                TestStatus.Passed if match.group(1) == "Passed" else TestStatus.Failed
            ),
            test_time=parse_time(match.group(2)),
        )
    return None


def _parse_power_event(raw_power_event: str) -> Optional[PowerEvent]:
    match = re.search(
        r"^([\w\s]+)\s+at\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+for\s+(\d+) sec\.$",
        raw_power_event,
    )
    if match:
        return PowerEvent(
            event_type=match.group(1),
            event_time=parse_time(match.group(2)),
            duration=timedelta(seconds=int(match.group(3))),
        )
    return None


def _is_ups_reachable(raw_ups_status: PropertyBag) -> bool:
    return raw_ups_status["State"] != "Lost Communication"


def _check_percent(value: float) -> float:
    if not isinstance(value, float) or value < 0.0 or value > 1.0:
        raise ValueError(
            f"percent should be a float value between 0.0 and 1.0 (inclusive),"
            f" not '{value}' ({type(value).__name__})"
        )
    return value


def _parse_power_failure_action(data: PropertyBag) -> PowerFailureAction:
    return PowerFailureAction(
        delay_time_since_power_failure=timedelta(
            seconds=int(data["Delay time since Power failure"].split()[0])
        ),
        script_command_enabled=_parse_on_off(data["Run script command"]),
        script_command_path=Path(data["Path of script command"]),
        script_command_duration=timedelta(
            seconds=int(data["Duration of command running"].split()[0])
        ),
        system_shutdown_enabled=_parse_on_off(data["Enable shutdown system"]),
    )


def _parse_low_battery_action(data: PropertyBag) -> LowBatteryAction:
    return LowBatteryAction(
        remaining_runtime_threshold=timedelta(
            seconds=int(data["Remaining runtime threshold"].split()[0])
        ),
        battery_capacity_threshold_percent=float(
            data["Battery capacity threshold"].split()[0]
        )
        / 100,
        script_command_enabled=_parse_on_off(data["Run script command"]),
        script_command_path=Path(data["Path of command"]),
        script_command_duration=timedelta(
            seconds=int(data["Duration of command running"].split()[0])
        ),
        system_shutdown_enabled=_parse_on_off(data["Enable shutdown system"]),
    )


def _parse_on_off(raw_value: str) -> bool:
    return {"on": True, "off": False}[raw_value.lower()]


def _on_off(value: bool) -> str:
    return "on" if value else "off"


class Pywrstat(object):
    def __init__(self, reader: Optional[ReaderBase] = None):
        self._reader = reader or Reader()

    def is_reachable(self) -> bool:
        """Check whether the UPS is reachable.
        :return: True if the UPS is reachable, False otherwise.
        """
        return _is_ups_reachable(
            self.get_raw_complete_ups_status()["Current UPS status"]
        )

    def get_pwrstat_version(self) -> Optional[str]:
        """Get the pwrstat binary version (as returned by `pwrstat -version`).
        :return: pwrstat binary version (as returned by `pwrstat -version`).
        """
        for line in self._reader.read(["-version"]).splitlines(keepends=False):
            match = re.search(r"^pwrstat version (\d+\.\d+\.\d+)$", line.strip())
            if match:
                return match.group(1)
        return None

    def get_raw_daemon_configuration(self) -> Dict[str, PropertyBag]:
        """Get the raw pwrstatd (pwrstat daemon) configuration (as returned by `pwrstat -config`).
        :return: raw pwrstatd (pwrstat daemon) configuration (as returned by `pwrstat -config`). The output is
                 a mapping of sections (example "Action for Power Failure") to their respective configurations (which
                 is a mapping of properties to string values)
        """
        return _parse_pwrstat_output(self._reader.read(["-config"]))

    def get_daemon_configuration(self) -> DaemonConfiguration:
        """Get the pwrstatd (pwrstat daemon) configuration (as returned by `pwrstat -config`).
        :return: pwrstatd (pwrstat daemon) configuration (as returned by `pwrstat -config`). The output is deserialized
                 to a `DaemonConfiguration` object.
        """
        data = self.get_raw_daemon_configuration()
        return DaemonConfiguration(
            alarm_enabled=_parse_on_off(data["Daemon Configuration"]["Alarm"]),
            hibernate_enabled=_parse_on_off(data["Daemon Configuration"]["Hibernate"]),
            cloud_enabled=_parse_on_off(data["Daemon Configuration"]["Cloud"]),
            power_failure_action=_parse_power_failure_action(
                data["Action for Power Failure"]
            ),
            low_battery_action=_parse_low_battery_action(
                data["Action for Battery Low"]
            ),
        )

    def get_power_failure_action(self) -> PowerFailureAction:
        """Get the power failure action configuration (i.e. "Action for Power Failure") from the daemon configuration.
        :return: power failure action configuration (i.e. "Action for Power Failure") from the daemon configuration.
                 The output is deserialized to a `PowerFailureAction` object.
        """
        return self.get_daemon_configuration().power_failure_action

    def get_low_battery_action(self) -> LowBatteryAction:
        """Get the low battery action configuration (i.e. "Action for Battery Low") from the daemon configuration.
        :return: low battery action configuration (i.e. "Action for Battery Low") from the daemon configuration. The
                 output is deserialized to a `LowBatteryAction` object.
        """
        return self.get_daemon_configuration().low_battery_action

    def get_raw_complete_ups_status(
        self, check_reachable: bool = False
    ) -> Dict[str, PropertyBag]:
        """Get the complete raw UPS status (as returned by `pwrstat -status`).
        :return: raw UPS status (as returned by `pwrstat -status`). The output is a mapping of sections
                 (example "Current UPS status") to their respective configurations (which is a mapping of
                 properties to string values)
        """
        data = _parse_pwrstat_output(self._reader.read(["-status"]))
        if check_reachable and not _is_ups_reachable(data["Current UPS status"]):
            raise Unreachable("UPS is not reachable")
        return data

    def get_raw_ups_status(self, check_reachable: bool = False) -> PropertyBag:
        """Get the raw UPS status limited to the "Current UPS status" section (as returned by `pwrstat -status`).
        :return: raw UPS status limited to the "Current UPS status" section (as returned by `pwrstat -status`). The
                 output is a mapping of properties to string values.
        :raises: Unreachable: If the UPS is not reachable.
        """
        return self.get_raw_complete_ups_status(check_reachable)["Current UPS status"]

    def get_ups_status(self) -> UPSStatus:
        """Get the UPS status limited to the "Current UPS status" section.
        :return: The UPS status limited to the "Current UPS status" section. The output is deserialized to a
                 `UPSStatus` object.
        :raises: Unreachable: If the UPS is not reachable.
        """
        data = self.get_raw_ups_status(check_reachable=True)
        return UPSStatus(
            state=data["State"],
            power_supply_by=data["Power Supply by"],
            utility_voltage_volts=float(data["Utility Voltage"].split()[0]),
            output_voltage_volts=float(data["Output Voltage"].split()[0]),
            battery_capacity_percent=float(data["Battery Capacity"].split()[0]) / 100.0,
            remaining_runtime=timedelta(
                minutes=int(data["Remaining Runtime"].split()[0])
            ),
            load_watts=float(data["Load"].split()[0]),
            load_percent=_parse_load_percent(data["Load"]),
            line_interaction=data["Line Interaction"],
            test_result=_parse_test_result(data["Test Result"]),
            last_power_event=_parse_power_event(data["Last Power Event"]),
        )

    def get_raw_ups_properties(self, check_reachable: bool = False) -> PropertyBag:
        """Get the raw UPS status limited to the "Properties" section (as returned by `pwrstat -status`).
        :return: raw UPS status limited to the "Properties" section (as returned by `pwrstat -status`). The
                 output is a mapping of properties to string values.
        :raises: Unreachable: If the UPS is not reachable.
        """
        return self.get_raw_complete_ups_status(check_reachable=check_reachable)[
            "Properties"
        ]

    def get_ups_properties(self) -> UPSProperties:
        """Get the UPS status limited to the "Properties" section.
        :return: The UPS status limited to the "Properties" section. The output is deserialized to a
                 `UPSProperties` object.
        :raises: Unreachable: If the UPS is not reachable.
        """
        data = self.get_raw_ups_properties(check_reachable=True)
        return UPSProperties(
            model_name=data["Model Name"],
            firmware_number=data["Firmware Number"],
            rating_voltage_volts=float(data["Rating Voltage"].split()[0]),
            rating_power_watts=float(data["Rating Power"].split()[0]),
        )

    def test_ups(
        self,
        poll_result: bool = True,
        timeout: Optional[timedelta] = None,
        poll_every: Optional[timedelta] = None,
    ) -> Optional[TestResult]:
        """Verify the UPS will work well in battery power (as run by `pwrstat -test`). The user of this function
            can choose to wait for the test to complete or not (`True` by default).
        :param poll_result: Whether to wait for the tests results (`True` by default). If set to `False`, directly
                            return the last known test result after starting the tests.
        :param timeout: Give up polling after the specified duration. No timeout by default.
        :param poll_every: Time between two test results polls (defaults to 1 second).
        :return: Final test result or `None` if polling is disabled.
        :raises: Unreachable: If the UPS is not reachable.
        :raises: CommandFailed: If the tests could not be started.
        :raises: NotReady: If a test is already in progress.
        :raises: Timeout: If the tests did not complete after the specified timeout.
        """
        previous_test_result = self.get_ups_status().test_result
        if (
            previous_test_result
            and previous_test_result.status == TestStatus.InProgress
        ):
            raise NotReady("A test is already in progress")
        data = self._reader.read(["-test"])
        if "The UPS test is initiated" not in data:
            raise CommandFailed(data)
        if not poll_result:
            return None
        cutoff = datetime.now() + timeout if timeout else None
        poll_every = timedelta(seconds=1) if poll_every is None else poll_every
        start_time = datetime.now()
        while True:
            last_result = self.get_ups_status().test_result
            if last_result == previous_test_result:
                pass
            elif last_result and last_result.status != TestStatus.InProgress:
                return last_result
            if cutoff and datetime.now() > cutoff:
                now = datetime.now()
                elapsed_seconds = (now - start_time).total_seconds()
                raise Timeout(
                    f"Timed out waiting for tests results after {elapsed_seconds}s."
                    f" Last status was '{last_result.status.value if last_result else 'unknown'}'."
                )
            time.sleep(poll_every.total_seconds())

    def reset_daemon_configuration(self) -> None:
        """Reset all daemon configurations to default (as run by `pwrstat -reset`).
        :return: Daemon configuration after reset.
        :raises: CommandFailed: If the daemon configuration could not be reset.
        """
        self._reader.read(["-reset"])

    @property
    def hibernation_enabled(self) -> bool:
        """Check whether system hibernation (vs. system shutdown) is enabled.
        :return: `True` if hibernation is enabled, `False` otherwise.
        """
        return self.get_daemon_configuration().hibernate_enabled

    @hibernation_enabled.setter
    def hibernation_enabled(self, enabled: bool):
        """Set up the hibernation (vs. system shutdown) enablement (as run by `pwrstat -hibernate [on/off]`).
        :param enabled: Specify whether to enable or disable hibernation (vs. system shutdown).
        """
        self._check_setup(self._reader.read(["-hibernate", _on_off(enabled)]))

    @property
    def alarm_enabled(self) -> bool:
        """Check whether the UPS alarm is enabled.
        :return: `True` if the UPS alarm is enabled, `False` otherwise.
        """
        return self.get_daemon_configuration().alarm_enabled

    @alarm_enabled.setter
    def alarm_enabled(self, enabled: bool):
        """Set the UPS alarm enablement (as run by `pwrstat -alarm [on/off]`).
        :param enabled: Specify whether to enable or disable the UPS alarm.
        :raises: SetupFailed: If alarm enablement could not be setup.
        """
        self._check_setup(self._reader.read(["-alarm", _on_off(enabled)]))

    def mute(self):
        """Setup temporally mute alarm when alarm is on enable state (as run by `pwrstat -mute`).
        :raises: Unreachable: If the UPS is not reachable.
        :raises: SetupFailed: If alarm enablement could not be muted.
        """
        self._check_setup(self._reader.read(["-mute"]))

    def _configure_action(
        self,
        action: str,
        delay: Optional[timedelta] = None,
        runtime: Optional[timedelta] = None,
        capacity: Optional[float] = None,
        active: Optional[bool] = None,
        cmd: Optional[Union[str, Path]] = None,
        duration: Optional[timedelta] = None,
        shutdown: Optional[bool] = None,
    ):
        args = [action]
        if delay is not None:
            args += ["-delay", str(int(delay.total_seconds()))]
        if runtime is not None:
            args += ["-runtime", str(int(runtime.total_seconds()))]
        if capacity is not None:
            args += ["-capacity", str(int(_check_percent(capacity) * 100.0))]
        if active is not None:
            args += ["-active", _on_off(active)]
        if cmd is not None:
            args += ["-cmd", str(cmd)]
        if duration is not None:
            args += ["-duration", str(int(duration.total_seconds()))]
        if shutdown is not None:
            args += ["-shutdown", _on_off(shutdown)]
        self._check_setup(self._reader.read(args))

    def configure_power_failure_action(
        self,
        script_command_enabled: Optional[bool] = None,
        delay_time_since_power_failure: Optional[timedelta] = None,
        script_command_duration: Optional[timedelta] = None,
        script_command_path: Optional[Union[str, Path]] = None,
        system_shutdown_enabled: Optional[bool] = None,
    ):
        """Configure the daemon power failure action (as run by `pwrstat -pwrfail ...args`). Only specify the
            arguments you wish to override.
        :param script_command_enabled: (-active*1) Setup command-execution or not when event occurred.
        :param delay_time_since_power_failure: (-delay*1) Setup delay seconds when event occurred.
        :param script_command_duration: (-duration*1) Setup duration seconds of command-execution when event occurred.
        :param script_command_path: (-cmd*1) Assign command file when event occurred.
        :param system_shutdown_enabled: (-shutdown*1) Setup shutdown OS or not when event occurred.
        :return: Power failure action after re-configuration.
        :raises: SetupFailed: If power failure action could not be re-configured.
        """
        self._configure_action(
            action="-pwrfail",
            active=script_command_enabled,
            delay=delay_time_since_power_failure,
            duration=script_command_duration,
            cmd=script_command_path,
            shutdown=system_shutdown_enabled,
        )

    def configure_low_battery_action(
        self,
        script_command_enabled: Optional[bool] = None,
        remaining_runtime_threshold: Optional[timedelta] = None,
        battery_capacity_threshold_percent: Optional[float] = None,
        script_command_duration: Optional[timedelta] = None,
        script_command_path: Optional[Union[str, Path]] = None,
        system_shutdown_enabled: Optional[bool] = None,
    ) -> None:
        """Configure the daemon low battery action (as run by `pwrstat -lowbatt ...args`). Only specify the arguments
            you wish to override.
        :param script_command_enabled: (-active*1) Setup command-execution or not when event occurred.
        :param remaining_runtime_threshold: (-runtime*1) Setup remaining runtime threshold to identify low battery
            event.
        :param battery_capacity_threshold_percent: (-capacity*1) Setup low battery capacity threshold to identify low
            battery event. This value is expected to be a float between 0.0 (0%) and 1.0 (100%).
        :param script_command_duration: (-duration*1) Setup duration seconds of command-execution when event occurred.
        :param script_command_path: (-cmd*1) Assign command file when event occurred.
        :param system_shutdown_enabled: (-shutdown*1) Setup shutdown OS or not when event occurred.
        :raises: SetupFailed: If power failure action could not be re-configured.
        """
        self._configure_action(
            action="-lowbatt",
            active=script_command_enabled,
            runtime=remaining_runtime_threshold,
            capacity=battery_capacity_threshold_percent,
            duration=script_command_duration,
            cmd=script_command_path,
            shutdown=system_shutdown_enabled,
        )

    def configure_cloud(
        self,
        enabled: Optional[bool] = None,
        account: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Configure the settings for cloud solution (as run by `pwrstat -cloud ...args`).
        :param enabled: (-active*2) Activate or deactivate cloud solution.
        :param account: (-account*2) Cloud account.
        :param password: (-password*2) Cloud password.
        :raises: SetupFailed: If power failure action could not be re-configured.
        """
        args = ["-cloud"]
        if enabled is not None:
            args += ["-active", _on_off(enabled)]
        if account is not None:
            args += ["-account", account]
        if password is not None:
            args += ["-password", password]
        self._check_setup(self._reader.read(args))

    def verify_cloud_configuration(self) -> bool:
        """Verify PowerPanel can log in to cloud server (as run by `pwrstat -verify`).
        :return: `True` if the verification passed, `False` otherwise.
        """
        output = self._reader.read(["-verify"])
        return "Verify failed" not in output

    @classmethod
    def _check_setup(cls, output: str):
        if not output.startswith("Setup configuration successful"):
            raise SetupFailed(f"Setup failed. Full pwrstat output: {output}")
