"""Phase 9.1 §3 – external video sources (YouTube / Aparat) for recorded sessions.

* Only a validated video id survives: URL or bare id in, canonical watch URL stored,
  official embed URL derived server-side.  HTML, ``javascript:``, foreign hosts, IPs and
  malformed ids are refused with stable codes.
* Playback information (id / embed URL) is part of the resource view **only after** the
  server-side access check; locked rows carry neither the id nor a URL.
* External sources are view-only (no download), count as a live resource for publishing,
  and never touch the private file path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_PARENT = Path(__file__).resolve().parents[2]
if str(BACKEND_PARENT) not in sys.path:
    sys.path.insert(0, str(BACKEND_PARENT))

from backend import video_sources  # noqa: E402
from test_event_registration_gate import gate_app  # noqa: E402
from test_recordings_api import (  # noqa: E402
    account_write_headers,
    bale_login,
    held_event,
    owner_write_headers,
    put_recording,
    recording_view,
    set_status,
)
from test_workflows_api import owner_login  # noqa: E402

YT = "dQw4w9WgXcQ"
AP = "abc12Xy"


@pytest.mark.parametrize("raw", [
    YT,
    f"https://www.youtube.com/watch?v={YT}",
    f"https://youtube.com/watch?feature=share&v={YT}&t=42",
    f"https://m.youtube.com/watch?v={YT}",
    f"https://youtu.be/{YT}?si=tracking",
    f"https://www.youtube.com/embed/{YT}",
    f"https://www.youtube-nocookie.com/embed/{YT}?rel=0",
    f"https://www.youtube.com/shorts/{YT}",
    f"https://www.youtube.com/live/{YT}",
    f"http://www.youtube.com/watch?v={YT}",
    f"  https://www.youtube.com/watch?v={YT}  ",
])
def test_youtube_inputs_collapse_to_one_validated_id(raw):
    source = video_sources.parse("youtube", raw)
    assert source.video_id == YT
    assert source.watch_url == f"https://www.youtube.com/watch?v={YT}"
    assert source.embed_url.startswith(f"https://www.youtube-nocookie.com/embed/{YT}?")
    assert source.frame_origin == "https://www.youtube-nocookie.com"
    assert video_sources.from_stored("youtube", source.watch_url) == source


@pytest.mark.parametrize("raw", [
    AP,
    f"https://www.aparat.com/v/{AP}",
    f"https://aparat.com/v/{AP}/",
    f"https://www.aparat.com/v/{AP}?playlist=1",
    f"https://www.aparat.com/video/video/embed/videohash/{AP}/vt/frame",
    f"https://www.aparat.com/embed/{AP}",
])
def test_aparat_inputs_collapse_to_one_validated_id(raw):
    source = video_sources.parse("aparat", raw)
    assert source.video_id == AP
    assert source.watch_url == f"https://www.aparat.com/v/{AP}"
    assert source.embed_url == f"https://www.aparat.com/video/video/embed/videohash/{AP}/vt/frame"
    assert video_sources.from_stored("aparat", source.watch_url) == source


@pytest.mark.parametrize("provider, raw, code", [
    ("youtube", "", "video_source_required"),
    ("youtube", None, "video_source_required"),
    ("youtube", 123, "invalid_video_source"),
    ("youtube", "x" * 2049, "invalid_video_source"),
    ("youtube", f'<iframe src="https://www.youtube.com/embed/{YT}"></iframe>', "html_not_allowed"),
    ("youtube", "javascript:alert(1)", "unsupported_video_host"),
    ("youtube", "data:text/html,<script>1</script>", "html_not_allowed"),
    ("youtube", "data:text/html;base64,PHNjcmlwdD4=", "unsupported_video_host"),
    ("youtube", "ftp://www.youtube.com/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://evil.example/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://www.youtube.com.evil.example/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://user:pw@www.youtube.com/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://www.youtube.com:8443/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://127.0.0.1/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://[::1]/watch?v=" + YT, "unsupported_video_host"),
    ("youtube", "https://www.youtube.com/watch?v=short", "invalid_video_id"),
    ("youtube", "https://www.youtube.com/channel/UC123", "invalid_video_id"),
    ("youtube", "https://www.youtube.com/watch?v=\n" + YT, "invalid_video_source"),
    ("youtube", "https://www.youtube.com/watch?v=" + YT + " x", "invalid_video_source"),
    ("youtube", "not an id", "invalid_video_source"),
    ("youtube", "tooshort", "invalid_video_id"),
    ("aparat", "https://www.aparat.com/profile/x", "invalid_video_id"),
    ("aparat", "https://www.aparat.com/v/../../etc", "invalid_video_id"),
    ("aparat", "https://aparat.example/v/" + AP, "unsupported_video_host"),
    ("aparat", "https://www.youtube.com/watch?v=" + YT, "unsupported_video_host"),
    ("aparat", "ab", "invalid_video_id"),
    ("vimeo", "https://vimeo.com/123456", "unsupported_video_provider"),
    ("link", "https://example.org", "unsupported_video_provider"),
])
def test_dangerous_or_foreign_inputs_are_refused(provider, raw, code):
    with pytest.raises(video_sources.VideoSourceError) as error:
        video_sources.parse(provider, raw)
    assert error.value.code == code


def test_stored_values_that_are_not_canonical_never_produce_an_embed():
    # A tampered row (anything but our own canonical watch URL) yields no player.
    assert video_sources.from_stored("youtube", f"https://youtu.be/{YT}") is None
    assert video_sources.from_stored("youtube", "javascript:alert(1)") is None
    assert video_sources.from_stored("aparat", "") is None
    assert video_sources.from_stored("link", "https://www.youtube.com/watch?v=" + YT) is None
    assert video_sources.from_stored("file", "") is None


def test_external_sessions_reveal_playback_info_only_after_the_server_access_check():
    app, engine = gate_app()
    try:
        with TestClient(app) as owner:
            owner_login(owner)
            held, _version = held_event(owner, 0)
            assert put_recording(owner, held, title="ضبط با منبع بیرونی", price=0, payment_card=None).status_code == 200
            base = f"/api/admin/events/{held}/resources"
            session = owner.post(f"/api/admin/events/{held}/recording/sessions", json={"title": "جلسهٔ یکم", "duration_minutes": 40},
                                 headers=owner_write_headers(owner))
            assert session.status_code == 201
            session_id = session.json()["id"]

            # Pasted iframe / foreign host / javascript: are refused with field-level codes.
            for raw, code in (
                (f'<iframe src="https://www.youtube.com/embed/{YT}"></iframe>', "html_not_allowed"),
                ("javascript:alert(1)", "unsupported_video_host"),
                ("https://evil.example/watch?v=" + YT, "unsupported_video_host"),
                ("https://www.youtube.com/watch?v=nope", "invalid_video_id"),
            ):
                bad = owner.post(base, json={"kind": "youtube", "title": "بد", "link_url": raw, "access": "purchased", "session_id": session_id},
                                 headers=owner_write_headers(owner))
                assert bad.status_code == 422, bad.text
                assert bad.json()["detail"] == {"code": code, "field": "link_url"}
            # Download delivery is impossible for an external player.
            no_download = owner.post(base, json={"kind": "aparat", "title": "دانلود؟", "link_url": AP, "access": "purchased", "session_id": session_id,
                                                 "delivery": "download"}, headers=owner_write_headers(owner))
            assert no_download.status_code == 422 and no_download.json()["detail"]["field"] == "delivery"

            # Valid YouTube URL with tracking noise → canonical watch URL + official embed in the admin view.
            yt = owner.post(base, json={"kind": "youtube", "title": "ویدیوی یوتیوب", "link_url": f"https://youtu.be/{YT}?si=abc&t=10",
                                        "access": "purchased", "session_id": session_id}, headers=owner_write_headers(owner))
            assert yt.status_code == 201, yt.text
            yt_id = yt.json()["id"]
            assert yt.json()["kind"] == "youtube" and yt.json()["delivery"] == "view"
            assert yt.json()["link_url"] == f"https://www.youtube.com/watch?v={YT}"
            assert yt.json()["video"]["embed_url"].startswith(f"https://www.youtube-nocookie.com/embed/{YT}?")
            ap = owner.post(base, json={"kind": "aparat", "title": "ویدیوی آپارات", "link_url": f"https://www.aparat.com/v/{AP}",
                                        "access": "purchased", "session_id": session_id}, headers=owner_write_headers(owner))
            assert ap.status_code == 201, ap.text
            ap_id = ap.json()["id"]
            assert ap.json()["video"] == {
                "provider": "aparat", "video_id": AP, "watch_url": f"https://www.aparat.com/v/{AP}",
                "embed_url": f"https://www.aparat.com/video/video/embed/videohash/{AP}/vt/frame",
                "frame_origin": "https://www.aparat.com",
            }
            # No bytes can be attached to an external source and the file endpoint stays 404 for it.
            upload = owner.put(f"{base}/{yt_id}/file", content=b"%PDF-1.4", headers={**owner_write_headers(owner), "X-File-Name": "x.pdf"})
            assert upload.status_code == 409 and upload.json()["detail"]["code"] == "resource_not_file"
            assert owner.get(f"/api/public/events/{held}/resources/{yt_id}/download").status_code == 404

            # Publishing: external rows count as live resources (no upload needed).
            for rid in (yt_id, ap_id):
                assert owner.put(f"{base}/{rid}", json={"status": "published"}, headers=owner_write_headers(owner)).status_code == 200
            assert owner.put(f"/api/admin/events/{held}/recording/sessions/{session_id}", json={"status": "published"},
                             headers=owner_write_headers(owner)).status_code == 200
            assert owner.get(f"/api/admin/events/{held}/recording").json()["recording"]["publish_blockers"] == []
            assert set_status(owner, held, "ready").status_code == 200
            assert set_status(owner, held, "published").status_code == 200

            # Guest: rows are listed, marked external, but carry neither id nor URL.
            guest = TestClient(app)
            locked = {row["id"]: row for row in recording_view(guest, held)["sessions"][0]["resources"]}
            for rid in (yt_id, ap_id):
                row = locked[rid]
                assert row["allowed"] is False and row["external"] is True and row["playable"] is True
                assert "video" not in row and "link_url" not in row and row["downloadable"] is False
                assert YT not in str(row) and AP not in str(row)

            # Member with access (free claim): playback info appears, download stays impossible.
            member = TestClient(app)
            bale_login(member, 95301)
            recording_id = owner.get(f"/api/admin/events/{held}/recording").json()["recording"]["id"]
            assert member.post(f"/api/account/recordings/{recording_id}/claim", headers=account_write_headers(member)).status_code == 201
            opened = {row["id"]: row for row in recording_view(member, held)["sessions"][0]["resources"]}
            assert opened[yt_id]["allowed"] is True and opened[yt_id]["video"]["video_id"] == YT
            assert opened[yt_id]["video"]["frame_origin"] == "https://www.youtube-nocookie.com"
            assert opened[ap_id]["video"]["embed_url"].endswith(f"/videohash/{AP}/vt/frame")
            assert opened[yt_id]["downloadable"] is False and opened[yt_id]["delivery"] == "view"
            assert member.get(f"/api/public/events/{held}/resources/{yt_id}/download").status_code == 404

            # Event-level (non-session) external row: the interaction snapshot applies the same rule.
            general = owner.post(base, json={"kind": "youtube", "title": "گزارش تصویری", "link_url": YT, "access": "registered", "status": "published"},
                                 headers=owner_write_headers(owner))
            assert general.status_code == 201, general.text
            general_id = general.json()["id"]
            snapshot = {row["id"]: row for row in guest.get(f"/api/public/events/{held}/interaction").json()["resources"]}
            assert snapshot[general_id]["external"] is True and snapshot[general_id]["allowed"] is False
            assert "video" not in snapshot[general_id] and "link_url" not in snapshot[general_id] and YT not in str(snapshot[general_id])
            staff_rows = {row["id"]: row for row in owner.get(f"/api/public/events/{held}/interaction").json()["resources"]}
            assert staff_rows[general_id]["video"]["video_id"] == YT  # staff may preview
            # Kind switch back to a plain link requires a fresh URL; the stored canonical URL is not reused silently.
            switched = owner.put(f"{base}/{yt_id}", json={"kind": "link"}, headers=owner_write_headers(owner))
            assert switched.status_code == 422 and switched.json()["detail"]["field"] == "link_url"
    finally:
        engine.dispose()
