from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


ALLOWED_SEVERITIES = ("INFO", "WARNING", "ERROR", "FATAL")


@dataclass(frozen=True)
class ValidationMessage:
    identifier: str
    file: str
    rule: str
    description: str
    severity: str

    def to_dict(self) -> dict[str, str]:
        return {
            "identifier": self.identifier,
            "file": self.file,
            "rule": self.rule,
            "description": self.description,
            "severity": self.severity,
        }


@dataclass
class ValidatorResult:
    validator: str
    status: str = "passed"
    severity: str = "INFO"
    checked: int = 0
    passed: int = 0
    failed: int = 0
    duration: float = 0.0
    messages: list[ValidationMessage] = field(default_factory=list)

    def add_message(self, *, identifier: str, file: str, rule: str, description: str, severity: str) -> None:
        sev = severity.upper()
        if sev not in ALLOWED_SEVERITIES:
            raise ValueError(f"invalid severity: {sev}")
        self.messages.append(
            ValidationMessage(
                identifier=identifier,
                file=file,
                rule=rule,
                description=description,
                severity=sev,
            )
        )

    def finalize(self) -> None:
        self.messages.sort(
            key=lambda m: (
                m.file,
                m.identifier,
                m.rule,
                m.description,
                m.severity,
            )
        )
        self.failed = len([m for m in self.messages if m.severity in {"ERROR", "FATAL"}])
        self.passed = max(0, self.checked - self.failed)
        self.status = "passed" if self.failed == 0 else "failed"

        if any(m.severity == "FATAL" for m in self.messages):
            self.severity = "FATAL"
        elif any(m.severity == "ERROR" for m in self.messages):
            self.severity = "ERROR"
        elif any(m.severity == "WARNING" for m in self.messages):
            self.severity = "WARNING"
        else:
            self.severity = "INFO"

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator": self.validator,
            "status": self.status,
            "severity": self.severity,
            "checked": self.checked,
            "passed": self.passed,
            "failed": self.failed,
            "duration": self.duration,
            "messages": [m.to_dict() for m in self.messages],
        }


@dataclass
class TransitionValidationReport:
    transition: str
    status: str = "passed"
    validators: dict[str, ValidatorResult] = field(default_factory=dict)

    def add_validator_result(self, result: ValidatorResult) -> None:
        result.finalize()
        self.validators[result.validator] = result
        if result.severity in {"ERROR", "FATAL"}:
            self.status = "failed"

    def has_errors(self) -> bool:
        return any(v.severity in {"ERROR", "FATAL"} for v in self.validators.values())

    def has_fatal(self) -> bool:
        return any(v.severity == "FATAL" for v in self.validators.values())

    def warning_count(self) -> int:
        return sum(len([m for m in v.messages if m.severity == "WARNING"]) for v in self.validators.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition": self.transition,
            "status": self.status,
            "validators": {k: v.to_dict() for k, v in sorted(self.validators.items(), key=lambda t: t[0])},
        }
