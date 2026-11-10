import math
import plistlib
import socket
import subprocess
import unittest
from unittest.mock import patch

from modules import random_number


class RandomNumberTests(unittest.TestCase):
    def test_bounds_and_reproducibility(self):
        for lower, upper in ((0, 1), (-5, 5), (7, 7), (-random_number.MAX_SAFE_INTEGER, random_number.MAX_SAFE_INTEGER)):
            for index in range(100):
                seed = {"sample": str(index)}
                value = random_number.integer_from_sources(seed, lower, upper)
                self.assertIs(type(value), int)
                self.assertLessEqual(lower, value)
                self.assertLessEqual(value, upper)
                self.assertEqual(value, random_number.integer_from_sources(seed, lower, upper))
        values = {random_number.integer_from_sources({"sample": str(i)}, 0, 1) for i in range(100)}
        self.assertEqual(values, {0, 1})

    def test_rejects_invalid_bounds(self):
        for lower, upper in ((True, 1), (0, False), ("0", 1), (0, 1.0), (2, 1), (0, 1 << 53), (-(1 << 53), 0)):
            with self.subTest(lower=lower, upper=upper), self.assertRaises(ValueError):
                random_number.integer_from_sources({}, lower, upper)

    def test_float_bounds_precision_and_reproducibility(self):
        bounds = (
            (0, 1),
            (0, 100),
            (-2.75, -1.25),
            (7.5, 7.5),
            (-random_number.MAX_SAFE_INTEGER, random_number.MAX_SAFE_INTEGER),
            (1.0, math.nextafter(1.0, 2.0)),
            (0.0, math.nextafter(0.0, 1.0)),
        )
        for lower, upper in bounds:
            for index in range(100):
                sources = {"sample": str(index)}
                value = random_number.float_from_sources(sources, lower, upper)
                self.assertIs(type(value), float)
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, lower)
                if lower == upper:
                    self.assertEqual(value, upper)
                else:
                    self.assertLess(value, upper)
                self.assertEqual(value, random_number.float_from_sources(sources, lower, upper))
        value = random_number.float_from_sources({"sample": "fraction"}, 0, 1)
        self.assertNotEqual(value, int(value))
        self.assertEqual(value * (1 << 53), int(value * (1 << 53)))

    def test_float_rounding_does_not_reach_upper_bound(self):
        with patch.object(random_number, "integer_from_sources", return_value=random_number.MAX_SAFE_INTEGER):
            self.assertLess(random_number.float_from_sources({}, -1, 0), 0)
            self.assertEqual(random_number.float_from_sources({}, 1, math.nextafter(1, 2)), 1.0)

    def test_float_rejects_invalid_bounds(self):
        invalid = (
            (True, 1), (0, False), ("0", 1), (None, 1), (2, 1),
            (float("nan"), 1), (0, float("nan")), (0, float("inf")),
            (-float("inf"), 0), (0, 1 << 53), (-(1 << 53), 0),
        )
        for lower, upper in invalid:
            with self.subTest(lower=lower, upper=upper), self.assertRaises(ValueError):
                random_number.float_from_sources({}, lower, upper)

    def test_seed_uses_all_fields_and_ignores_dictionary_order(self):
        sources = {"client_ip": "192.0.2.1", "machine_code": "machine", "cpu_frequency": "1000"}
        expected = random_number.integer_from_sources(sources, 0, random_number.MAX_SAFE_INTEGER)
        self.assertEqual(expected, random_number.integer_from_sources(dict(reversed(list(sources.items()))), 0, random_number.MAX_SAFE_INTEGER))
        for key in sources:
            changed = {**sources, key: sources[key] + "x"}
            self.assertNotEqual(expected, random_number.integer_from_sources(changed, 0, random_number.MAX_SAFE_INTEGER))

    def test_macos_sources(self):
        addresses = [
            (socket.AF_INET, 0, 0, "", ("192.0.2.2", 0)),
            (socket.AF_INET6, 0, 0, "", ("2001:db8::2", 0, 0, 0)),
        ]
        commands = [
            subprocess.CompletedProcess([], 0, stdout=plistlib.dumps([{"IOPlatformUUID": "test-machine"}])),
            subprocess.CompletedProcess([], 0, stdout="2400000000\n"),
        ]
        with patch.object(random_number.sys, "platform", "darwin"), patch.object(
            random_number.socket, "getaddrinfo", return_value=addresses
        ), patch.object(random_number.subprocess, "run", side_effect=commands):
            sources, warnings = random_number.collect_sources("192.0.2.1")
        self.assertEqual(warnings, [])
        self.assertEqual(sources["machine_code"], "test-machine")
        self.assertEqual(sources["ipv4"], "192.0.2.2")
        self.assertEqual(sources["ipv6"], "2001:db8::2")
        self.assertEqual(float(sources["cpu_frequency"]), 2400000000)

    def test_unavailable_sources_are_explicit_and_time_counter_remain(self):
        with patch.object(random_number.sys, "platform", "darwin"), patch.object(
            random_number.socket, "getaddrinfo", side_effect=socket.gaierror("Unavailable")
        ), patch.object(random_number.subprocess, "run", side_effect=subprocess.TimeoutExpired("test", 2)):
            first, warnings = random_number.collect_sources(None)
            second, _ = random_number.collect_sources(None)
        self.assertEqual(set(first), {"system_time", "monotonic_time", "sequence"})
        self.assertNotEqual(first["sequence"], second["sequence"])
        self.assertEqual(len(warnings), 6)
        self.assertIn(random_number.integer_from_sources(first, 0, 1), (0, 1))

    def test_linux_sources(self):
        def read_text(path):
            return "test-machine\n" if str(path) == "/etc/machine-id" else "cpu MHz\t\t: 1200.5\n"

        with patch.object(random_number.sys, "platform", "linux"), patch.object(
            random_number.socket, "getaddrinfo", return_value=[]
        ), patch.object(random_number.Path, "read_text", read_text):
            sources, warnings = random_number.collect_sources("192.0.2.1")
        self.assertEqual(sources["machine_code"], "test-machine")
        self.assertEqual(float(sources["cpu_frequency"]), 1200500000)
        self.assertEqual(len(warnings), 2)


class RandomEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app

        cls.module = app

    def test_authentication_validation_response_and_no_sensitive_values(self):
        module = self.module
        sources = {"client_ip": "192.0.2.1", "machine_code": "private-machine-code"}
        with patch.object(module, "access_hash", return_value="a" * 64), patch.object(
            module.request_log, "record"
        ), patch.object(module.user_data, "new_code", return_value="ABC123"), patch.object(
            module, "collect_sources", return_value=(sources, ["Server IPv6 is unavailable."])
        ) as collect, module.app.test_client() as client:
            self.assertEqual(client.post("/api/ping/random", json={}).status_code, 401)
            with client.session_transaction() as session:
                session["authenticated"] = True
            with self.assertLogs(module.app.logger.name, level="WARNING"):
                response = client.post("/api/ping/random", json={})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.json), {"value", "sources", "warnings"})
            self.assertIn(response.json["value"], (0, 1))
            self.assertEqual(response.json["sources"], list(sources))
            self.assertEqual(response.json["warnings"], ["Server IPv6 is unavailable."])
            self.assertNotIn(b"private-machine-code", response.data)
            self.assertNotIn(b"192.0.2.1", response.data)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            collect.reset_mock()
            for payload in ({"minimum": 3, "maximum": 2}, {"minimum": True}, {"maximum": 1.5}, {"maximum": 1 << 53}, []):
                with self.assertLogs(module.app.logger.name, level="WARNING"):
                    response = client.post("/api/ping/random", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
            collect.assert_not_called()
            self.assertEqual(client.get("/api/ping/random").status_code, 405)
            self.assertEqual(client.get("/ping?probe=1").json["pong"], True)
            response = client.get("/ping")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="random-form"', response.data)
            self.assertIn(b'value="0"', response.data)
            self.assertIn(b'value="1"', response.data)
            self.assertIn(b'id="random-type"', response.data)
            self.assertIn(b'id="random-quick"', response.data)

    def test_float_api_and_type_validation(self):
        module = self.module
        with patch.object(module, "access_hash", return_value="a" * 64), patch.object(
            module.request_log, "record"
        ), patch.object(module.user_data, "new_code", return_value="ABC123"), patch.object(
            module, "collect_sources", return_value=({"sample": "test"}, [])
        ) as collect, module.app.test_client() as client:
            with client.session_transaction() as session:
                session["authenticated"] = True
            for lower, upper in ((0, 1), (0, 100), (-1.5, 2.25), (7.5, 7.5)):
                response = client.post(
                    "/api/ping/random",
                    json={"minimum": lower, "maximum": upper, "number_type": "float"},
                )
                self.assertEqual(response.status_code, 200)
                value = response.json["value"]
                self.assertIs(type(value), float)
                self.assertGreaterEqual(value, lower)
                if lower == upper:
                    self.assertEqual(value, upper)
                else:
                    self.assertLess(value, upper)
            collect.reset_mock()
            invalid = (
                {"number_type": "other"}, {"number_type": None}, {"number_type": []},
                {"number_type": "float", "minimum": True},
                {"number_type": "float", "minimum": "0"},
                {"number_type": "float", "maximum": float("inf")},
                {"number_type": "float", "minimum": float("nan")},
                {"number_type": "float", "minimum": 2, "maximum": 1},
                {"number_type": "int", "minimum": 0.5},
            )
            for payload in invalid:
                with self.subTest(payload=payload), self.assertLogs(module.app.logger.name, level="WARNING"):
                    response = client.post("/api/ping/random", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn("error", response.json)
            collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
