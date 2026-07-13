"""Deterministic, AI-free watchdog for Jetson Thor.

``thor monitor`` periodically runs the :mod:`jetson_thor.probe` collectors,
compares their numbers against configured thresholds, and POSTs to a generic
webhook when a catastrophe condition crosses (and again when it clears). No
model, no inference — just threshold comparison, designed to run always-on as
a systemd ``--user`` service the CLI installs and manages.

Modules:

* :mod:`jetson_thor.monitor.config` — thresholds, webhook target, intervals
  (JSON + env), all stdlib.
* :mod:`jetson_thor.monitor.rules` — ``evaluate(snapshot, thresholds) ->
  [Alert]``, pure and fully testable.
* :mod:`jetson_thor.monitor.state` — edge-triggering (fire on transition,
  resolve on recovery, re-notify slowly) so a standing condition doesn't spam.
* :mod:`jetson_thor.monitor.notify` — ``urllib`` webhook POST that never
  raises into the loop; generic JSON or Slack/Discord chat presets.
* :mod:`jetson_thor.monitor.engine` — snapshot -> evaluate -> diff -> notify
  -> persist.
* :mod:`jetson_thor.monitor.systemd` — generate and manage the user-level unit.
"""

from __future__ import annotations
