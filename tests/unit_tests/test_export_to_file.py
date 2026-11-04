"""``export_to(path)`` replaces the file only with a complete export."""

import http.server
import socket
import stat
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from surrealdb.connections.import_export import (
    ExportOptions,
    aexport_sql_to,
    export_sql_to,
)
from surrealdb.connections.url import Url
from surrealdb.errors import ConnectionUnavailableError

EXPORT = b"OPTION IMPORT;\n-- the whole export\n"
BACKUP = b"THE LAST GOOD BACKUP"


class _Export(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    complete = True

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Length", str(len(EXPORT)))
        self.end_headers()
        if self.complete:
            self.wfile.write(EXPORT)
        else:
            # A body that breaks off: the server promised more than it sent.
            self.wfile.write(EXPORT[:10])
            self.wfile.flush()
            self.close_connection = True
            self.connection.shutdown(socket.SHUT_RDWR)

    def log_message(self, format: str, *args: object) -> None:
        pass


class _BrokenExport(_Export):
    complete = False


def _serve(handler: type[http.server.BaseHTTPRequestHandler]) -> Iterator[Url]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, args=(0.01,), daemon=True)
    thread.start()
    try:
        yield Url(f"http://127.0.0.1:{server.server_address[1]}")
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def export_url() -> Iterator[Url]:
    yield from _serve(_Export)


@pytest.fixture
def broken_export_url() -> Iterator[Url]:
    yield from _serve(_BrokenExport)


def _export(url: Url, target: Path) -> None:
    export_sql_to(url, ExportOptions(), target, 5, None, None, None)


async def _aexport(url: Url, target: Path) -> None:
    await aexport_sql_to(url, ExportOptions(), target, 5, None, None, None)


def test_an_export_that_breaks_off_leaves_the_file_as_it_was(
    broken_export_url: Url, tmp_path: Path
) -> None:
    backup = tmp_path / "backup.surql"
    backup.write_bytes(BACKUP)
    with pytest.raises(ConnectionUnavailableError):
        _export(broken_export_url, backup)
    assert backup.read_bytes() == BACKUP
    assert [path.name for path in tmp_path.iterdir()] == ["backup.surql"]


async def test_an_async_export_that_breaks_off_leaves_the_file_as_it_was(
    broken_export_url: Url, tmp_path: Path
) -> None:
    backup = tmp_path / "backup.surql"
    backup.write_bytes(BACKUP)
    with pytest.raises(ConnectionUnavailableError):
        await _aexport(broken_export_url, backup)
    assert backup.read_bytes() == BACKUP
    assert [path.name for path in tmp_path.iterdir()] == ["backup.surql"]


def test_a_complete_export_replaces_the_file_keeping_its_mode(
    export_url: Url, tmp_path: Path
) -> None:
    backup = tmp_path / "backup.surql"
    backup.write_bytes(BACKUP)
    backup.chmod(0o640)
    _export(export_url, backup)
    assert backup.read_bytes() == EXPORT
    assert stat.S_IMODE(backup.stat().st_mode) == 0o640
    assert [path.name for path in tmp_path.iterdir()] == ["backup.surql"]


async def test_a_complete_async_export_writes_a_new_file(
    export_url: Url, tmp_path: Path
) -> None:
    target = tmp_path / "new.surql"
    await _aexport(export_url, target)
    assert target.read_bytes() == EXPORT


def test_an_export_through_a_symlink_writes_the_file_it_points_to(
    export_url: Url, tmp_path: Path
) -> None:
    real = tmp_path / "real.surql"
    real.write_bytes(BACKUP)
    link = tmp_path / "latest.surql"
    link.symlink_to(real)
    _export(export_url, link)
    assert link.is_symlink()
    assert real.read_bytes() == EXPORT
