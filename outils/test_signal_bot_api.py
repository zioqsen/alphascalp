"""Tests locaux du flux SignalBot isole. Aucun appel reseau, aucun ordre MT5."""

import importlib.util
import os
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SignalBotApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ["ALPHASCALP_DB"] = str(pathlib.Path(cls.temp.name) / "test.db")
        os.environ["ALPHASCALP_MASTER_TOKEN"] = "master-test-local-only"
        os.environ["ALPHASCALP_ADMIN_TOKEN"] = "admin-test-local-only"
        spec = importlib.util.spec_from_file_location("alphascalp_server_test", ROOT / "server.py")
        cls.server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.server)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        with self.server.db() as conn:
            conn.execute("DELETE FROM signal_bot_signals")
            conn.execute("DELETE FROM signals")

    def payload(self, **changes):
        now = datetime.now(timezone.utc)
        data = dict(
            event_id="signalbot:123:open", action="open", ref_id="signalbot:123",
            symbol="XAUUSD", direction="SELL", order_kind="LIMIT",
            price=4393.0, zone_low=4393.0, zone_high=4405.0,
            sl=4411.0, tp1=4388.0, tp2=4380.0, tp3=4370.0,
            expires_at=(now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            emitted_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        data.update(changes)
        return self.server.SignalBotSignalIn(**data)

    def test_flux_isole_et_dedup_idempotente(self):
        first = self.server.publish_signal_bot(self.payload(), "master-test-local-only")
        second = self.server.publish_signal_bot(self.payload(), "master-test-local-only")
        self.assertTrue(first["ok"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["signal_id"], second["signal_id"])
        with self.server.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM signal_bot_signals").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0], 0)

    def test_meme_id_autre_contenu_refuse(self):
        self.server.publish_signal_bot(self.payload(), "master-test-local-only")
        with self.assertRaises(self.server.HTTPException) as ctx:
            self.server.publish_signal_bot(self.payload(tp1=4387.0), "master-test-local-only")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_limit_doit_viser_premier_bord(self):
        bad = self.payload(event_id="signalbot:124:open", price=4400.0)
        with self.assertRaises(self.server.HTTPException) as ctx:
            self.server.publish_signal_bot(bad, "master-test-local-only")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_buy_limit_au_premier_bord_accepte(self):
        result = self.server.publish_signal_bot(
            self.payload(
                event_id="signalbot:buy:open", direction="BUY", price=4405.0,
                sl=4390.0, tp1=4410.0, tp2=4420.0, tp3=4430.0,
            ),
            "master-test-local-only",
        )
        self.assertTrue(result["ok"])

    def test_sell_paliers_deux_et_trois_acceptes(self):
        for stage, price in ((2, 4405.0), (3, 4408.0)):
            result = self.server.publish_signal_bot(
                self.payload(
                    event_id=f"signalbot:stage{stage}:open", price=price,
                    entry_stage=stage, risk_fraction=1 / 3,
                ),
                "master-test-local-only",
            )
            self.assertTrue(result["ok"])

    def test_palier_ne_peut_pas_prendre_tout_le_risque(self):
        with self.assertRaises(self.server.HTTPException) as ctx:
            self.server.publish_signal_bot(
                self.payload(
                    event_id="signalbot:risk:open", entry_stage=1,
                    risk_fraction=1.0,
                ),
                "master-test-local-only",
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_ouverture_perimee_refusee(self):
        old = (datetime.now(timezone.utc) - timedelta(seconds=301)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.assertRaises(self.server.HTTPException) as ctx:
            self.server.publish_signal_bot(
                self.payload(event_id="signalbot:125:open", emitted_at=old),
                "master-test-local-only",
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_expiration_limit_deja_passee_refusee(self):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.assertRaises(self.server.HTTPException) as ctx:
            self.server.publish_signal_bot(
                self.payload(event_id="signalbot:126:open", expires_at=past),
                "master-test-local-only",
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_move_sl_sans_niveau_refuse(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        event = self.server.SignalBotSignalIn(
            event_id="signalbot:123:move_sl", action="move_sl",
            ref_id="signalbot:123", symbol="XAUUSD", emitted_at=now,
        )
        with self.assertRaises(self.server.HTTPException) as ctx:
            self.server.publish_signal_bot(event, "master-test-local-only")
        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
