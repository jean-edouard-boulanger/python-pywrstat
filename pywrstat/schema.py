import enum
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel as _BaseModel


class BaseModel(_BaseModel):
    class Config:
        frozen = True


class PowerEvent(BaseModel):
    event_type: str
    event_time: datetime
    duration: timedelta


class TestStatus(enum.Enum):
    InProgress = "In Progress"
    Passed = "Passed"
    Failed = "Failed"


class TestResult(BaseModel):
    status: TestStatus
    test_time: Optional[datetime]


class UPSStatus(BaseModel):
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


class UPSProperties(BaseModel):
    ups_model_name: str
    firmware_number: str
    rating_voltage_volts: float
    rating_power_watts: float


class PowerFailureAction(BaseModel):
    delay_time_since_power_failure: timedelta
    script_command_enabled: bool
    script_command_path: Path
    script_command_duration: timedelta
    system_shutdown_enabled: bool


class LowBatteryAction(BaseModel):
    remaining_runtime_threshold: timedelta
    battery_capacity_threshold_percent: float
    script_command_enabled: bool
    script_command_path: Path
    script_command_duration: timedelta
    system_shutdown_enabled: bool


class DaemonConfiguration(BaseModel):
    alarm_enabled: bool
    hibernate_enabled: bool
    cloud_enabled: bool
    power_failure_action: PowerFailureAction
    low_battery_action: LowBatteryAction


class ValueChangedEvent(BaseModel):
    event_type: Literal["value_changed"] = "value_changed"
    field_name: str
    new_value: Any
    previous_value: Any


class ReachabilityChangedEvent(BaseModel):
    event_type: Literal["reachability_changed"] = "reachability_changed"
    reachable: bool


EventType = Union[ValueChangedEvent, ReachabilityChangedEvent]


class Events(BaseModel):
    events: list[EventType]
    new_state: Optional[UPSStatus]
    previous_state: Optional[UPSStatus]
