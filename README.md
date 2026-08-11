# Protocols as contracts and protocol dispatch

Python Protocols provide duck typing, which is a common pattern for
describing behavior, and protocols are well supported by type-checking
tools like `mypy` and `ty`. They don't support assertions that classes or
objects implement protocols. They don't support promises to abide
by contracts, and view such assertions as non-pythonic.

On the other hand, [design by
contract](https://en.wikipedia.org/wiki/Design_by_contract) is a
popular and valuable approach for separating defined behaviors from
implementation.  This package allows classes (and objects) to promise
to implement protocols, using protocols as (semi-formal) contracts.

This package takes inspiration and reimplements APIs from
[zope.interface](https://zopeinterface.readthedocs.io/en/latest/README.html),
substituting protocols for interfaces.

## Usage

```python
import typing
import declareprotocol

class HasRun(typing.Protocol):
    def run(self) -> str: pass

@declareprotocol.implementer(HasRun)
class Runner:
    def run(self) -> str:
        return "run"

runner = Runner()
print(declareprotocol.implementedBy(Runner))  # (<class 'HasRun'>,)
print(declareprotocol.providedBy(runner))      # (<class 'HasRun'>,)
```

Having explicit declarations also supports behavior-based dispatch,
which this package also provides.

```python

if HasRun in declareprotocol.providedBy(runner):
    ...
```

## Adapters

An adapter registry can select and invoke factories using declared protocols:

```python
class Summary(typing.Protocol):
    text: str

registry = declareprotocol.AdapterRegistry()
registry.register(
    (HasRun,),
    Summary,
    "",
    lambda value: f"summary: {value.run()}",
)

assert registry.queryAdapter(runner, Summary) == "summary: run"
```

