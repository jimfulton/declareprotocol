import typing

import pytest

from declareprotocol.adapter import AdapterRegistry


class Source(typing.Protocol):
    source: str


class OtherSource(typing.Protocol):
    other: str


class Target(typing.Protocol):
    target: str


class TargetBase(typing.Protocol):
    base: str


class DerivedTarget(TargetBase, typing.Protocol):
    derived: str


def first_factory(value: object) -> tuple[str, object]:
    return ("first", value)


def second_factory(value: object) -> tuple[str, object]:
    return ("second", value)


def test_empty_registry_and_exact_registration() -> None:
    registry = AdapterRegistry()

    assert registry.registered((Source,), Target) is None
    assert registry.lookup((Source,), Target, default="missing") == "missing"

    registry.register((Source,), Target, "", first_factory)

    assert registry.registered((Source,), Target) is first_factory


def test_register_replaces_and_none_unregisters() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), Target, "", first_factory)
    registry.register((Source,), Target, "", second_factory)

    assert registry.registered((Source,), Target) is second_factory

    registry.register((Source,), Target, "", None)

    assert registry.registered((Source,), Target) is None


def test_unregister_honors_optional_value_identity() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), Target, "named", first_factory)

    assert not registry.unregister(
        (Source,),
        Target,
        "named",
        second_factory,
    )
    assert registry.unregister(
        (Source,),
        Target,
        "named",
        first_factory,
    )
    assert not registry.unregister((Source,), Target, "named")


def test_registered_is_exact_for_required_provided_and_name() -> None:
    registry = AdapterRegistry()
    registry.register((Source,), DerivedTarget, "named", first_factory)

    assert registry.registered((OtherSource,), DerivedTarget, "named") is None
    assert registry.registered((Source,), TargetBase, "named") is None
    assert registry.registered((Source,), DerivedTarget, "") is None


@pytest.mark.parametrize(
    ("required", "provided"),
    [
        ((str,), Target),
        ((Source,), str),
        (((Source,),), Target),
    ],
)
def test_registration_rejects_invalid_protocols(
    required: tuple[object, ...],
    provided: object,
) -> None:
    registry = AdapterRegistry()

    with pytest.raises(TypeError):
        registry.register(required, provided, "", first_factory)  # type: ignore[arg-type]


@pytest.mark.parametrize("name", [None, 1, object()])
def test_registration_rejects_non_string_names(name: object) -> None:
    registry = AdapterRegistry()

    with pytest.raises(ValueError):
        registry.register((Source,), Target, name, first_factory)  # type: ignore[arg-type]
