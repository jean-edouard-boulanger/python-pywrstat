from dataclasses import dataclass
from textwrap import dedent
from typing import List, Optional

from pywrstat.client import _on_off
from pywrstat.reader import ReaderBase


@dataclass
class FakeCall:
    args: List[str]
    output: Optional[str]
    raises: Optional[Exception]

    def __post_init__(self):
        if self.output is None and self.raises is None:
            raise ValueError("output or raises must be set")


class FakeReader(ReaderBase):
    def __init__(self):
        self._expected_calls: List[FakeCall] = []
        self._previous_calls: List[FakeCall] = []

    def assert_no_more_calls(self):
        assert len(self._expected_calls) == 0

    def read(self, args: List[str]) -> str:
        assert len(self._expected_calls) > 0, (
            f"FakeReader did not expect to be called any more, was called with"
            f" `{args}` instead (call number {len(self._previous_calls) + 1})"
        )
        call = self._expected_calls.pop(0)
        assert call.args == args, (
            f"FakeReader expected to be called with `{call.args}`, was called with"
            f" `{args}` instead (call number {len(self._previous_calls) + 1})"
        )
        self._previous_calls.append(call)
        if call.raises:
            raise call.raises
        assert call.output is not None
        return call.output

    def expect_status_call_unreachable(
        self,
        model_name: str = "CP1500EPFCLCD",
        firmware_number: str = "CR01505B481",
        rating_voltage: int = 230,
        rating_power: int = 900,
        ups_test_result: str = "Passed at 2022/07/21 16:16:42",
        ups_last_power_event: str = "Blackout at 2022/07/21 15:10:43 for 24 sec.",
    ):
        self._expected_calls.append(
            FakeCall(
                args=["-status"],
                output=dedent(
                    f"""
                    The UPS information shows as following:
    
                        Properties:
                            Model Name................... {model_name}
                            Firmware Number.............. {firmware_number}
                            Rating Voltage............... {rating_voltage} V
                            Rating Power................. {rating_power} Watt
    
                        Current UPS status:
                            State........................ Lost Communication
                            Test Result.................. {ups_test_result}
                            Last Power Event............. {ups_last_power_event}
                    """
                ),
                raises=None,
            )
        )

    def expect_status_call(
        self,
        model_name: str = "CP1500EPFCLCD",
        firmware_number: str = "CR0XXXXXXX",
        rating_voltage: int = 230,
        rating_power: int = 900,
        ups_state: str = "Normal",
        ups_power_supply: str = "Utility Power",
        ups_utility_voltage: int = 230,
        ups_output_voltage: int = 230,
        ups_battery_capacity: int = 100,
        ups_remaining_runtime: int = 129,
        ups_load_watts: int = 9,
        ups_line_interaction: str = "None",
        ups_test_result: str = "Passed at 2022/07/21 16:16:42",
        ups_last_power_event: str = "Blackout at 2022/07/21 15:10:43 for 24 sec.",
    ):
        self._expected_calls.append(
            FakeCall(
                args=["-status"],
                output=dedent(
                    f"""
                    The UPS information shows as following:
    
                        Properties:
                            Model Name................... {model_name}
                            Firmware Number.............. {firmware_number}
                            Rating Voltage............... {rating_voltage} V
                            Rating Power................. {rating_power} Watt
    
                        Current UPS status:
                            State........................ {ups_state}
                            Power Supply by.............. {ups_power_supply}
                            Utility Voltage.............. {ups_utility_voltage} V
                            Output Voltage............... {ups_output_voltage} V
                            Battery Capacity............. {ups_battery_capacity} %
                            Remaining Runtime............ {ups_remaining_runtime} min.
                            Load......................... {ups_load_watts} Watt({int((ups_load_watts / rating_power) * 100)} %)
                            Line Interaction............. {ups_line_interaction}
                            Test Result.................. {ups_test_result}
                            Last Power Event............. {ups_last_power_event}
                    """
                ),
                raises=None,
            )
        )

    def expect_config_call(
        self,
        alarm_enabled: bool = True,
        hibernate_enabled: bool = False,
        cloud_enabled: bool = False,
        pf_action_delay_seconds: int = 600,
        pf_action_script_enabled: bool = True,
        pf_action_script_command_path: str = "/etc/pwrstatd-powerfail.sh",
        pf_action_script_duration_seconds: int = 0,
        pf_action_system_shutdown_enabled: bool = True,
        bl_action_runtime_threshold_seconds: int = 600,
        bl_action_battery_capacity_threshold: int = 35,
        bl_action_script_enabled: bool = True,
        bl_action_script_command_path: str = "/etc/pwrstatd-lowbatt.sh",
        bl_action_script_duration_seconds: int = 0,
        bl_action_system_shutdown_enabled: bool = True,
    ):
        self._expected_calls.append(
            FakeCall(
                args=["-config"],
                output=dedent(
                    f"""
                    Daemon Configuration:
                    
                    Alarm .............................................. {_on_off(alarm_enabled).capitalize()}
                    Hibernate .......................................... {_on_off(hibernate_enabled).capitalize()}
                    Cloud .............................................. {_on_off(cloud_enabled).capitalize()}
                    
                    Action for Power Failure:
                    
                        Delay time since Power failure ............. {pf_action_delay_seconds} sec.
                        Run script command ......................... {_on_off(pf_action_script_enabled).capitalize()}
                        Path of script command ..................... {pf_action_script_command_path}
                        Duration of command running ................ {pf_action_script_duration_seconds} sec.
                        Enable shutdown system ..................... {_on_off(pf_action_system_shutdown_enabled).capitalize()}
                    
                    Action for Battery Low:
                    
                        Remaining runtime threshold ................ {bl_action_runtime_threshold_seconds} sec.
                        Battery capacity threshold ................. {bl_action_battery_capacity_threshold} %.
                        Run script command ......................... {_on_off(bl_action_script_enabled).capitalize()}
                        Path of command ............................ {bl_action_script_command_path}
                        Duration of command running ................ {bl_action_script_duration_seconds} sec.
                        Enable shutdown system ..................... {_on_off(bl_action_system_shutdown_enabled).capitalize()}
                    """
                ),
                raises=None,
            )
        )

    def expect_version_call(self, pwrstat_version: str = "1.4.1"):
        self._expected_calls.append(
            FakeCall(
                args=["-version"],
                output=dedent(
                    f"""
                    version:
                    pwrstat version {pwrstat_version}
                    """
                ),
                raises=None,
            )
        )

    def expect_test_call(self):
        self._expected_calls.append(
            FakeCall(
                args=["-test"],
                output=dedent(
                    """
                    The UPS test is initiated, checking the result by command "pwrstat -status".
                    """
                ),
                raises=None,
            )
        )

    def expect_call(
        self,
        args: List[str],
        output: Optional[str] = None,
        raises: Optional[Exception] = None,
    ):
        self._expected_calls.append(FakeCall(args, output, raises))
