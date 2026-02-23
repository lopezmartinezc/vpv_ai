from __future__ import annotations


class VPVError(Exception):
    def __init__(self, message: str, code: str = "UNKNOWN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(VPVError):
    def __init__(self, resource: str, identifier: str | int) -> None:
        super().__init__(
            message=f"{resource} con id={identifier} no encontrado",
            code="NOT_FOUND",
        )


class BusinessRuleError(VPVError):
    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="BUSINESS_RULE_VIOLATION")


class AuthorizationError(VPVError):
    def __init__(self, message: str = "No autorizado") -> None:
        super().__init__(message=message, code="UNAUTHORIZED")
