import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Union


@dataclass(frozen=True)
class PowerEvent:
    """Power event"""

    event_type: str
    event_time: datetime
    duration: timedelta


class TestStatus(enum.Enum):
    """Test status"""

    InProgress = "In Progress"
    Passed = "Passed"
    Failed = "Failed"


@dataclass(frozen=True)
class TestResult:
    """Test result"""

    status: TestStatus
    test_time: Optional[datetime]


@dataclass(frozen=True)
class UPSStatus:
    """UPS Status"""

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


@dataclass(frozen=True)
class UPSProperties:
    """UPS Properties"""

    model_name: str
    firmware_number: str
    rating_voltage_volts: float
    rating_power_watts: float


@dataclass(frozen=True)
class PowerFailureAction:
    """Power failure action"""

    delay_time_since_power_failure: timedelta
    script_command_enabled: bool
    script_command_path: Path
    script_command_duration: timedelta
    system_shutdown_enabled: bool


@dataclass(frozen=True)
class LowBatteryAction:
    """Low battery action"""

    remaining_runtime_threshold: timedelta
    battery_capacity_threshold_percent: float
    script_command_enabled: bool
    script_command_path: Path
    script_command_duration: timedelta
    system_shutdown_enabled: bool


@dataclass(frozen=True)
class DaemonConfiguration:
    """Daemon configuration"""

    alarm_enabled: bool
    hibernate_enabled: bool
    cloud_enabled: bool
    power_failure_action: PowerFailureAction
    low_battery_action: LowBatteryAction


@dataclass
class ValueChanged:
    """Type of event metadata indicating a change in one of the UPS status fields"""

    field_name: str
    new_value: Any
    previous_value: Any


@dataclass
class ReachabilityChanged:
    """Type of event metadata indicating a change in the UPS reachability"""

    reachable: bool


EventMetadataType = Union[ValueChanged, ReachabilityChanged]


@dataclass
class Event:
    """UPS event (change while monitoring the UPS status)"""

    event_metadata: EventMetadataType
    new_state: Optional[UPSStatus]
    previous_state: Optional[UPSStatus]
