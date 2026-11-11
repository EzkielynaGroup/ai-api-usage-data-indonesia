"""Tests for scripts/update.py against a local HTTP server with recorded, trimmed fixtures (no internet)."""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
import update  # noqa: E402

FIX = {
    "/status/leaderboard.json": "leaderboard.json",
    "/status/models.json": "models.json",
    "/api/pricing": "pricing.json",
}
BLOCKED = ("uncensored", "abliterated", "nsfw")


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


class Handler(http.server.BaseHTTPRequestHandler):
    mode = "ok"

    def do_GET(self):
        name = FIX.get(self.path)
        if Handler.mode == "fail" and self.path == "/api/pricing":
            self.send_response(500)
            self.end_headers()
            return
        if not name:
            self.send_response(404)
            self.end_headers()
            return
        body = read_bytes(os.path.join(HERE, "fixtures", name))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class UpdateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = "http://127.0.0.1:%d" % cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        Handler.mode = "ok"
        self.root = tempfile.mkdtemp(prefix="ezk-data-")
        with open(os.path.join(self.root, "README.md"), "w", encoding="utf-8") as f:
            f.write("# Title\n\nintro\n\n%s\nold table\n%s\n\n## Footer\nkeep me\n" % (update.START, update.END))
        update.TIMEOUT_S = 5

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def load(self, *parts):
        with open(os.path.join(self.root, *parts), encoding="utf-8") as f:
            return json.load(f)

    def test_writes_dated_and_latest_snapshots(self):
        day, changed = update.run(self.root, self.base, "2026-11-11")
        self.assertEqual(day, "2026-11-11")
        for name in ("leaderboard", "models", "pricing"):
            self.assertIn(os.path.join("data", "2026", "11", "11", name + ".json"), changed)
            self.assertIn(os.path.join("latest", name + ".json"), changed)
            self.assertEqual(self.load("data", "2026", "11", "11", name + ".json"), self.load("latest", name + ".json"))
        self.assertIn("README.md", changed)

    def test_blocked_ids_are_removed_everywhere(self):
        update.run(self.root, self.base, "2026-11-11")
        for name in ("leaderboard", "models", "pricing"):
            text = update.read_text(os.path.join(self.root, "latest", name + ".json")).lower()
            for word in BLOCKED:
                self.assertNotIn(word, text, name)
        readme = update.read_text(os.path.join(self.root, "README.md")).lower()
        for word in BLOCKED:
            self.assertNotIn(word, readme)

    def test_leaderboard_keeps_source_fields_and_license(self):
        update.run(self.root, self.base, "2026-11-11")
        lb = self.load("latest", "leaderboard.json")
        self.assertEqual(lb["license"], "CC BY 4.0")
        self.assertEqual(lb["attribution"], update.ATTRIBUTION)
        self.assertEqual(lb["window"]["days"], 7)
        first = lb["models"]["items"][0]
        self.assertEqual(first["model"], "deepseek-v4.1-flash-1017")
        self.assertEqual(first["requests"], 47627)
        self.assertNotIn("icon", first)
        self.assertEqual(len(lb["models"]["items"]), 12)  # 13 in the fixture, 1 synthetic blocked row removed
        self.assertEqual(lb["apps"]["items"][0]["name"], "OpenCode")

    def test_models_status_unchanged_except_filter(self):
        update.run(self.root, self.base, "2026-11-11")
        st = self.load("latest", "models.json")
        src = json.loads(update.read_text(os.path.join(HERE, "fixtures", "models.json")))
        self.assertEqual(st["models"]["deepseek-v4.1-flash"], src["models"]["deepseek-v4.1-flash"])
        self.assertEqual(len(st["models"]), len([k for k in src["models"] if not any(w in k.lower() for w in BLOCKED)]))
        self.assertEqual(st["generated_at"], src["generated_at"])

    def test_pricing_math_matches_the_public_price_list(self):
        update.run(self.root, self.base, "2026-11-11")
        pr = {m["id"]: m for m in self.load("latest", "pricing.json")["models"]}
        ds = pr["deepseek-v4.1-flash"]  # ratio 0.02, completion 4, cache 0.135, Standard 1x
        self.assertEqual((ds["billing"], ds["input_usd_per_1m"], ds["output_usd_per_1m"], ds["cached_input_usd_per_1m"]), ("tokens", 0.04, 0.16, 0.0054))
        self.assertEqual(ds["key_groups"], ["default"])
        cs = pr["claude-sonnet-5.5"]  # Premium 1.5x: 0.0535 x 2 x 1.5
        self.assertEqual((cs["input_usd_per_1m"], cs["output_usd_per_1m"], cs["multiplier"]), (0.1605, 0.8025, 1.5))
        img = pr["gpt-image-2.5"]
        self.assertEqual((img["billing"], img["unit"], img["price_usd"]), ("per_call", "image", 0.00207))
        self.assertEqual(pr["edge-tts"]["billing"], "characters")
        self.assertEqual(pr["edge-tts"]["input_usd_per_1m"], 1.0)
        self.assertEqual(pr["stt-xai-v1"]["billing"], "audio_minutes")
        self.assertIsNone(pr["glm-4.5-flash"]["cached_input_usd_per_1m"])  # cache_ratio 1 is not a discount
        for m in pr.values():
            self.assertTrue(set(m["key_groups"]) <= {"default", "free", "media", "premium", "pro"}, m)
            self.assertNotIn("description", m)

    def test_readme_block_replaced_in_place(self):
        update.run(self.root, self.base, "2026-11-11")
        text = update.read_text(os.path.join(self.root, "README.md"))
        self.assertTrue(text.startswith("# Title\n\nintro\n\n" + update.START))
        self.assertTrue(text.endswith(update.END + "\n\n## Footer\nkeep me\n"))
        self.assertNotIn("old table", text)
        self.assertIn("| 1 | `deepseek-v4.1-flash-1017` | DeepSeek | 46.3% | 47,627 | 45 | -49.6% | 99.91% |", text)
        self.assertIn("| 3 | `deepseek-v4-pro` | DeepSeek | 2.05% | 2,109 | 10 | +33.6% (was #7) | 99.38% |", text)
        self.assertEqual(text.count("\n| ") - 1, 10)  # header + 10 rows (separator row starts with |---)
        self.assertIn("This week the most-used model was `deepseek-v4.1-flash-1017` (46.3% of requests).", text)
        self.assertIn("Snapshot of 2026-11-11 22:23 WIB.", text)
        self.assertIn("Models from DeepSeek together took", text)
        self.assertIn(update.ATTRIBUTION, text)

    def test_second_run_with_same_data_changes_nothing(self):
        update.run(self.root, self.base, "2026-11-11")
        _, changed = update.run(self.root, self.base, "2026-11-11")
        self.assertEqual(changed, [])
        _, changed = update.run(self.root, self.base, "2026-11-12")
        self.assertEqual(sorted(changed), sorted(os.path.join("data", "2026", "11", "12", n + ".json") for n in ("leaderboard", "models", "pricing")))

    def test_failed_fetch_writes_nothing(self):
        Handler.mode = "fail"
        with self.assertRaises(update.UpdateError):
            update.run(self.root, self.base, "2026-11-11")
        self.assertFalse(os.path.exists(os.path.join(self.root, "data")))
        self.assertFalse(os.path.exists(os.path.join(self.root, "latest")))
        self.assertEqual(update.main(["--root", self.root, "--source", self.base, "--date", "2026-11-11"]), 1)

    def test_rejects_plain_http_and_bad_dates(self):
        with self.assertRaises(update.UpdateError):
            update.run(self.root, "http://example.com", "2026-11-11")
        with self.assertRaises(update.UpdateError):
            update.run(self.root, self.base, "11/11/2026")

    def test_readme_without_markers_gets_block_appended(self):
        with open(os.path.join(self.root, "README.md"), "w", encoding="utf-8") as f:
            f.write("# Plain\n")
        update.run(self.root, self.base, "2026-11-11")
        text = update.read_text(os.path.join(self.root, "README.md"))
        self.assertTrue(text.startswith("# Plain\n\n" + update.START))


if __name__ == "__main__":
    unittest.main()
