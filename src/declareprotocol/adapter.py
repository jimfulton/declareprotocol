import dataclasses
import typing

from . import declarations

__all__ = ["AdapterRegistry"]

Protocol = type[object]
Required = Protocol | None
Declaration = tuple[Protocol, ...]
LookupRequirement = Protocol | Declaration


@dataclasses.dataclass
class _Registration:
    required: tuple[Required, ...]
    provided: Protocol
    name: str
    value: object


class AdapterRegistry:
    def __init__(self) -> None:
        self._registrations: list[_Registration] = []

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str):
            raise ValueError("name is not a string")  # noqa: TRY004

    @staticmethod
    def _validate_protocol(protocol: object) -> None:
        if not declarations._is_protocol_class(protocol):
            raise TypeError(f"{protocol!r} is not a Protocol class")

    @classmethod
    def _normalize_registered_required(
        cls,
        required: typing.Iterable[Required],
    ) -> tuple[Required, ...]:
        normalized = tuple(required)
        for protocol in normalized:
            if protocol is not None:
                cls._validate_protocol(protocol)
        return normalized

    @classmethod
    def _registration_key(
        cls,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str,
    ) -> tuple[tuple[Required, ...], Protocol, str]:
        normalized = cls._normalize_registered_required(required)
        cls._validate_protocol(provided)
        cls._validate_name(name)
        return normalized, provided, name

    def register(
        self,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str,
        value: object,
    ) -> None:
        key = self._registration_key(required, provided, name)
        for index, registration in enumerate(self._registrations):
            if (
                registration.required,
                registration.provided,
                registration.name,
            ) != key:
                continue
            if value is None:
                del self._registrations[index]
            else:
                registration.value = value
            return

        if value is not None:
            self._registrations.append(_Registration(*key, value))

    def unregister(
        self,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str,
        value: object = None,
    ) -> bool:
        key = self._registration_key(required, provided, name)
        for index, registration in enumerate(self._registrations):
            if (
                registration.required,
                registration.provided,
                registration.name,
            ) != key:
                continue
            if value is not None and registration.value is not value:
                return False
            del self._registrations[index]
            return True
        return False

    def registered(
        self,
        required: typing.Iterable[Required],
        provided: Protocol,
        name: str = "",
    ) -> object | None:
        key = self._registration_key(required, provided, name)
        for registration in self._registrations:
            if (
                registration.required,
                registration.provided,
                registration.name,
            ) == key:
                return registration.value
        return None

    def lookup(
        self,
        required: typing.Iterable[LookupRequirement],
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        self._validate_protocol(provided)
        self._validate_name(name)
        return default
