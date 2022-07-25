import dataclasses
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent
from unittest.mock import call, patch

import pytest

from pywrstat import (
    DaemonConfiguration,
    LowBatteryAction,
    NotReady,
    PowerEvent,
    PowerFailureAction,
    Pywrstat,
    ReachabilityChanged,
    TestResult,
    TestStatus,
    UPSProperties,
    UPSStatus,
    ValueChanged,
)
from pywrstat.client import (
    _check_percent,
    _is_ups_reachable,
    _parse_load_percent,
    _parse_low_battery_action,
    _parse_on_off,
    _parse_power_event,
    _parse_power_failure_action,
    _parse_pwrstat_output,
    _parse_test_result,
)

from .conftest import does_not_raise, pretty_dump
from .fake_reader import FakeReader

TestResult.__test__ = False  # type: ignore
TestStatus.__test__ = False  # type: ignore


@pytest.fixture(scope="function")
def reader_mock():
    yield FakeReader()


@pytest.fixture(scope="function")
def pywrstat_client(reader_mock: FakeReader):
    yield Pywrstat(reader=reader_mock)


def test_parse_pwrstat_output():
    sample_output = dedent(
        """
        The UPS information shows as following:
        
            Properties:
                Model Name................... CP1500EPFCLCD
                Firmware Number.............. CR01XXXXXX
                Rating Voltage............... 230 V
                Rating Power................. 900 Watt
        
            Current UPS status:
                State........................ Lost Communication
                Test Result.................. Passed at 2022/07/21 16:16:42
                Last Power Event............. Blackout at 2022/07/21 15:10:43 for 24 sec.
    """
    ).strip()
    assert _parse_pwrstat_output(sample_output) == {
        "Properties": {
            "Model Name": "CP1500EPFCLCD",
            "Firmware Number": "CR01XXXXXX",
            "Rating Voltage": "230 V",
            "Rating Power": "900 Watt",
        },
        "Current UPS status": {
            "State": "Lost Communication",
            "Test Result": "Passed at 2022/07/21 16:16:42",
            "Last Power Event": "Blackout at 2022/07/21 15:10:43 for 24 sec.",
        },
    }


def test_parse_load_percent():
    assert _parse_load_percent("27 Watt(3 %)") == 0.03


@pytest.mark.parametrize(
    "raw_test_result, expected_test_result",
    [
        ("None", None),
        ("In progress", TestResult(status=TestStatus.InProgress, test_time=None)),
        (
            "Passed at 2022/07/21 17:13:45",
            TestResult(
                status=TestStatus.Passed,
                test_time=datetime(
                    year=2022, month=7, day=21, hour=17, minute=13, second=45
                ),
            ),
        ),
        (
            "Failed at 2022/02/10 11:09:32",
            TestResult(
                status=TestStatus.Failed,
                test_time=datetime(
                    year=2022, month=2, day=10, hour=11, minute=9, second=32
                ),
            ),
        ),
    ],
)
def test_parse_test_result(raw_test_result: str, expected_test_result: TestResult):
    assert _parse_test_result(raw_test_result) == expected_test_result


@pytest.mark.parametrize(
    "raw_power_event, expected_power_event",
    [
        ("None", None),
        (
            "Blackout at 2022/07/21 17:13:45 for 15 sec.",
            PowerEvent(
                event_type="Blackout",
                event_time=datetime(
                    year=2022, month=7, day=21, hour=17, minute=13, second=45
                ),
                duration=timedelta(seconds=15),
            ),
        ),
        (
            "Over Voltage at 2022/02/10 11:09:32 for 642 sec.",
            PowerEvent(
                event_type="Over Voltage",
                event_time=datetime(
                    year=2022, month=2, day=10, hour=11, minute=9, second=32
                ),
                duration=timedelta(seconds=642),
            ),
        ),
    ],
)
def test_parse_power_event(raw_power_event: str, expected_power_event: PowerEvent):
    assert _parse_power_event(raw_power_event) == expected_power_event


@pytest.mark.parametrize(
    "state, expected_reachable", [("Normal", True), ("Lost Communication", False)]
)
def test_is_ups_reachable(state: str, expected_reachable: bool):
    assert _is_ups_reachable({"State": state}) is expected_reachable


@pytest.mark.parametrize(
    "percent_value, expectation",
    [
        (0.0, does_not_raise()),
        (0.5, does_not_raise()),
        (1.0, does_not_raise()),
        (0, pytest.raises(ValueError)),
        (1, pytest.raises(ValueError)),
        (-1.0, pytest.raises(ValueError)),
        (100, pytest.raises(ValueError)),
        (50.0, pytest.raises(ValueError)),
    ],
)
def test_check_percent(percent_value, expectation):
    with expectation:
        _check_percent(percent_value)


@pytest.mark.parametrize(
    "raw_on_off, expected_enabled",
    [
        ("on", True),
        ("On", True),
        ("ON", True),
        ("oN", True),
        ("off", False),
        ("Off", False),
        ("OFF", False),
    ],
)
def _test_parse_on_off(raw_on_off: str, expected_enabled: bool):
    assert _parse_on_off(raw_on_off) is expected_enabled


def test_parse_power_failure_action():
    data = {
        "Delay time since Power failure": "600 sec.",
        "Run script command": "Off",
        "Path of script command": "/etc/pwrstatd-powerfail.sh",
        "Duration of command running": "60 sec.",
        "Enable shutdown system": "On",
    }
    assert _parse_power_failure_action(data) == PowerFailureAction(
        delay_time_since_power_failure=timedelta(seconds=600),
        script_command_enabled=False,
        script_command_path=Path("/etc/pwrstatd-powerfail.sh"),
        script_command_duration=timedelta(seconds=60),
        system_shutdown_enabled=True,
    )


def test_parse_low_battery_action():
    data = {
        "Remaining runtime threshold": "200 sec.",
        "Battery capacity threshold": "35 %",
        "Run script command": "On",
        "Path of command": "/etc/pwrstatd-lowbatt.sh",
        "Duration of command running": "0 sec.",
        "Enable shutdown system": "Off",
    }
    assert _parse_low_battery_action(data) == LowBatteryAction(
        remaining_runtime_threshold=timedelta(seconds=200),
        battery_capacity_threshold_percent=0.35,
        script_command_enabled=True,
        script_command_path=Path("/etc/pwrstatd-lowbatt.sh"),
        script_command_duration=timedelta(seconds=0),
        system_shutdown_enabled=False,
    )


def test_is_reachable_when_reachable(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_status_call()
    assert pywrstat_client.is_reachable()


def test_is_reachable_when_unreachable(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_status_call_unreachable()
    assert not pywrstat_client.is_reachable()


def test_get_pwrstat_version(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_version_call(pwrstat_version="1.2.3")
    assert pywrstat_client.get_pwrstat_version() == "1.2.3"
    reader_mock.assert_no_more_calls()


def test_get_raw_daemon_configuration(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_config_call()
    assert pretty_dump(pywrstat_client.get_raw_daemon_configuration()) == pretty_dump(
        {
            "Daemon Configuration": {"Alarm": "On", "Hibernate": "Off", "Cloud": "Off"},
            "Action for Power Failure": {
                "Delay time since Power failure": "600 sec.",
                "Run script command": "On",
                "Path of script command": "/etc/pwrstatd-powerfail.sh",
                "Duration of command running": "0 sec.",
                "Enable shutdown system": "On",
            },
            "Action for Battery Low": {
                "Remaining runtime threshold": "600 sec.",
                "Battery capacity threshold": "35 %.",
                "Run script command": "On",
                "Path of command": "/etc/pwrstatd-lowbatt.sh",
                "Duration of command running": "0 sec.",
                "Enable shutdown system": "On",
            },
        }
    )
    reader_mock.assert_no_more_calls()


def test_get_daemon_configuration(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_config_call()
    assert pywrstat_client.get_daemon_configuration() == DaemonConfiguration(
        alarm_enabled=True,
        hibernate_enabled=False,
        cloud_enabled=False,
        power_failure_action=PowerFailureAction(
            delay_time_since_power_failure=timedelta(seconds=600),
            script_command_enabled=True,
            script_command_path=Path("/etc/pwrstatd-powerfail.sh"),
            script_command_duration=timedelta(seconds=0),
            system_shutdown_enabled=True,
        ),
        low_battery_action=LowBatteryAction(
            remaining_runtime_threshold=timedelta(seconds=600),
            battery_capacity_threshold_percent=0.35,
            script_command_enabled=True,
            script_command_path=Path("/etc/pwrstatd-lowbatt.sh"),
            script_command_duration=timedelta(seconds=0),
            system_shutdown_enabled=True,
        ),
    )
    reader_mock.assert_no_more_calls()


def test_get_power_failure_action(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_config_call()
    assert pywrstat_client.get_power_failure_action() == PowerFailureAction(
        delay_time_since_power_failure=timedelta(seconds=600),
        script_command_enabled=True,
        script_command_path=Path("/etc/pwrstatd-powerfail.sh"),
        script_command_duration=timedelta(seconds=0),
        system_shutdown_enabled=True,
    )
    reader_mock.assert_no_more_calls()


def test_get_low_battery_action(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_config_call()
    assert pywrstat_client.get_low_battery_action() == LowBatteryAction(
        remaining_runtime_threshold=timedelta(seconds=600),
        battery_capacity_threshold_percent=0.35,
        script_command_enabled=True,
        script_command_path=Path("/etc/pwrstatd-lowbatt.sh"),
        script_command_duration=timedelta(seconds=0),
        system_shutdown_enabled=True,
    )
    reader_mock.assert_no_more_calls()


def test_get_raw_complete_ups_status(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_status_call()
    assert pretty_dump(pywrstat_client.get_raw_complete_ups_status()) == pretty_dump(
        {
            "Properties": {
                "Model Name": "CP1500EPFCLCD",
                "Firmware Number": "CR0XXXXXXX",
                "Rating Voltage": "230 V",
                "Rating Power": "900 Watt",
            },
            "Current UPS status": {
                "State": "Normal",
                "Power Supply by": "Utility Power",
                "Utility Voltage": "230 V",
                "Output Voltage": "230 V",
                "Battery Capacity": "100 %",
                "Remaining Runtime": "129 min.",
                "Load": "9 Watt(1 %)",
                "Line Interaction": "None",
                "Test Result": "Passed at 2022/07/21 16:16:42",
                "Last Power Event": "Blackout at 2022/07/21 15:10:43 for 24 sec.",
            },
        }
    )
    reader_mock.assert_no_more_calls()


def test_get_raw_ups_status(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_status_call()
    assert pretty_dump(pywrstat_client.get_raw_ups_status()) == pretty_dump(
        {
            "State": "Normal",
            "Power Supply by": "Utility Power",
            "Utility Voltage": "230 V",
            "Output Voltage": "230 V",
            "Battery Capacity": "100 %",
            "Remaining Runtime": "129 min.",
            "Load": "9 Watt(1 %)",
            "Line Interaction": "None",
            "Test Result": "Passed at 2022/07/21 16:16:42",
            "Last Power Event": "Blackout at 2022/07/21 15:10:43 for 24 sec.",
        }
    )
    reader_mock.assert_no_more_calls()


def test_get_ups_status(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_status_call()
    assert pywrstat_client.get_ups_status() == UPSStatus(
        state="Normal",
        power_supply_by="Utility Power",
        utility_voltage_volts=230,
        output_voltage_volts=230,
        battery_capacity_percent=1.0,
        remaining_runtime=timedelta(minutes=129),
        load_watts=9,
        load_percent=0.01,
        line_interaction="None",
        test_result=TestResult(
            status=TestStatus.Passed,
            test_time=datetime(
                year=2022, month=7, day=21, hour=16, minute=16, second=42
            ),
        ),
        last_power_event=PowerEvent(
            event_type="Blackout",
            event_time=datetime(
                year=2022, month=7, day=21, hour=15, minute=10, second=43
            ),
            duration=timedelta(seconds=24),
        ),
    )
    reader_mock.assert_no_more_calls()


@patch("time.sleep")
def test_monitor_ups_status(
    sleep_mock, pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_status_call(ups_output_voltage=230, ups_load_watts=15)
    reader_mock.expect_status_call(ups_output_voltage=230, ups_load_watts=15)
    reader_mock.expect_status_call(ups_output_voltage=235, ups_load_watts=16)
    reader_mock.expect_status_call_unreachable()
    reader_mock.expect_status_call(ups_output_voltage=229, ups_load_watts=15)

    initial_status = pywrstat_client.get_ups_status()
    event_iterator = pywrstat_client.monitor_ups_status(poll_every=timedelta(seconds=2))
    event = next(event_iterator)
    assert event.previous_state == initial_status
    assert event.new_state == dataclasses.replace(
        initial_status, output_voltage_volts=235, load_watts=16
    )
    assert event.event_metadata == ValueChanged(
        field_name="load_watts", previous_value=15, new_value=16
    )
    event = next(event_iterator)
    assert event.previous_state == initial_status
    assert event.new_state == dataclasses.replace(
        initial_status, output_voltage_volts=235, load_watts=16
    )
    assert event.event_metadata == ValueChanged(
        field_name="output_voltage_volts", previous_value=230, new_value=235
    )
    event = next(event_iterator)
    assert event.previous_state == dataclasses.replace(
        initial_status, output_voltage_volts=235, load_watts=16
    )
    assert event.new_state is None
    assert event.event_metadata == ReachabilityChanged(reachable=False)
    event = next(event_iterator)
    assert event.previous_state is None
    assert event.new_state == dataclasses.replace(
        initial_status, output_voltage_volts=229
    )
    assert event.event_metadata == ReachabilityChanged(reachable=True)
    reader_mock.assert_no_more_calls()
    sleep_mock.assert_has_calls([call(2.0), call(2.0), call(2.0)])


def test_get_raw_ups_properties(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_status_call()
    assert pretty_dump(pywrstat_client.get_raw_ups_properties()) == pretty_dump(
        {
            "Model Name": "CP1500EPFCLCD",
            "Firmware Number": "CR0XXXXXXX",
            "Rating Voltage": "230 V",
            "Rating Power": "900 Watt",
        }
    )
    reader_mock.assert_no_more_calls()


def test_get_ups_properties(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_status_call()
    assert pywrstat_client.get_ups_properties() == UPSProperties(
        model_name="CP1500EPFCLCD",
        firmware_number="CR0XXXXXXX",
        rating_voltage_volts=230,
        rating_power_watts=900,
    )
    reader_mock.assert_no_more_calls()


@pytest.mark.parametrize(
    "previous_test_result, final_test_result",
    [
        ("None", "Failed at 2022/07/21 16:16:42"),
        ("Failed at 2022/06/21 11:23:42", "Passed at 2022/07/21 16:16:42"),
        ("Failed at 2022/06/21 11:23:42", "Failed at 2022/07/21 16:16:42"),
        ("Passed at 2022/06/21 11:23:42", "Passed at 2022/07/21 16:16:42"),
    ],
)
@patch("time.sleep")
def test_test_ups_with_poll(
    sleep_mock,
    pywrstat_client: Pywrstat,
    reader_mock: FakeReader,
    previous_test_result: str,
    final_test_result: str,
):
    reader_mock.expect_status_call(ups_test_result=previous_test_result)
    reader_mock.expect_test_call()
    reader_mock.expect_status_call(ups_test_result=previous_test_result)
    reader_mock.expect_status_call(ups_test_result="In progress")
    reader_mock.expect_status_call(ups_test_result="In progress")
    reader_mock.expect_status_call(ups_test_result="In progress")
    reader_mock.expect_status_call(ups_test_result=final_test_result)
    final_result = pywrstat_client.test_ups(
        poll_result=True, poll_every=timedelta(seconds=5)
    )
    assert final_result == _parse_test_result(final_test_result)
    reader_mock.assert_no_more_calls()
    sleep_mock.assert_has_calls([call(5.0), call(5.0), call(5.0), call(5.0)])


def test_test_ups_raises_if_test_already_in_progress(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_status_call(ups_test_result="In progress")
    with pytest.raises(NotReady):
        pywrstat_client.test_ups()
    reader_mock.assert_no_more_calls()


def test_reset_daemon_configuration(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_call(["-reset"], "")
    pywrstat_client.reset_daemon_configuration()
    reader_mock.assert_no_more_calls()


@pytest.mark.parametrize("hibernate_enabled", [True, False])
def test_get_hibernation_enabled(
    pywrstat_client: Pywrstat, reader_mock: FakeReader, hibernate_enabled: bool
):
    reader_mock.expect_config_call(hibernate_enabled=hibernate_enabled)
    assert pywrstat_client.hibernation_enabled == hibernate_enabled
    reader_mock.assert_no_more_calls()


@pytest.mark.parametrize("hibernate_enabled", [True, False])
def test_set_hibernation_enabled(
    pywrstat_client: Pywrstat, reader_mock: FakeReader, hibernate_enabled: bool
):
    reader_mock.expect_call(
        ["-hibernate", "on" if hibernate_enabled else "off"],
        "Setup configuration successful.",
    )
    pywrstat_client.hibernation_enabled = hibernate_enabled
    reader_mock.assert_no_more_calls()


@pytest.mark.parametrize("alarm_enabled", [True, False])
def test_get_alarm_enabled(
    pywrstat_client: Pywrstat, reader_mock: FakeReader, alarm_enabled: bool
):
    reader_mock.expect_config_call(alarm_enabled=alarm_enabled)
    assert pywrstat_client.alarm_enabled == alarm_enabled
    reader_mock.assert_no_more_calls()


@pytest.mark.parametrize("alarm_enabled", [True, False])
def test_set_alarm_enabled(
    pywrstat_client: Pywrstat, reader_mock: FakeReader, alarm_enabled: bool
):
    reader_mock.expect_call(
        ["-alarm", "on" if alarm_enabled else "off"], "Setup configuration successful."
    )
    pywrstat_client.alarm_enabled = alarm_enabled
    reader_mock.assert_no_more_calls()


def test_mute(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_call(["-mute"], "Setup configuration successful.")
    pywrstat_client.mute()
    reader_mock.assert_no_more_calls()


def test_configure_power_failure_action(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_call(
        [
            "-pwrfail",
            "-delay",
            "600",
            "-active",
            "on",
            "-cmd",
            "/etc/pwrstatd-powerfail.sh",
            "-duration",
            "60",
            "-shutdown",
            "off",
        ],
        "Setup configuration successful.",
    )
    pywrstat_client.configure_power_failure_action(
        script_command_enabled=True,
        delay_time_since_power_failure=timedelta(minutes=10),
        script_command_duration=timedelta(seconds=60),
        script_command_path="/etc/pwrstatd-powerfail.sh",
        system_shutdown_enabled=False,
    )
    reader_mock.assert_no_more_calls()


def test_configure_low_battery_action(
    pywrstat_client: Pywrstat, reader_mock: FakeReader
):
    reader_mock.expect_call(
        [
            "-lowbatt",
            "-runtime",
            "1200",
            "-capacity",
            "50",
            "-active",
            "off",
            "-cmd",
            "/etc/pwrstatd-lowbatt.sh",
            "-duration",
            "120",
            "-shutdown",
            "on",
        ],
        "Setup configuration successful.",
    )
    pywrstat_client.configure_low_battery_action(
        script_command_enabled=False,
        remaining_runtime_threshold=timedelta(minutes=20),
        battery_capacity_threshold_percent=0.5,
        script_command_path=Path("/etc/pwrstatd-lowbatt.sh"),
        script_command_duration=timedelta(seconds=120),
        system_shutdown_enabled=True,
    )
    reader_mock.assert_no_more_calls()


def test_configure_cloud(pywrstat_client: Pywrstat, reader_mock: FakeReader):
    reader_mock.expect_call(
        ["-cloud", "-active", "on", "-account", "dummy", "-password", "123456"],
        "Setup configuration successful.",
    )
    pywrstat_client.configure_cloud(enabled=True, account="dummy", password="123456"),
    reader_mock.assert_no_more_calls()
