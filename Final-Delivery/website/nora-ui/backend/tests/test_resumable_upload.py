"""Phase 9.5 §5.2/§5.3: resumable upload sessions + storage health — real HTTP, real files.

Proven here (and nothing more):

* a 12 MiB MP4 goes up in 4 MiB chunks through a REAL uvicorn server, the connection is cut in the
  middle of a chunk, the client asks the server for the offset and resumes from there; the final
  file is byte-identical (sha256) and is streamed back with Range;
* the rule matrix over the in-process client: wrong/duplicate/stale offset → 409 with the real
  offset, bad chunk checksum → 400 and the bytes are gone again, chunk over the cap → 413, size over
  the storage cap → 413 at session start, whole-file sha256 mismatch → 422 and no file committed,
  a second ``complete`` while the first one holds the lock → 409, expired session → 410 and the part
  is removed, abort removes the part, another actor cannot touch the session, CSRF/role enforced;
* near-cap upload (cap 20 MiB, file 20 MiB − 1 KiB) succeeds and one byte over the cap is refused
  before any byte is written;
* replacing the bytes keeps access rows and prunes the old key; the DB row and the file agree;
* ``GET /api/admin/storage/health`` reports referenced/missing/orphan/incomplete honestly and
  changes nothing.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT.parent))

from backend import storage as storage_mod  # noqa: E402
from backend import upload_sessions as upload_mod  # noqa: E402
from backend.models import EventResourceRecord, RecordingAccessRecord, UploadSessionRecord  # noqa: E402
from test_private_storage import (  # noqa: E402
    LiveServer,
    big_mp4_chunks,
    big_mp4_sha256,
    cookie_header,
    product_with_file_resource,
    ranged_get,
    storage_app,
)
from test_recordings_api import MP4  # noqa: E402
from test_workflows_api import account_write_headers, bale_login, owner_login, owner_write_headers  # noqa: E402

MIB = 1024 * 1024
CHUNK = 4 * MIB


def sessions_path(event_id: str, resource_id: str) -> str:
    return f"/api/admin/events/{event_id}/resources/{resource_id}/upload-sessions"


def file_bytes(size: int) -> bytes:
    return b"".join(big_mp4_chunks(size))


def chunk_headers(owner: TestClient, offset: int, body: bytes) -> dict[str, str]:
    return {**owner_write_headers(owner), "Upload-Offset": str(offset), "Upload-Checksum": "sha256 " + hashlib.sha256(body).hexdigest(),
            "Content-Type": "application/octet-stream"}


def start(owner: TestClient, base: str, size: int, *, sha256: str | None = None, name: str = "جلسه.mp4"):
    payload = {"size": size, "file_name": name}
    if sha256:
        payload["sha256"] = sha256
    return owner.post(base, json=payload, headers=owner_write_headers(owner))


def push(owner: TestClient, base: str, sid: str, offset: int, body: bytes):
    return owner.patch(f"{base}/{sid}", content=body, headers=chunk_headers(owner, offset, body))


def upload_all(owner: TestClient, base: str, data: bytes, *, chunk: int = CHUNK) -> dict:
    opened = start(owner, base, len(data), sha256=hashlib.sha256(data).hexdigest())
    assert opened.status_code == 201, opened.text
    sid = opened.json()["id"]
    offset = 0
    while offset < len(data):
        piece = data[offset: offset + chunk]
        pushed = push(owner, base, sid, offset, piece)
        assert pushed.status_code == 200, pushed.text
        offset = pushed.json()["offset"]
    done = owner.post(f"{base}/{sid}/complete", json={}, headers=owner_write_headers(owner))
    assert done.status_code == 200, done.text
    return done.json()


def part_files(tmp_path: Path) -> list[Path]:
    incoming = tmp_path / "private-store" / storage_mod.INCOMING_DIR
    return sorted(incoming.iterdir()) if incoming.is_dir() else []


# ── real server: disconnect in the middle, resume from the server's offset ──


def test_live_server_upload_survives_a_disconnect_and_resumes_from_the_server_offset(tmp_path):
    size = 12 * MIB
    app, engine = storage_app(tmp_path, max_bytes=64 * MIB)
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, resource_id, recording_id = product_with_file_resource(owner)
        base = sessions_path(event_id, resource_id)
        data = file_bytes(size)
        digest = big_mp4_sha256(size)
        cookie = cookie_header(owner)
        csrf = owner.cookies.get("nora_csrf")
        with LiveServer(app) as live:
            common = {"Cookie": cookie, "Origin": live.origin, "X-CSRF-Token": csrf}
            conn = live.connection()
            conn.request("POST", base, body=json.dumps({"size": size, "sha256": digest, "file_name": "big.mp4"}),
                         headers={**common, "Content-Type": "application/json"})
            opened = conn.getresponse()
            session = json.loads(opened.read())
            assert opened.status == 201 and session["offset"] == 0 and session["chunk_bytes"] == CHUNK
            sid = session["id"]

            # chunk 1 complete
            first = data[:CHUNK]
            conn = live.connection()
            conn.request("PATCH", f"{base}/{sid}", body=first, headers={**common, "Upload-Offset": "0",
                         "Upload-Checksum": "sha256 " + hashlib.sha256(first).hexdigest(), "Content-Type": "application/octet-stream"})
            pushed = conn.getresponse()
            assert pushed.status == 200 and json.loads(pushed.read())["offset"] == CHUNK

            # chunk 2: the connection dies after half the body (declared length never arrives)
            second = data[CHUNK: 2 * CHUNK]
            broken = live.connection()
            broken.putrequest("PATCH", f"{base}/{sid}")
            for name, value in {**common, "Upload-Offset": str(CHUNK), "Content-Length": str(len(second)),
                                "Upload-Checksum": "sha256 " + hashlib.sha256(second).hexdigest(),
                                "Content-Type": "application/octet-stream"}.items():
                broken.putheader(name, value)
            broken.endheaders()
            broken.send(second[: len(second) // 2])
            broken.sock.close()

            # the client asks where to resume: the server answers with what is really on disk
            conn = live.connection()
            conn.request("GET", f"{base}/{sid}", headers={"Cookie": cookie})
            status = conn.getresponse()
            state = json.loads(status.read())
            assert status.status == 200 and state["status"] == "open" and state["offset"] == CHUNK, state

            offset = state["offset"]
            while offset < size:
                piece = data[offset: offset + CHUNK]
                conn = live.connection()
                conn.request("PATCH", f"{base}/{sid}", body=piece, headers={**common, "Upload-Offset": str(offset),
                             "Upload-Checksum": "sha256 " + hashlib.sha256(piece).hexdigest(), "Content-Type": "application/octet-stream"})
                pushed = conn.getresponse()
                body = json.loads(pushed.read())
                assert pushed.status == 200, body
                offset = body["offset"]
            assert body["complete"] is True and body["chunk_count"] == 3

            conn = live.connection()
            conn.request("POST", f"{base}/{sid}/complete", body="{}", headers={**common, "Content-Type": "application/json"})
            done = conn.getresponse()
            saved = json.loads(done.read())
            assert done.status == 200, saved
            assert saved["size"] == size and saved["storage"] == {"backend": "local_disk", "state": "ready"}
            assert saved["upload_session"]["status"] == "completed" and saved["upload_session"]["chunk_count"] == 3

            # row ↔ bytes agree; the part is gone; download streams with Range after a real grant
            with Session(engine) as db:
                row = db.get(EventResourceRecord, resource_id)
                assert row.content is None and row.content_size == size and row.content_hash == digest
                disk = tmp_path / "private-store" / row.storage_key
                assert disk.stat().st_size == size and hashlib.sha256(disk.read_bytes()).hexdigest() == digest
            assert part_files(tmp_path) == []
            holder = TestClient(app)
            holder_id = bale_login(holder, 97001)
            grant = owner.post(f"/api/admin/events/{event_id}/recording/access",
                               json={"account_id": holder_id, "reason": "آزمون آپلود قطعه‌ای"}, headers=owner_write_headers(owner))
            assert grant.status_code in (200, 201), grant.text
            download = f"/api/public/events/{event_id}/resources/{resource_id}/download"
            partial = ranged_get(live, download, cookie_header(holder), "bytes=4-7")
            assert partial.status == 206 and partial.read() == b"ftyp"
            tail = ranged_get(live, download, cookie_header(holder), f"bytes={size - 16}-")
            assert tail.status == 206 and tail.read() == data[-16:]


# ── rule matrix over the in-process client ──


def test_resumable_rules_offsets_checksums_caps_and_locking(tmp_path):
    cap = 20 * MIB
    app, engine = storage_app(tmp_path, max_bytes=cap)
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, resource_id, recording_id = product_with_file_resource(owner)
        base = sessions_path(event_id, resource_id)
        data = file_bytes(9 * MIB + 123)
        digest = hashlib.sha256(data).hexdigest()

        # start: validation
        assert start(owner, base, 0).status_code == 422
        assert start(owner, base, cap + 1).status_code == 413
        assert owner.post(base, json={"size": 10, "file_name": "x", "extra": 1}, headers=owner_write_headers(owner)).status_code == 400
        assert owner.post(base, json={"size": 10, "file_name": "x"}).status_code == 403  # CSRF
        opened = start(owner, base, len(data), sha256=digest)
        assert opened.status_code == 201 and opened.json()["offset"] == 0 and opened.json()["expected_size"] == len(data)
        sid = opened.json()["id"]
        # same actor, same file → resumed (no second part)
        again = start(owner, base, len(data), sha256=digest)
        assert again.status_code == 200 and again.json()["id"] == sid and again.json()["resumed"] is True
        assert len(part_files(tmp_path)) == 1

        # chunks: header rules
        first = data[:CHUNK]
        assert owner.patch(f"{base}/{sid}", content=first, headers={**owner_write_headers(owner), "Upload-Offset": "0"}).status_code == 400
        assert owner.patch(f"{base}/{sid}", content=first, headers={**owner_write_headers(owner), "Upload-Checksum": "sha256 " + "0" * 64}).status_code == 400
        wrong_sum = owner.patch(f"{base}/{sid}", content=first, headers={**owner_write_headers(owner), "Upload-Offset": "0", "Upload-Checksum": "sha256 " + "0" * 64})
        assert wrong_sum.status_code == 400 and wrong_sum.json()["detail"]["code"] == "chunk_checksum_mismatch"
        assert owner.get(f"{base}/{sid}").json()["offset"] == 0  # nothing kept
        assert push(owner, base, sid, 0, b"").status_code == 400
        stale = push(owner, base, sid, CHUNK, first)  # out of order
        assert stale.status_code == 409 and stale.json()["detail"] == {"code": "offset_mismatch", "offset": 0}
        ok = push(owner, base, sid, 0, first)
        assert ok.status_code == 200 and ok.json()["offset"] == CHUNK and ok.json()["complete"] is False
        dup = push(owner, base, sid, 0, first)  # duplicate / retry of an accepted chunk
        assert dup.status_code == 409 and dup.json()["detail"]["offset"] == CHUNK
        too_big = owner.patch(f"{base}/{sid}", content=b"x" * (upload_mod.MAX_CHUNK_BYTES + 1), headers=chunk_headers(owner, CHUNK, b"x"))
        assert too_big.status_code == 413 and too_big.json()["detail"]["code"] == "chunk_too_large"
        overflow = push(owner, base, sid, CHUNK, b"y" * (len(data) - CHUNK + 1))
        assert overflow.status_code == 413 and overflow.json()["detail"]["code"] == "chunk_exceeds_expected_size"
        # premature complete
        early = owner.post(f"{base}/{sid}/complete", json={}, headers=owner_write_headers(owner))
        assert early.status_code == 409 and early.json()["detail"]["code"] == "upload_incomplete" and early.json()["detail"]["offset"] == CHUNK

        # another actor (manager with ev_create) cannot see or touch the session
        other = TestClient(app)
        other_id = bale_login(other, 97002)
        from test_workflows_api import assign_manager
        manager = TestClient(app)
        assign_manager(manager, other_id)
        assert manager.get(f"{base}/{sid}").status_code == 404
        assert manager.patch(f"{base}/{sid}", content=first, headers={**account_write_headers(manager), "Upload-Offset": str(CHUNK),
                             "Upload-Checksum": "sha256 " + hashlib.sha256(first).hexdigest()}).status_code == 404
        blocked = manager.post(base, json={"size": 10, "file_name": "x"}, headers=account_write_headers(manager))
        assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "upload_session_open_by_other"
        guest = TestClient(app)
        assert guest.get(f"{base}/{sid}").status_code == 401

        # finish the upload
        offset = CHUNK
        while offset < len(data):
            piece = data[offset: offset + CHUNK]
            pushed = push(owner, base, sid, offset, piece)
            assert pushed.status_code == 200, pushed.text
            offset = pushed.json()["offset"]
        extra = push(owner, base, sid, offset, b"z")
        assert extra.status_code == 413  # complete sessions accept nothing more
        # whole-file sha256 conflicting with the declared one → refused before hashing
        conflict = owner.post(f"{base}/{sid}/complete", json={"sha256": "f" * 64}, headers=owner_write_headers(owner))
        assert conflict.status_code == 422 and conflict.json()["detail"]["code"] == "sha256_conflict"
        done = owner.post(f"{base}/{sid}/complete", json={}, headers=owner_write_headers(owner))
        assert done.status_code == 200 and done.json()["size"] == len(data) and done.json()["content_type"] == "video/mp4"
        twice = owner.post(f"{base}/{sid}/complete", json={}, headers=owner_write_headers(owner))
        assert twice.status_code == 410 and twice.json()["detail"]["code"] == "upload_session_completed"
        assert part_files(tmp_path) == []
        with Session(engine) as db:
            row = db.get(EventResourceRecord, resource_id)
            first_key = row.storage_key
            assert row.content_hash == digest and (tmp_path / "private-store" / first_key).stat().st_size == len(data)
            session_row = db.get(UploadSessionRecord, sid)
            assert session_row.status == "completed" and session_row.storage_key == first_key and session_row.chunk_count == 3

        # sha256 mismatch at complete: nothing committed, the part is removed, the previous file stays
        other_data = file_bytes(5 * MIB)
        bad = start(owner, base, len(other_data), sha256="a" * 64)
        bad_sid = bad.json()["id"]
        push(owner, base, bad_sid, 0, other_data[:CHUNK])
        push(owner, base, bad_sid, CHUNK, other_data[CHUNK:])
        mismatch = owner.post(f"{base}/{bad_sid}/complete", json={}, headers=owner_write_headers(owner))
        assert mismatch.status_code == 422 and mismatch.json()["detail"]["code"] == "sha256_mismatch"
        assert part_files(tmp_path) == []
        with Session(engine) as db:
            assert db.get(EventResourceRecord, resource_id).storage_key == first_key
            assert db.get(UploadSessionRecord, bad_sid).status == "failed"
        # without any sha256 the upload cannot be completed
        nosum = start(owner, base, 16)
        nosum_sid = nosum.json()["id"]
        push(owner, base, nosum_sid, 0, b"x" * 16)
        assert owner.post(f"{base}/{nosum_sid}/complete", json={}, headers=owner_write_headers(owner)).status_code == 422
        assert owner.delete(f"{base}/{nosum_sid}", headers=owner_write_headers(owner)).json()["status"] == "aborted"
        assert part_files(tmp_path) == []

        # a session that is not a real media file is refused at complete (sniffed like the single-request path)
        html = b"<html><body>x</body></html>" + b"\0" * 100
        sniff = start(owner, base, len(html), sha256=hashlib.sha256(html).hexdigest(), name="page.mp4")
        push(owner, base, sniff.json()["id"], 0, html)
        refused = owner.post(f"{base}/{sniff.json()['id']}/complete", json={}, headers=owner_write_headers(owner))
        assert refused.status_code == 415 and part_files(tmp_path) == []

        # replace: near-cap file (cap − 1 KiB) through the resumable path; the old key is pruned; access rows stay
        holder = TestClient(app)
        holder_id = bale_login(holder, 97003)
        assert owner.post(f"/api/admin/events/{event_id}/recording/access", json={"account_id": holder_id, "reason": "آزمون جایگزینی"},
                          headers=owner_write_headers(owner)).status_code in (200, 201)
        near = file_bytes(cap - 1024)
        saved = upload_all(owner, base, near)
        assert saved["size"] == cap - 1024 and saved["storage"]["state"] == "ready"
        with Session(engine) as db:
            row = db.get(EventResourceRecord, resource_id)
            assert row.storage_key != first_key and not (tmp_path / "private-store" / first_key).exists()
            assert (tmp_path / "private-store" / row.storage_key).stat().st_size == cap - 1024
            assert db.scalar(select(RecordingAccessRecord).where(RecordingAccessRecord.account_id == holder_id)).status == "active"
        over = start(owner, base, cap + 1, sha256=digest)
        assert over.status_code == 413 and over.json()["detail"]["max_bytes"] == cap
        assert part_files(tmp_path) == []
        served = holder.get(f"/api/public/events/{event_id}/resources/{resource_id}/download", headers={"Range": "bytes=0-3"})
        assert served.status_code == 206 and served.content == near[:4]

        # expiry: an open session past its TTL answers 410 and its part is removed
        late = start(owner, base, 2 * MIB, sha256="b" * 64)
        late_sid = late.json()["id"]
        push(owner, base, late_sid, 0, b"q" * MIB)
        assert len(part_files(tmp_path)) == 1
        with Session(engine) as db:
            row = db.get(UploadSessionRecord, late_sid)
            row.expires_at = row.expires_at - timedelta(hours=25)
            db.commit()
        expired = owner.get(f"{base}/{late_sid}")
        assert expired.status_code == 200 and expired.json()["status"] == "expired"
        assert push(owner, base, late_sid, MIB, b"q").status_code == 410
        assert part_files(tmp_path) == []

        # the audit trail names the session and the resumable path
        from test_event_interaction_api import audit_actions
        actions = audit_actions(engine)
        assert {"event_resource.upload_session", "event_resource.file", "event_resource.file_pruned", "event_resource.upload_abort"} <= set(actions)


def test_complete_is_single_winner_under_concurrency(tmp_path):
    """Two finalizers race: exactly one commits; the other sees the lock (409) or the final state (410)."""
    import threading

    app, engine = storage_app(tmp_path, max_bytes=8 * MIB)
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, resource_id, _recording_id = product_with_file_resource(owner)
        base = sessions_path(event_id, resource_id)
        data = file_bytes(3 * MIB)
        opened = start(owner, base, len(data), sha256=hashlib.sha256(data).hexdigest())
        sid = opened.json()["id"]
        assert push(owner, base, sid, 0, data).status_code == 200
        cookie = cookie_header(owner)
        csrf = owner.cookies.get("nora_csrf")
        results: list[int] = []
        with LiveServer(app) as live:
            def finish() -> None:
                conn = live.connection()
                conn.request("POST", f"{base}/{sid}/complete", body="{}", headers={
                    "Cookie": cookie, "Origin": live.origin, "X-CSRF-Token": csrf, "Content-Type": "application/json"})
                response = conn.getresponse()
                response.read()
                results.append(response.status)
            threads = [threading.Thread(target=finish) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=60)
        assert sorted(results).count(200) == 1 and set(results) <= {200, 409, 410}, results
        with Session(engine) as db:
            row = db.get(EventResourceRecord, resource_id)
            assert row.content_size == len(data)
            assert [p.name for p in (tmp_path / "private-store").glob("*/*/*")] == [row.storage_key.split("/")[-1]]  # old key pruned, one final file
        assert part_files(tmp_path) == []


def test_resumable_requires_private_storage_and_health_is_honest(tmp_path):
    # without the private store the protocol is refused explicitly; health says so
    app, _engine = storage_app(tmp_path, configured=False)
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, resource_id, _ = product_with_file_resource(owner)
        refused = start(owner, sessions_path(event_id, resource_id), 10)
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "resumable_requires_private_storage"
        health = owner.get("/api/admin/storage/health")
        assert health.status_code == 200 and health.json()["configured"] is False and health.json()["state"] == "inline_only"
        assert health.json()["inline"]["rows"] == 1 and health.json()["read_only"] is True

    app, engine = storage_app(tmp_path, max_bytes=16 * MIB)
    with TestClient(app) as owner:
        owner_login(owner)
        event_id, resource_id, _ = product_with_file_resource(owner)  # single-request upload of the small MP4
        base = sessions_path(event_id, resource_id)
        assert TestClient(app).get("/api/admin/storage/health").status_code == 401
        plain = TestClient(app)
        bale_login(plain, 97009)
        assert plain.get("/api/admin/storage/health").status_code == 403
        health = owner.get("/api/admin/storage/health").json()
        assert health["configured"] is True and health["backend"] == "local_disk" and health["state"] == "ok"
        assert health["referenced"] == {"rows": 1, "bytes": len(MP4)} and health["missing"]["count"] == 0
        assert health["orphans"] == {"count": 0, "bytes": 0} and health["incomplete"]["parts"] == 0
        assert health["markers"] == {} and "path" not in json.dumps(health) and "private-store" not in json.dumps(health)
        # an open session shows up as incomplete; an orphan file and a missing file are counted, never touched
        opened = start(owner, base, 2 * MIB, sha256="c" * 64)
        push(owner, base, opened.json()["id"], 0, b"k" * MIB)
        orphan = tmp_path / "private-store" / "2026" / "01" / ("f" * 32)
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_bytes(b"orphan-bytes")
        health = owner.get("/api/admin/storage/health").json()
        assert health["incomplete"] == {"parts": 1, "bytes": MIB, "stale_parts": 0, "open_sessions": 1}
        assert health["orphans"] == {"count": 1, "bytes": 12} and health["state"] == "warning"
        assert health["upload_sessions"]["open"] == {"count": 1, "bytes": MIB}
        with Session(engine) as db:
            key = db.get(EventResourceRecord, resource_id).storage_key
        (tmp_path / "private-store" / key).unlink()
        health = owner.get("/api/admin/storage/health").json()
        assert health["missing"] == {"count": 1, "resource_ids": [resource_id]} and health["state"] == "error"
        assert orphan.exists() and len(part_files(tmp_path)) == 1  # read-only: nothing removed
