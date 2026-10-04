from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    employeeId: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    role: Literal["admin", "operator"] | None = None


class RegistrationRequest(BaseModel):
    employeeId: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=256)


class UserDocument(BaseModel):
    employee_id: str
    name: str
    role: Literal["admin", "operator"]
    password_hash: str
    machines: list[str] = Field(default_factory=list)
    active: bool = True
    session_active: bool = False
    created_at: datetime


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["admin", "operator"] | None = None
    machines: list[str] | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    machine_id: str = Field(min_length=1, max_length=80)
    assigned_to: str = Field(min_length=1, max_length=80)
    due_date: date | None = None


class TaskStatusUpdate(BaseModel):
    status: Literal["Pending", "In Progress", "Completed"]


class ReportRequest(BaseModel):
    type: Literal["Energy", "Machine", "Sustainability", "Maintenance", "Anomalies"]
    machineId: str = "all"
    range: dict
    tariff: float = Field(default=8.5, ge=0)


class PublicUser(BaseModel):
    id: str
    name: str
    role: Literal["admin", "operator"]
    machines: list[str] = Field(default_factory=list)


class TokenResponse(BaseModel):
    token: str
    user: PublicUser


class MachineCreate(BaseModel):
    machine_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    status: str = Field(default="active", max_length=40)
    plant: str | None = Field(default=None, max_length=120)
    machine_type: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    rated_power: float | None = Field(default=None, gt=0)
    power: float | None = Field(default=None, ge=0)
    units_per_hour: float | None = Field(default=None, gt=0)
    operational_constraint: str | None = Field(default=None, max_length=80)
    power_factor: float | None = Field(default=None, ge=0, le=1)
    temperature: float | None = None
    baseline_temp: float | None = None
    baseline_kwh_per_unit: float | None = Field(default=None, gt=0)
    ml_asset_id: str | None = Field(default=None, max_length=80)


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = Field(default=None, max_length=40)
    plant: str | None = Field(default=None, max_length=120)
    machine_type: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=120)
    rated_power: float | None = Field(default=None, gt=0)
    power: float | None = Field(default=None, ge=0)
    units_per_hour: float | None = Field(default=None, gt=0)
    operational_constraint: str | None = Field(default=None, max_length=80)
    power_factor: float | None = Field(default=None, ge=0, le=1)
    temperature: float | None = None
    baseline_temp: float | None = None
    baseline_kwh_per_unit: float | None = Field(default=None, gt=0)
    ml_asset_id: str | None = Field(default=None, max_length=80)


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    machine_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    protocol: str = Field(default="HTTP API", max_length=40)


class DeviceUpdate(BaseModel):
    machine_id: str | None = Field(default=None, min_length=1, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    protocol: str | None = Field(default=None, max_length=40)
    enabled: bool | None = None


class TelemetryCreate(BaseModel):
    machine_id: str = Field(min_length=1, max_length=80)
    device_id: str | None = Field(default=None, max_length=100)
    power_kw: float = Field(ge=0)
    power_factor: float = Field(ge=0, le=1)
    temperature: float = Field(ge=-50, le=300)
    voltage: float | None = Field(default=None, ge=0, le=1000)
    current: float | None = Field(default=None, ge=0, le=100000)
    energy_kwh: float | None = Field(default=None, ge=0)
    source: str = Field(default="manual_test", max_length=40)
    timestamp: datetime | None = None


class AlertCreate(BaseModel):
    machine_id: str = Field(min_length=1, max_length=80)
    rule_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=1000)
    severity: Literal["warning", "critical"] = "warning"
    reading: dict = Field(default_factory=dict)


class AlertUpdate(BaseModel):
    status: Literal["Open", "Acknowledged", "In Progress", "Resolved"] | None = None
    assigned_to: str | None = Field(default=None, max_length=80)


class RequestCreate(BaseModel):
    m: str = Field(min_length=1, max_length=80)
    type: Literal["stop", "eco"]
    reason: str = Field(min_length=1, max_length=500)
    obs: list[str] = Field(default_factory=list, max_items=20)
    fb: str = Field(default="", max_length=1000)
    acts: list[str] = Field(default_factory=list, max_items=20)


class RequestStatusUpdate(BaseModel):
    status: Literal["Approved", "Changes Requested", "Rejected", "Completed"]

