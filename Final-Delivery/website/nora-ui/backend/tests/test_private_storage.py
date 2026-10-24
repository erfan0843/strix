"""Phase 9.4: private file storage outside the web root — real HTTP, real files, bounded memory.

What is proven here (and nothing more):

* the storage interface never builds a path from user input, refuses a root under the static web
  root, stages uploads atomically and leaves nothing behind on abort;
* through a REAL uvicorn server (not the in-process TestClient) a 48 MiB MP4 is uploaded in chunks
  and later streamed back with HTTP Range while the Python process' peak allocation stays far below
  the file size — i.e. neither direction buffers the whole file;
* access is decided per request (403 for a stranger, 401 for a guest), stops the moment the
  product's access is revoked, and survives a replacement of the bytes (new key, old file pruned,
  access rows untouched);
* a file that disappears from disk is reported as ``missing`` to the panel and never served;
* without ``NORA_PRIVATE_STORAGE_DIR`` nothing changes: >8 MiB is still 413 and bytes stay inline;
* a backup snapshot of the directory can be restored and the rows point at files that are there
  (``tools/private-storage-backup.py verify``).
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import tracemalloc
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend import storage as storage_mod  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import UI_ROOT, Settings  # noqa: E402
from backend.models import Base, EventResourceRecord, RecordingAccessRecord, SystemMarkerRecord  # noqa: E402
from backend.security import hash_password  # noqa: E402
from test_recordings_api import MP4, build_sellable_product, held_event, purchase_form, set_status  # noqa: E402
from test_workflows_api import BOT_TOKEN, SERVICE_TOKEN, bale_login, owner_login, owner_write_headers  # noqa: E402
BIG_SIZE = 48 * 1024 * 1024
CHUNK = 256 * 1024
MEMORY_CEILING = 12 * 1024 * 1024  # a quarter of the file: proves chunked handling on both directions


def storage_app(tmp_path: Path, *, configured: bool = True, max_bytes: int = 256 * 1024 * 1024):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
        private_storage_dir=str(tmp_path / "private-store") if configured else "",
        private_storage_max_bytes=max_bytes,
    )
    return create_app(settings, engine=engine), engine


def big_mp4_chunks(size: int = BIG_SIZE):
    """Deterministic MP4-looking stream: the real ``ftyp`` header, then patterned bytes."""
    head = (MP4 + bytes((i * 7) % 251 for i in range(CHUNK)))[:min(CHUNK, size)]
    yield head
    sent = len(head)
    block = bytes((i * 13) % 253 for i in range(CHUNK))
    while sent < size:
        piece = block[: min(CHUNK, size - sent)]
        sent += len(piece)
        yield piece


def big_mp4_sha256(size: int = BIG_SIZE) -> str:
    digest = hashlib.sha256()
    for piece in big_mp4_chunks(size):
        digest.update(piece)
    return digest.hexdigest()


class LiveServer:
    """uvicorn in a thread on a free port; the same app object (and in-memory DB) as the TestClient."""

    def __init__(self, app) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning", lifespan="off")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> "LiveServer":
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return self
            time.sleep(0.05)
        raise RuntimeError("live server did not start")

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def connection(self) -> http.client.HTTPConnection:
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)


def cookie_header(client: TestClient) -> str:
    return "; ".join(f"{name}={value}" for name, value in client.cookies.items())


def product_with_file_resource(owner: TestClient) -> tuple[str, str, str]:
    """Held event + sellable product; returns (event_id, resource_id, recording_id)."""
    event_id, _version = held_event(owner, 0)
    product = build_sellable_product(owner, event_id, price=500_000, payment_card=None)
    recording_id = product["recording"]["id"]
    purchase_form(owner, recording_id, price=500_000)  # paid products publish only behind a published purchase form
    return event_id, product["_resource_id"], recording_id


def chunked_put(live: LiveServer, path: str, headers: dict[str, str], pieces) -> http.client.HTTPResponse:
    conn = live.connection()
    conn.putrequest("PUT", path)
    for name, value in headers.items():
        conn.putheader(name, value)
    conn.endheaders()
    for piece in pieces:
        conn.send(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
    conn.send(b"0\r\n\r\n")
    return conn.getresponse()


def ranged_get(live: LiveServer, path: str, cookie: str, range_header: str | None = None) -> http.client.HTTPResponse:
    conn = live.connection()
    headers = {"Cookie": cookie}
    if range_header:
        headers["Range"] = range_header
    conn.request("GET", path, headers=headers)
    return conn.getresponse()


# ── storage unit behaviour ──


def test_local_storage_refuses_webroot_and_unsafe_keys(tmp_path):
    with pytest.raises(storage_mod.StorageError) as refused:
        storage_mod.LocalPrivateStorage(UI_ROOT / "uploads", max_bytes=1024, forbidden_parents=(UI_ROOT,))
    assert refused.value.code == "storage_inside_webroot"
    store = storage_mod.LocalPrivateStorage(tmp_path / "store", max_bytes=1024, forbidden_parents=(UI_ROOT,))
    assert stat.S_IMODE((tmp_path / "store").stat().st_mode) == 0o700
    for bad in ("../../etc/passwd", "2026/10/../../x", "2026/10/zz", "", "2026/10/" + "a" * 32 + "/x", "/abs"):
        with pytest.raises(storage_mod.StorageError):
            store.resolve(bad)
        assert store.exists(bad) is False and store.size(bad) is None and store.delete(bad) is False
    key = store.new_key()
    assert storage_mod.KEY_PATTERN.fullmatch(key) and store.exists(key) is False


def test_local_storage_stages_atomically_and_aborts_cleanly(tmp_path):
    store = storage_mod.LocalPrivateStorage(tmp_path / "store", max_bytes=10, forbidden_parents=(UI_ROOT,))
    incoming = tmp_path / "store" / storage_mod.INCOMING_DIR
    pending = store.begin()
    pending.write(b"12345")
    staged = list(incoming.iterdir())
    assert len(staged) == 1 and staged[0].suffix == ".part" and stat.S_IMODE(staged[0].stat().st_mode) == 0o600
    assert list(store.list_keys()) == []  # nothing visible before commit
    with pytest.raises(storage_mod.StorageError) as too_big:
        pending.write(b"1234567")  # 5 + 7 > 10
    assert too_big.value.code == "file_too_large"
    pending.abort()
    assert list(incoming.iterdir()) == [] and list(store.list_keys()) == []

    pending = store.begin()
    pending.write(b"hello ")
    pending.write(b"nora")
    stored = pending.commit()
    assert stored.size == 10 and stored.sha256 == hashlib.sha256(b"hello nora").hexdigest()
    assert store.exists(stored.key) and store.size(stored.key) == 10 and list(store.list_keys()) == [stored.key]
    assert b"".join(store.open_range(stored.key, 6, 9)) == b"nora"
    assert list(incoming.iterdir()) == []
    assert store.delete(stored.key) is True and store.delete(stored.key) is False
    status = store.status()
    assert status.configured and status.backend == "local_disk" and status.max_bytes == 10 and status.writable is True


# ── real HTTP: bounded memory on upload and ranged download, per-request authorization ──


def test_large_file_streams_to_disk_and_back_over_real_http_without_buffering(tmp_path):
    app, engine = storage_app(tmp_path)
    store_root = tmp_path / "private-store"
    incoming = store_root / storage_mod.INCOMING_DIR
    try:
        with TestClient(app) as owner, LiveServer(app) as live:
            owner_login(owner)
            event_id, resource_id, _recording_id = product_with_file_resource(owner)
            limits = owner.get(f"/api/admin/events/{event_id}/resources").json()["limits"]
            assert limits["storage"]["configured"] is True and limits["storage"]["backend"] == "local_disk"
            assert limits["max_bytes"] == 256 * 1024 * 1024 and limits["inline_max_bytes"] == 8 * 1024 * 1024
            upload_path = f"/api/admin/events/{event_id}/resources/{resource_id}/file"
            upload_headers = {
                "Cookie": cookie_header(owner), "Origin": live.origin, "X-CSRF-Token": owner.cookies.get("nora_csrf", ""),
                "X-File-Name": "lecture-02.mp4", "Transfer-Encoding": "chunked", "Content-Type": "application/octet-stream",
            }

            tracemalloc.start()
            response = chunked_put(live, upload_path, upload_headers, big_mp4_chunks())
            body = response.read()
            _current, upload_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert response.status == 200, body[:300]
            assert upload_peak < MEMORY_CEILING, f"upload buffered in memory: peak={upload_peak}"
            view = json.loads(body)
            assert view["size"] == BIG_SIZE and view["content_type"] == "video/mp4" and view["file_name"] == "lecture-02.mp4"
            assert view["storage"] == {"backend": "local_disk", "state": "ready"}
            assert "storage_key" not in view and "private-store" not in body.decode()
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row is not None and row.content is None and row.storage_key and row.content_hash == big_mp4_sha256()
                key = row.storage_key
            path = store_root / key
            assert path.is_file() and path.stat().st_size == BIG_SIZE and stat.S_IMODE(path.stat().st_mode) == 0o600
            assert UI_ROOT not in path.parents and list(incoming.iterdir()) == []

            # Publish and grant; the holder streams it back with Range through the real server.
            assert owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}", json={"status": "published"},
                             headers=owner_write_headers(owner)).status_code == 200
            assert set_status(owner, event_id, "ready").status_code == 200
            went_live = set_status(owner, event_id, "published")
            assert went_live.status_code == 200, went_live.text
            holder = TestClient(app)
            holder_id = bale_login(holder, 97001)
            grant = owner.post(f"/api/admin/events/{event_id}/recording/access",
                               json={"account_id": holder_id, "reason": "آزمون ۹.۴"}, headers=owner_write_headers(owner))
            assert grant.status_code == 201, grant.text
            download = f"/api/public/events/{event_id}/resources/{resource_id}/download"
            holder_cookie = cookie_header(holder)

            tracemalloc.start()
            full = ranged_get(live, download, holder_cookie)
            digest, received = hashlib.sha256(), 0
            while True:
                piece = full.read(CHUNK)
                if not piece:
                    break
                digest.update(piece)
                received += len(piece)
            _current, download_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert full.status == 200 and received == BIG_SIZE and digest.hexdigest() == big_mp4_sha256()
            assert full.getheader("Accept-Ranges") == "bytes" and full.getheader("Content-Length") == str(BIG_SIZE)
            assert full.getheader("Content-Encoding") == "identity" and "no-store" in (full.getheader("Cache-Control") or "")
            assert "inline" in (full.getheader("Content-Disposition") or "") and full.getheader("X-Nora-Resource-Access") == "purchased"
            leaked = str(full.getheaders())
            assert "private-store" not in leaked and key not in leaked
            assert download_peak < MEMORY_CEILING, f"download buffered in memory: peak={download_peak}"

            # Valid ranges: middle, open-ended tail, suffix, over-long end; invalid: beyond EOF, inverted, empty.
            expected = b"".join(big_mp4_chunks())
            for header, start, end in (
                ("bytes=1048576-1048579", 1048576, 1048579),
                (f"bytes={BIG_SIZE - 10}-", BIG_SIZE - 10, BIG_SIZE - 1),
                ("bytes=-16", BIG_SIZE - 16, BIG_SIZE - 1),
                (f"bytes=0-{BIG_SIZE + 999}", 0, BIG_SIZE - 1),
            ):
                part = ranged_get(live, download, holder_cookie, header)
                data = part.read()
                assert part.status == 206, header
                assert part.getheader("Content-Range") == f"bytes {start}-{end}/{BIG_SIZE}"
                assert part.getheader("Content-Length") == str(end - start + 1) and data == expected[start:end + 1]
            for header in (f"bytes={BIG_SIZE}-", "bytes=10-5", "bytes=-"):
                bad = ranged_get(live, download, holder_cookie, header)
                bad.read()
                assert bad.status == 416 and bad.getheader("Content-Range") == f"bytes */{BIG_SIZE}", header
            multi = ranged_get(live, download, holder_cookie, "bytes=0-1,5-6")
            assert multi.status == 200 and len(multi.read()) == BIG_SIZE  # multi-range → whole body, never 500

            # Authorization is per request: stranger 403, guest 401, revoked holder 403 on the very next request.
            stranger = TestClient(app)
            bale_login(stranger, 97002)
            assert stranger.get(download).status_code == 403
            assert stranger.get(download, headers={"Range": "bytes=0-1"}).status_code == 403
            assert TestClient(app).get(download).status_code == 401
            access_id = grant.json()["access"]["id"]
            assert owner.post(f"/api/admin/events/{event_id}/recording/access/{access_id}/revoke",
                              json={"reason": "آزمون لغو"}, headers=owner_write_headers(owner)).status_code == 200
            assert holder.get(download).status_code == 403
            assert holder.get(download, headers={"Range": "bytes=0-1"}).status_code == 403
            regrant = owner.post(f"/api/admin/events/{event_id}/recording/access",
                                 json={"account_id": holder_id, "reason": "بازگردانی"}, headers=owner_write_headers(owner))
            assert regrant.status_code in (200, 201), regrant.text
            assert holder.get(download, headers={"Range": "bytes=0-1"}).status_code == 206

            # Replacement: a small (inline-sized) file still goes to disk; new key, old file pruned, access rows kept.
            small = MP4 + b"\x00" * 2048
            replaced = owner.put(upload_path, content=small, headers={**owner_write_headers(owner), "X-File-Name": "lecture-02-v2.mp4"})
            assert replaced.status_code == 200, replaced.text
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row is not None and row.storage_key and row.storage_key != key and row.content is None
                new_key = row.storage_key
                statuses = db.scalars(select(RecordingAccessRecord.status).where(RecordingAccessRecord.account_id == holder_id)).all()
                assert statuses == ["active"]  # the re-granted row is untouched by the file replacement
            assert not path.exists() and (store_root / new_key).is_file() and list(incoming.iterdir()) == []
            assert holder.get(download).content == small

            # Rejections never touch the row or the disk: wrong type, aborted body.
            before = (store_root / new_key).stat().st_mtime_ns
            assert owner.put(upload_path, content=b"MZ\x90\x00" + b"\x00" * 64,
                             headers={**owner_write_headers(owner), "X-File-Name": "evil.exe"}).status_code == 415
            conn = live.connection()
            conn.putrequest("PUT", upload_path)
            for name, value in {**upload_headers, "X-File-Name": "aborted.mp4"}.items():
                conn.putheader(name, value)
            conn.endheaders()
            conn.send(f"{len(MP4):x}\r\n".encode() + MP4 + b"\r\n")
            conn.close()  # the client goes away mid-body
            for _ in range(40):
                if list(incoming.iterdir()) == []:
                    break
                time.sleep(0.1)
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row is not None and row.storage_key == new_key and row.content_size == len(small)
            assert (store_root / new_key).stat().st_mtime_ns == before and list(incoming.iterdir()) == []
            assert list(storage_mod.LocalPrivateStorage(store_root, max_bytes=1).list_keys()) == [new_key]

            # The file vanishes from disk → panel says "missing", nobody is served bytes, publishing is refused.
            (store_root / new_key).unlink()
            listing = owner.get(f"/api/admin/events/{event_id}/resources").json()["items"]
            assert next(i for i in listing if i["id"] == resource_id)["storage"] == {"backend": "local_disk", "state": "missing"}
            assert holder.get(download).status_code == 404
            assert owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}", json={"status": "draft"},
                             headers=owner_write_headers(owner)).status_code == 200
            assert owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}", json={"status": "published"},
                             headers=owner_write_headers(owner)).status_code == 409
    finally:
        engine.dispose()


def test_oversize_upload_is_rejected_at_the_configured_cap_without_leftovers(tmp_path):
    app, engine = storage_app(tmp_path, max_bytes=9 * 1024 * 1024)
    store_root = tmp_path / "private-store"
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, resource_id, _recording_id = product_with_file_resource(owner)
            with Session(engine) as db:
                original = db.get(EventResourceRecord, resource_id)
                assert original is not None and original.storage_key  # the helper's small MP4 already went to disk
                original_key = original.storage_key
            too_big = owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}/file",
                                content=b"".join(big_mp4_chunks(10 * 1024 * 1024)),
                                headers={**owner_write_headers(owner), "X-File-Name": "big.mp4"})
            assert too_big.status_code == 413
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row is not None and row.storage_key == original_key
            assert list((store_root / storage_mod.INCOMING_DIR).iterdir()) == []
            assert list(storage_mod.LocalPrivateStorage(store_root, max_bytes=1).list_keys()) == [original_key]
    finally:
        engine.dispose()


def test_without_private_storage_nothing_changes(tmp_path):
    app, engine = storage_app(tmp_path, configured=False)
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, resource_id, _recording_id = product_with_file_resource(owner)
            limits = owner.get(f"/api/admin/events/{event_id}/resources").json()["limits"]
            assert limits["storage"]["configured"] is False and limits["storage"]["backend"] == "database"
            assert limits["max_bytes"] == 8 * 1024 * 1024
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row is not None and row.storage_key is None and row.content == MP4
            big = owner.put(f"/api/admin/events/{event_id}/resources/{resource_id}/file",
                            content=b"".join(big_mp4_chunks(9 * 1024 * 1024)),
                            headers={**owner_write_headers(owner), "X-File-Name": "big.mp4"})
            assert big.status_code == 413
            item = owner.get(f"/api/admin/events/{event_id}/resources").json()["items"][0]
            assert item["storage"] == {"backend": "database", "state": "ready"}
            assert not (tmp_path / "private-store").exists()
    finally:
        engine.dispose()


# ── backup / restore of the files that live outside the database ──


def run_backup_tool(*args: str, db_url: str, store: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "NORA_DATABASE_URL": db_url, "NORA_PRIVATE_STORAGE_DIR": str(store)}
    return subprocess.run([sys.executable, str(BACKEND_ROOT.parent / "tools" / "private-storage-backup.py"), *args],
                          capture_output=True, text=True, env=env, cwd=BACKEND_ROOT.parent, timeout=120)


def test_backup_snapshot_restores_files_that_rows_point_at(tmp_path):
    db_path = tmp_path / "nora.db"
    db_url = f"sqlite+pysqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    store = tmp_path / "private-store"
    settings = Settings(
        database_url=None, owner_id="owner-01", owner_username="nora-owner",
        owner_password_hash=hash_password("correct-horse-staple-42"), cookie_secure=False,
        bale_bot_token=BOT_TOKEN, bot_service_token=SERVICE_TOKEN, owner_bale_user_id="70001",
        private_storage_dir=str(store), private_storage_max_bytes=64 * 1024 * 1024,
    )
    app = create_app(settings, engine=engine)
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            event_id, resource_id, _recording_id = product_with_file_resource(owner)
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row is not None and row.storage_key
                key, digest = row.storage_key, row.content_hash
            # An orphan (file without a row) and a stale staging part must be reported, never silently deleted.
            orphan = store / "2020" / "01" / ("f" * 32)
            orphan.parent.mkdir(parents=True, exist_ok=True)
            orphan.write_bytes(b"orphan")
            (store / storage_mod.INCOMING_DIR / "stale.part").write_bytes(b"half")

            verified = run_backup_tool("verify", db_url=db_url, store=store)
            assert verified.returncode == 0, verified.stdout + verified.stderr
            report = json.loads(verified.stdout)
            assert report["referenced"] == 1 and report["missing"] == [] and report["size_mismatch"] == []
            assert report["orphans"] == ["2020/01/" + "f" * 32] and report["stale_parts"] == ["stale.part"]
            assert orphan.exists() and (store / storage_mod.INCOMING_DIR / "stale.part").exists()

            snapshot = tmp_path / "snapshot"
            taken = run_backup_tool("snapshot", str(snapshot), db_url=db_url, store=store)
            assert taken.returncode == 0, taken.stdout + taken.stderr
            assert (snapshot / key).is_file() and (snapshot / "MANIFEST.json").is_file()
            manifest = json.loads((snapshot / "MANIFEST.json").read_text(encoding="utf-8"))
            assert manifest["files"][key]["sha256"] == digest and "stale.part" not in json.dumps(manifest)

            # Disaster: the storage directory is lost; the row now points at a missing file.
            shutil.rmtree(store)
            broken = run_backup_tool("verify", db_url=db_url, store=store)
            assert broken.returncode == 1 and json.loads(broken.stdout)["missing"] == [key]
            with TestClient(app) as owner_again:
                owner_login(owner_again)
                item = owner_again.get(f"/api/admin/events/{event_id}/resources").json()["items"][0]
                assert item["storage"]["state"] == "missing"

            # Restore from the snapshot (hashes re-checked) → rows and files agree again.
            restored = run_backup_tool("restore", str(snapshot), db_url=db_url, store=store)
            assert restored.returncode == 0, restored.stdout + restored.stderr
            assert (store / key).is_file() and hashlib.sha256((store / key).read_bytes()).hexdigest() == digest
            assert stat.S_IMODE((store / key).stat().st_mode) == 0o600
            ok_again = run_backup_tool("verify", db_url=db_url, store=store)
            assert ok_again.returncode == 0 and json.loads(ok_again.stdout)["missing"] == []
            with TestClient(app) as owner_again:
                owner_login(owner_again)
                item = owner_again.get(f"/api/admin/events/{event_id}/resources").json()["items"][0]
                assert item["storage"] == {"backend": "local_disk", "state": "ready"}
                # Phase 9.5: every tool run leaves a marker that the read-only health view reports
                # (last verify / snapshot / restore), without paths or secrets.
                health = owner_again.get("/api/admin/storage/health")
                assert health.status_code == 200
                markers = health.json()["markers"]
                assert markers["storage_verify"]["ok"] is True and markers["storage_verify"]["at"]
                assert markers["storage_verify"]["orphans"] == 1 and markers["storage_verify"]["stale_parts"] == 0
                assert markers["storage_snapshot"]["ok"] is True and markers["storage_snapshot"]["files"] == 2  # referenced + orphan (snapshots never drop files)
                assert markers["storage_restore"]["ok"] is True and markers["storage_restore"]["restored"] == 2
                assert "scheduled_publish" not in markers
                assert str(store) not in json.dumps(health.json())
            # --no-marker leaves the recorded state untouched (operator dry runs).
            with Session(engine) as db:
                before = {m.key: m.updated_at for m in db.query(SystemMarkerRecord).all()}
            assert run_backup_tool("verify", "--no-marker", db_url=db_url, store=store).returncode == 0
            with Session(engine) as db:
                assert {m.key: m.updated_at for m in db.query(SystemMarkerRecord).all()} == before
    finally:
        engine.dispose()
