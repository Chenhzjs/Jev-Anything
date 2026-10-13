# Jev Anything

Jev Anything connects Jev to a live Linux GUI through GUI2TUI.

```text
observe -> candidates -> Jev decision -> validate -> execute -> readback
```

The first release is a local, inspectable workbench rather than a hidden
automation script. It shows the real application, the semantic TUI projection,
the Jev decision, and the execution evidence in one place.

## First release

The first release will support one real GUI fixture and one complete workflow:

1. GUI2TUI observes the running application.
2. Jev Anything produces a small set of legal candidates.
3. Jev chooses a candidate or abstains.
4. GUI2TUI validates and executes the decision.
5. The application is observed again and the effect is confirmed or reported
   as unknown.

The local workbench will be available at `http://localhost:<port>` and will
show:

- the current GUI view;
- the current semantic TUI view;
- candidate operations and the selected decision;
- the live lifecycle from observation through readback;
- latency, generation, scope and outcome evidence.

Jev Anything does not invent coordinates, arbitrary commands or unsupported
capabilities. The GUI2TUI operation authority remains responsible for scope,
freshness, execution and authoritative readback.

## Status

The repository is in protocol and integration setup. See
[`docs/TODO.md`](docs/TODO.md) for the current implementation sequence.

