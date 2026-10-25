from __future__ import annotations

import io
import zipfile

import pytest

from app.garmin.fit_parser import FitUnavailable, _downsample, extract_fit_bytes


def test_extract_fit_from_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("activity.fit", b"\x0e\x10\x00\x00\x00\x00\x00\x00.FITxx")
    assert extract_fit_bytes(buf.getvalue()).endswith(b".FITxx")


def test_extract_rejects_garbage():
    with pytest.raises(FitUnavailable):
        extract_fit_bytes(b"not a fit file at all")


def test_downsample_keeps_endpoints():
    pts = [{"i": i} for i in range(100)]
    out = _downsample(pts, 10)
    assert out[0]["i"] == 0 and out[-1]["i"] == 99
    assert 10 <= len(out) <= 11
