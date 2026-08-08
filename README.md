# Protocols as contracts and protocol dispatch

Python Protocols provide duck typing, which is a common pattern for
describing behavior and protocols are well supported by type-checking
tools like mypy and ty. They don't support assertions that classes or
objects implement protocols. IOW, they don't support promises to abide
by contracts, and views such assertions as non-pythonic.

zope.interface (ZI) OTOH views interfaces as contracts that classes
implement or objects provide. Some find this very valuable.

Having explicit declarations also supports behavior-based dispatch. ZI
provides a powerful adapter protocol that provides advanced automated
dispatch.

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

