import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from threading import Lock, Thread
from time import sleep
from unittest.mock import patch

from speed_test import main


BODY = b"x" * (128 * 1024)


class SpeedTest(unittest.TestCase):
    def run_cli(self, truncate_request=None):
        events = []
        lock = Lock()
        request_count = 0

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                nonlocal request_count
                with lock:
                    request_count += 1
                    number = request_count
                    events.append(("start", number))

                self.send_response(200)
                self.send_header("Content-Length", str(len(BODY)))
                self.end_headers()
                self.wfile.write(BODY[:-1])
                sleep(0.03)
                if number == truncate_request:
                    return

                with lock:
                    self.wfile.write(BODY[-1:])
                    events.append(("end", number))

        stdout, stderr = StringIO(), StringIO()
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            url = f"http://127.0.0.1:{server.server_port}/file"
            worker = Thread(target=server.serve_forever)
            worker.start()
            try:
                with patch.object(sys, "argv", ["speed_test.py", url]), patch.dict(
                    os.environ, {"no_proxy": "127.0.0.1"}
                ), redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = main()
            finally:
                server.shutdown()
                worker.join()

        return exit_code, stdout.getvalue(), stderr.getvalue(), events

    def test_downloads_ten_complete_responses_in_order(self):
        code, stdout, stderr, events = self.run_cli()

        expected = [(event, number) for number in range(1, 11) for event in ("start", "end")]
        self.assertEqual(events, expected)
        self.assertEqual(code, 0, stderr)
        self.assertIn(f"Всего скачано: {10 * len(BODY)} байт", stdout)

    def test_stops_on_truncated_third_response(self):
        code, stdout, stderr, events = self.run_cli(truncate_request=3)

        self.assertEqual([number for event, number in events if event == "start"], [1, 2, 3])
        self.assertEqual(code, 1)
        self.assertIn("Запрос 3/10: неполный ответ", stderr)
        self.assertEqual(stdout, "")
