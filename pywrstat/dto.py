import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class PowerEvent:
    event_type: str
    event_time: datetime
    duration: timedelta


class TestStatus(enum.Enum):
    InProgress = "In Progress"
    Passed = "Passed"
    Failed = "Failed"


@dataclass
class TestResult:
    status: TestStatus
    test_time: Optional[datetime]


@dataclass
class UPSStatus:
    state: str
    power_supply_by: str
    utility_voltage_volts: float
    output_voltage_volts: float
    battery_capacity_percent: float
    remaining_runtime: timedelta
    load_watts: float
    load_percent: float
    line_interaction: str
    test_result: Optional[TestResult]
    last_power_event: Optional[PowerEvent]


@dataclass
class UPSProperties:
    model_name: str
    firmware_number: str
    rating_voltage_volts: float
    rating_power_watts: float


@dataclass
class PowerFailureAction:
    delay_time_since_power_failure: timedelta
    script_command_enabled: bool
    script_command_path: Path
    script_command_duration: timedelta
    system_shutdown_enabled: bool


@dataclass
class LowBatteryAction:
    remaining_runtime_threshold: timedelta
    battery_capacity_threshold_percent: float
    script_command_enabled: bool
    script_command_path: Path
    script_command_duration: timedelta
    system_shutdown_enabled: bool


@dataclass
class DaemonConfiguration:
    alarm_enabled: bool
    hibernate_enabled: bool
    cloud_enabled: bool
    power_failure_action: PowerFailureAction
    low_battery_action: LowBatteryAction
