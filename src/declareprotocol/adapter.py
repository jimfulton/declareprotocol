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

    @classmethod
    def _normalize_lookup_required(
        cls,
        required: typing.Iterable[LookupRequirement],
    ) -> tuple[Declaration, ...]:
        normalized: list[Declaration] = []
        for requirement in required:
            if isinstance(requirement, tuple):
                declaration = requirement
            else:
                cls._validate_protocol(requirement)
                declaration = (requirement,)
            for protocol in declaration:
                cls._validate_protocol(protocol)
            normalized.append(declaration)
        return tuple(normalized)

    @staticmethod
    def _provided_score(
        registered: Protocol,
        requested: Protocol,
    ) -> tuple[int, int] | None:
        try:
            distance = registered.__mro__.index(requested)
        except ValueError:
            return None
        return (0 if distance == 0 else 1, distance)

    @staticmethod
    def _required_score(
        registered: Required,
        declaration: Declaration,
    ) -> tuple[int, int, int] | None:
        if registered is None:
            return (2, 0, 0)

        matches: list[tuple[int, int, int]] = []
        for declaration_index, protocol in enumerate(declaration):
            try:
                distance = protocol.__mro__.index(registered)
            except ValueError:
                continue
            matches.append(
                (
                    0 if distance == 0 else 1,
                    distance,
                    declaration_index,
                )
            )
        return min(matches, default=None)

    @classmethod
    def _score(
        cls,
        registration: _Registration,
        required: tuple[Declaration, ...],
        provided: Protocol,
        name: str,
    ) -> tuple[tuple[int, int], tuple[tuple[int, int, int], ...]] | None:
        if registration.name != name or len(registration.required) != len(required):
            return None

        provided_score = cls._provided_score(registration.provided, provided)
        if provided_score is None:
            return None

        required_scores: list[tuple[int, int, int]] = []
        for registered, declaration in zip(registration.required, required):
            score = cls._required_score(registered, declaration)
            if score is None:
                return None
            required_scores.append(score)
        return provided_score, tuple(required_scores)

    def lookup(
        self,
        required: typing.Iterable[LookupRequirement],
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        normalized = self._normalize_lookup_required(required)
        self._validate_protocol(provided)
        self._validate_name(name)
        matches = (
            (score, registration.value)
            for registration in self._registrations
            if (
                score := self._score(
                    registration,
                    normalized,
                    provided,
                    name,
                )
            )
            is not None
        )
        return min(matches, default=((), default), key=lambda match: match[0])[1]

    def lookup1(
        self,
        required: LookupRequirement,
        provided: Protocol,
        name: str = "",
        default: object = None,
    ) -> object:
        return self.lookup((required,), provided, name, default)
