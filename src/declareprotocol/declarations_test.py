import typing

import pytest

import declareprotocol


class HasRun(typing.Protocol):
    def run(self) -> str: ...


class HasStop(typing.Protocol):
    def stop(self) -> str: ...


class HasPrivateHook(typing.Protocol):
    def _hook(self) -> None: ...


class HasData(typing.Protocol):
    data: int


@declareprotocol.implementer(HasRun)
class Runner:
    def run(self) -> str:
        return "run"


def test_implementer_rejects_non_protocol() -> None:
    with pytest.raises(TypeError):
        declareprotocol.implementer(str)


def test_implementer_validates_required_members() -> None:
    with pytest.raises(TypeError):

        @declareprotocol.implementer(HasRun)
        class MissingRun:
            pass


def test_implementedBy_includes_inherited_declarations() -> None:
    @declareprotocol.implementer(HasStop)
    class Child(Runner):
        def stop(self) -> str:
            return "stop"

    assert declareprotocol.implementedBy(Child) == (
        HasStop,
        HasRun,
    )


def test_directlyProvides_replaces_direct_declarations() -> None:
    runner = Runner()
    declareprotocol.directlyProvides(runner, HasRun)
    assert declareprotocol.directlyProvidedBy(runner) == (HasRun,)

    declareprotocol.directlyProvides(runner, HasStop)
    assert declareprotocol.directlyProvidedBy(runner) == (HasStop,)


def test_alsoProvides_adds_without_duplicates() -> None:
    runner = Runner()
    declareprotocol.directlyProvides(runner, HasRun)
    declareprotocol.alsoProvides(runner, HasStop, HasRun)
    assert declareprotocol.directlyProvidedBy(runner) == (
        HasRun,
        HasStop,
    )


def test_noLongerProvides_removes_only_direct_protocols() -> None:
    runner = Runner()
    declareprotocol.directlyProvides(runner, HasRun, HasStop)

    declareprotocol.noLongerProvides(runner, HasRun)
    assert declareprotocol.directlyProvidedBy(runner) == (HasStop,)

    with pytest.raises(ValueError):
        declareprotocol.noLongerProvides(runner, HasRun)


def test_providedBy_merges_direct_and_class_declarations() -> None:
    runner = Runner()
    declareprotocol.directlyProvides(runner, HasStop)

    assert declareprotocol.providedBy(runner) == (
        HasStop,
        HasRun,
    )


def test_directlyProvides_rejects_non_protocol() -> None:
    runner = Runner()
    with pytest.raises(TypeError):
        declareprotocol.directlyProvides(runner, str)


def test_implementer_validates_private_protocol_members() -> None:
    with pytest.raises(TypeError):

        @declareprotocol.implementer(HasPrivateHook)
        class MissingPrivateHook:
            pass


@declareprotocol.implementer(HasData)
class HasAnnotatedData:
    data: int


def test_implementer_accepts_annotation_only_data_member() -> None:
    assert declareprotocol.implementedBy(HasAnnotatedData) == (HasData,)
