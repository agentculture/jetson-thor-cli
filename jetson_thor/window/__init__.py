"""Benchmark window (clock/fan lock), page-cache clear and sudo grant.

The domain behind ``thor window``, ``thor drop-caches`` and ``thor
grant-permissions`` (contract: lobes ``docs/contracts/machine-cli-window.md``).
Every function takes an :class:`Env` so tests inject fakes and never touch the
host; nothing here runs at import time.
"""
