"""
Tests for the Connect-tab machinery:

- config_loader.set_instrument_address updates the in-memory config
  and persists it to the YAML file on disk.
- acquisition.connection.identify runs *IDN? against a fake connection
  and returns the trimmed response.
- acquisition.connection.connect_and_identify returns (conn, idn) with
  the connection still open and the IDN string.
- gui.tabs.connect.DEFAULT_CARDS is a list of 4-tuples
  ``(id, name, description, dialect)`` and the Connected-panel
  iteration unpacks them with the 4-element shape.
- gui.tabs.connect.parse_idn_model returns the chunk between the
  first and second comma of a SCPI ``*IDN?`` response.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from config_loader import ConfigLoader
from gui.tabs.connect import CommandHistory
from tests.fake_connection import FakeConnection


class SetInstrumentAddressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "config.yaml"
        with open(self.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "instruments": {
                        "smu": {"name": "SMU", "address": "TCPIP::1.2.3.4::INSTR"},
                        "scope1": {"name": "RTA", "address": "TCPIP::5.6.7.8::INSTR"},
                    },
                    "paths": {"output_base": "Output"},
                },
                f,
            )
        # Reset the singleton state so load_config picks up our tmp file.
        ConfigLoader._instance = None
        ConfigLoader._loaded = False

    def tearDown(self) -> None:
        ConfigLoader._instance = None
        ConfigLoader._loaded = False
        self.tmp.cleanup()

    def test_set_in_memory_and_persists_to_disk(self):
        cfg = ConfigLoader()
        cfg.load_config(str(self.path))
        cfg.set_instrument_address("smu", "TCPIP::9.9.9.9::INSTR")

        # In-memory
        self.assertEqual(cfg.get_instrument_address("smu"), "TCPIP::9.9.9.9::INSTR")
        # On disk
        with open(self.path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["instruments"]["smu"]["address"], "TCPIP::9.9.9.9::INSTR")
        # Other instrument untouched
        self.assertEqual(data["instruments"]["scope1"]["address"], "TCPIP::5.6.7.8::INSTR")

    def test_set_unknown_instrument_raises(self):
        cfg = ConfigLoader()
        cfg.load_config(str(self.path))
        with self.assertRaises(KeyError):
            cfg.set_instrument_address("scope99", "TCPIP::1.1.1.1::INSTR")


class IdentifyTests(unittest.TestCase):
    def test_identify_with_provided_connection(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Rohde&Schwarz,RTA4004,1234,01.000\n")
        from acquisition.connection import identify
        result = identify("scope1", conn=fake)
        self.assertEqual(result, "Rohde&Schwarz,RTA4004,1234,01.000")
        self.assertIn("*IDN?", fake.queries)
        self.assertFalse(fake.closed)  # caller owns the connection

    def test_identify_opens_and_closes_when_no_conn(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Keysight,DSOX,ABC,01.00")

        with patch("acquisition.connection.open_pyvisa", return_value=fake) as open_mock:
            from acquisition.connection import identify
            result = identify("scope3")

        self.assertEqual(result, "Keysight,DSOX,ABC,01.00")
        open_mock.assert_called_once()
        self.assertTrue(fake.closed)

    def test_connect_and_identify_returns_open_connection(self):
        fake = FakeConnection()
        fake.set_response("*IDN?", "Keysight,B2902A,MY-SMU,1.0")

        with patch("acquisition.connection.open_pyvisa", return_value=fake) as open_mock:
            from acquisition.connection import connect_and_identify
            conn, idn = connect_and_identify("smu")

        self.assertIs(conn, fake)
        self.assertEqual(idn, "Keysight,B2902A,MY-SMU,1.0")
        self.assertFalse(fake.closed)  # caller must close
        open_mock.assert_called_once()


class NormalizeAddressTests(unittest.TestCase):
    """Tests for gui_connect.normalize_address (pure function)."""

    def test_empty_inputs(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address(""), "")
        self.assertEqual(normalize_address(None), "")
        self.assertEqual(normalize_address("   "), "")

    def test_bare_ipv4_is_wrapped(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("192.168.0.32"),
                         "TCPIP::192.168.0.32::INSTR")
        self.assertEqual(normalize_address("169.254.168.151"),
                         "TCPIP::169.254.168.151::INSTR")
        self.assertEqual(normalize_address("  10.0.0.1  "),
                         "TCPIP::10.0.0.1::INSTR")

    def test_full_address_preserved(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("TCPIP::1.2.3.4::INSTR"),
                         "TCPIP::1.2.3.4::INSTR")
        self.assertEqual(normalize_address("USB0::0x1234::0x5678::INSTR"),
                         "USB0::0x1234::0x5678::INSTR")
        self.assertEqual(normalize_address("GPIB0::1::INSTR"),
                         "GPIB0::1::INSTR")

    def test_unknown_format_passes_through(self):
        """If the user typed something that doesn't look like an IPv4
        and doesn't contain '::', we don't touch it. Better to save
        whatever they meant than to corrupt it."""
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("ASRL1::INSTR"), "ASRL1::INSTR")
        # Even odd input is passed through unchanged.
        self.assertEqual(normalize_address("not-a-known-bus"), "not-a-known-bus")

    def test_custom_prefix_and_suffix(self):
        from gui.tabs.connect import normalize_address
        self.assertEqual(normalize_address("192.168.0.32",
                                          default_prefix="USB",
                                          default_suffix="MYDEV"),
                         "USB::192.168.0.32::MYDEV")


class DefaultCardsShapeTests(unittest.TestCase):
    """``DEFAULT_CARDS`` is iterated in ``_refresh_connected_list`` to
    decide the rendering order of the Connected panel. The iteration
    must unpack the 4-tuple shape
    ``(instrument_id, short_name, description, scope_dialect)``; a
    regression to a 3-element unpack used to silently fall back to
    the static card name and the user saw no model from ``*IDN?``."""

    def test_default_cards_are_4_tuples(self):
        from gui.tabs.connect import DEFAULT_CARDS
        for entry in DEFAULT_CARDS:
            self.assertEqual(
                len(entry), 4,
                f"DEFAULT_CARDS entry {entry!r} must have 4 elements, "
                f"got {len(entry)}"
            )
            instrument_id, short_name, description, dialect = entry
            self.assertTrue(instrument_id, "instrument_id must be non-empty")
            self.assertTrue(short_name, "short_name must be non-empty")
            self.assertTrue(description, "description must be non-empty")
            # dialect is None for non-scope instruments, otherwise a string.
            self.assertTrue(
                dialect is None or isinstance(dialect, str),
                f"dialect must be None or str, got {dialect!r}",
            )

    def test_4tuple_unpacking_does_not_raise(self):
        """Mirror the exact comprehension the Connected panel uses."""
        from gui.tabs.connect import DEFAULT_CARDS
        # If this comprehension raises, the panel falls back to a
        # lambda that returns "" for parse_idn_model and the user
        # never sees the model field of their *IDN? response.
        try:
            ordered_ids = [iid for iid, _, _, _ in DEFAULT_CARDS]
        except ValueError as e:
            self.fail(f"4-tuple unpacking raised: {e}")
        self.assertEqual(len(ordered_ids), len(DEFAULT_CARDS))
        self.assertIn("scope1", ordered_ids)
        self.assertIn("scope2", ordered_ids)
        self.assertIn("scope3", ordered_ids)


class ParseIdnModelTests(unittest.TestCase):
    """``parse_idn_model`` returns the chunk between the first and
    second comma of a ``*IDN?`` response (manufacturer, model, ...)."""

    def test_returns_model_field(self):
        from gui.tabs.connect import parse_idn_model
        self.assertEqual(parse_idn_model("Rohde&Schwarz,RTA4004,1234,01.00"),
                         "RTA4004")
        self.assertEqual(parse_idn_model("Keysight Technologies,DSOS054A,..."),
                         "DSOS054A")

    def test_empty_inputs(self):
        from gui.tabs.connect import parse_idn_model
        self.assertEqual(parse_idn_model(""), "")
        self.assertEqual(parse_idn_model("no_commas_here"), "")

    def test_strips_whitespace(self):
        from gui.tabs.connect import parse_idn_model
        self.assertEqual(parse_idn_model("Acme, Model-X ,sn,fw"), "Model-X")


class ExceptBlockLambdaClosureTests(unittest.TestCase):
    """Under Python 3.13, ``except Exception as e:`` deletes the
    ``e`` name when the block exits, so a ``lambda: str(e)``
    scheduled via ``after(0, ...)`` (i.e. fired after the worker
    has returned) will raise ``NameError`` later.

    The fix used in ``_do_connect`` binds ``e`` as a default
    argument of the lambda so its current value is captured.
    """

    def test_plain_lambda_fails_when_fired_after_except_block(self):
        """Reproduce the bug: a ``lambda: str(e)`` defined inside
        an ``except`` block and then fired after the block has
        exited must raise ``NameError`` on Python 3.13. This is
        exactly what the user saw in connect.py:320.
        """
        import sys
        if sys.version_info < (3, 13):
            self.skipTest("behaviour changed at 3.13")

        captured: list = []
        scheduled: list = []

        def schedule(cb):
            # Simulate ``self.after(0, cb)``: defer the callback
            # until after the ``try``/``except`` block has exited.
            scheduled.append(cb)

        try:
            raise ValueError("simulated VISA timeout")
        except Exception as e:
            schedule(lambda: captured.append(str(e)))

        # The worker has returned; now fire the scheduled callback.
        self.assertEqual(len(scheduled), 1)
        with self.assertRaises(NameError):
            scheduled[0]()
        self.assertEqual(captured, [])

    def test_lambda_with_default_arg_captures_e(self):
        """The fix: ``lambda e=e: str(e)`` keeps the value alive
        even after the except block has exited."""
        captured: list = []
        scheduled: list = []

        def schedule(cb):
            scheduled.append(cb)

        try:
            raise ValueError("simulated VISA timeout")
        except Exception as e:
            schedule(lambda e=e: captured.append(str(e)))

        scheduled[0]()
        self.assertEqual(captured, ["simulated VISA timeout"])


class CommandHistoryUnitTests(unittest.TestCase):
    """Pure tests for the ``CommandHistory`` class.

    The Up/Down/Tab bindings in the GUI delegate to this
    class, so we cover the navigation logic here. The end-to-end
    test in ``CommandLinePanelTests`` below wires the panel to
    a fake connection.
    """

    def test_add_dedupes_and_keeps_most_recent_first(self):
        h = CommandHistory()
        h.add("*IDN?")
        h.add("CHAN1:OUTP ON")
        h.add("*IDN?")  # re-add
        self.assertEqual(h._items, ["*IDN?", "CHAN1:OUTP ON"])

    def test_add_ignores_empty(self):
        h = CommandHistory()
        h.add("   ")
        h.add("")
        self.assertEqual(h._items, [])

    def test_up_returns_none_when_empty(self):
        h = CommandHistory()
        self.assertIsNone(h.up("draft"))

    def test_up_down_navigation(self):
        h = CommandHistory()
        h.add("a")
        h.add("b")
        h.add("c")
        # Up from draft jumps to the most recent.
        self.assertEqual(h.up("draft"), "c")
        # Up again goes to the older one.
        self.assertEqual(h.up("b"), "b")
        # Up at the oldest stays.
        self.assertEqual(h.up("a"), "a")
        # Down walks back.
        self.assertEqual(h.down(), "b")
        self.assertEqual(h.down(), "c")
        # Down from newest restores the draft.
        self.assertEqual(h.down(), "draft")
        # Down past draft returns None.
        self.assertIsNone(h.down())

    def test_suggest_prefix_match(self):
        h = CommandHistory()
        h.add("CHAN1:OUTP ON")    # oldest
        h.add("CHAN1:OUTP OFF")
        h.add("CHAN2:OUTP ON")
        h.add("*IDN?")            # newest
        # Suggestions come back most-recent-first.
        self.assertEqual(h.suggest("CHAN1"),
                         ["CHAN1:OUTP OFF", "CHAN1:OUTP ON"])
        self.assertEqual(h.suggest("chan2"), ["CHAN2:OUTP ON"])
        self.assertEqual(h.suggest("nothing"), [])

    def test_reset_restores_draft(self):
        h = CommandHistory()
        h.add("x")
        h.up("draft")
        h.reset()
        # After reset, the index is back to -1 so a new Up
        # starts from the most recent again.
        self.assertEqual(h.up("new draft"), "x")


class CommandLinePanelTests(unittest.TestCase):
    """End-to-end tests for the SCPI command line in Connect.

    Builds the actual command panel inside a Tk root, with a
    fake connected instrument, sends a few commands and checks
    that:
      1. ``_push_history`` populates the per-instrument history.
      2. The active history has the commands in the right order.
      3. Switching the active instrument swaps the history.

    Note: ``event_generate`` does not reliably fire <Key-Up>
    bindings in headless test environments, so the Up/Down/Tab
    key handlers are exercised through the public
    ``CommandHistory`` API, which is the layer the GUI itself
    delegates to.
    """

    def setUp(self) -> None:
        try:
            import customtkinter as ctk
            self.root = ctk.CTk()
        except Exception as e:
            self.skipTest(f"CTk unavailable: {e}")

        import gui.tabs.connect as connect_tab

        class _Stub:
            pass

        self.stub = _Stub()
        self.stub.config = type("Cfg", (), {"config": {}})()
        # Fake connection: any object that supports .write and
        # .query (we use write only here).
        self.conn = FakeConnection()
        self.stub.connect_cards = {
            "scope1": {"connection": self.conn, "idn": "Rohde&Schwarz,RTA4004,..."},
            "scope2": {"connection": FakeConnection(),
                       "idn": "Keysight,DSOS054A,..."},
        }

        # Build the command panel against a CTkFrame parent.
        self.parent = ctk.CTkFrame(self.root)
        connect_tab._build_command_panel(self.stub, self.parent)
        # The default menu label is "(no instruments connected)";
        # simulate the user picking the RTA card.
        self.menu = self.stub.connect_command_menu
        self.menu.set("RTA")

        # `_push_history` is the only function that mutates the
        # per-instrument history dict. We mock out the worker
        # thread that _cmd_send would otherwise start.
        self._orig_conn = None

    def tearDown(self) -> None:
        try:
            self.root.destroy()
        except Exception:
            pass

    def _send(self, raw: str) -> None:
        # Bypass the worker thread: just push the history.
        import gui.tabs.connect as connect_tab
        connect_tab._push_history(self.stub, "scope1", raw)

    def test_first_command_populates_history(self):
        # Regression: previously ``if not histories: return``
        # bailed out on the very first push because the dict
        # was empty, so the per-instrument history never grew.
        import gui.tabs.connect as connect_tab
        self.assertEqual(self.stub.connect_command_histories, {})
        self._send("*IDN?")
        self.assertIn("scope1", self.stub.connect_command_histories)
        history = self.stub.connect_command_histories["scope1"]
        self.assertEqual(history._items, ["*IDN?"])

    def test_multiple_commands_keep_order(self):
        for cmd in ("*IDN?", "CHAN1:OUTP ON", "CHAN1:OUTP OFF"):
            self._send(cmd)
        history = self.stub.connect_command_histories["scope1"]
        self.assertEqual(
            history._items,
            ["CHAN1:OUTP OFF", "CHAN1:OUTP ON", "*IDN?"],
        )

    def test_repeated_command_moves_to_top(self):
        for cmd in ("*IDN?", "CHAN1:OUTP ON", "*IDN?"):
            self._send(cmd)
        history = self.stub.connect_command_histories["scope1"]
        self.assertEqual(history._items, ["*IDN?", "CHAN1:OUTP ON"])

    def test_per_instrument_isolation(self):
        # Switch to scope2 and send a command.
        import gui.tabs.connect as connect_tab
        self._send("RTA:CMD1")
        connect_tab._push_history(self.stub, "scope2", "KEY:CMD1")
        rta = self.stub.connect_command_histories["scope1"]
        key = self.stub.connect_command_histories["scope2"]
        self.assertEqual(rta._items, ["RTA:CMD1"])
        self.assertEqual(key._items, ["KEY:CMD1"])

    def test_suggest_completion_via_active_history(self):
        import gui.tabs.connect as connect_tab
        for cmd in ("CHAN1:OUTP ON", "CHAN1:OUTP OFF", "CHAN2:OUTP ON"):
            self._send(cmd)
        # The _active_history closure inside _build_command_panel
        # picks the right history for the selected instrument.
        # We can't reach that closure directly, but
        # ``self.stub.connect_command_history`` is the cached
        # reference used by the entry's Up/Down handlers; it
        # is updated whenever _push_history runs.
        self.assertEqual(
            self.stub.connect_command_history.suggest("CHAN1"),
            ["CHAN1:OUTP OFF", "CHAN1:OUTP ON"],
        )

    def test_up_down_navigation_after_three_sends(self):
        import gui.tabs.connect as connect_tab
        for cmd in ("*IDN?", "CHAN1:OUTP ON", "CHAN1:OUTP OFF"):
            self._send(cmd)
        history = self.stub.connect_command_history
        # Up from the draft jumps to the most recent command.
        self.assertEqual(history.up("draft"), "CHAN1:OUTP OFF")
        # Up again -> older.
        self.assertEqual(history.up("CHAN1:OUTP OFF"), "CHAN1:OUTP ON")
        # Up at the oldest stays.
        self.assertEqual(history.up("CHAN1:OUTP ON"), "*IDN?")
        # Down -> back to the newer.
        self.assertEqual(history.down(), "CHAN1:OUTP ON")
        # Down -> newest.
        self.assertEqual(history.down(), "CHAN1:OUTP OFF")
        # Down -> draft.
        self.assertEqual(history.down(), "draft")


if __name__ == "__main__":
    unittest.main()
