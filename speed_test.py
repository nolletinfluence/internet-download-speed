import argparse
import sys
from http.client import HTTPException
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024
TIMEOUT_SECONDS = 15


def parse_http_url(value: str) -> str:
    try:
        parts = urlsplit(value)
        if parts.scheme in ("http", "https") and parts.hostname:
            return value
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("укажите полный URL с http:// или https://")


def download(url: str) -> tuple[int, float]:
    request = Request(url, headers={"Accept-Encoding": "identity"}, method="GET")
    received = 0
    started = perf_counter()
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        while chunk := response.read(CHUNK_SIZE):
            received += len(chunk)
        elapsed = perf_counter() - started

        content_length = response.getheader("Content-Length")
        if content_length is not None and response.getheader("Transfer-Encoding") is None:
            if received != int(content_length):
                raise ValueError(f"неполный ответ: {received} из {content_length} байт")

    return received, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Измерить скорость скачивания с URL.")
    parser.add_argument("url", type=parse_http_url, help="прямая ссылка на файл по HTTP(S)")
    args = parser.parse_args()

    total_bytes = 0
    total_seconds = 0.0
    for number in range(1, REQUEST_COUNT + 1):
        try:
            received, elapsed = download(args.url)
        except (HTTPException, OSError, ValueError) as error:
            print(f"Запрос {number}/{REQUEST_COUNT}: {error}", file=sys.stderr)
            return 1
        total_bytes += received
        total_seconds += elapsed

    speed_mbps = total_bytes * 8 / total_seconds / 1_000_000
    print(f"Запросов: {REQUEST_COUNT}")
    print(f"Среднее время запроса: {total_seconds / REQUEST_COUNT:.3f} с")
    print(f"Всего скачано: {total_bytes} байт")
    print(f"Скорость скачивания: {speed_mbps:.2f} Мбит/с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
