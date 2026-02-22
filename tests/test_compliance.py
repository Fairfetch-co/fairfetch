"""Tests for EU AI Act compliance: lineage, headers, copyright opt-out, usage grants."""

from __future__ import annotations

from pathlib import Path

import pytest

from compliance.copyright import CopyrightOptOutLog, OptOutEntry
from compliance.headers import ComplianceHeaders
from compliance.lineage import DataLineageTracker
from core.signatures import Ed25519Signer


class TestDataLineageTracker:
    def test_record_steps(self):
        tracker = DataLineageTracker(source_url="https://example.com")
        tracker.record("fetch", tool="httpx", output_hash="abc123")
        tracker.record("extract", tool="trafilatura", input_hash="abc123", output_hash="def456")

        lineage = tracker.to_dict()
        assert lineage["source_url"] == "https://example.com"
        assert lineage["record_count"] == 2
        assert len(lineage["pipeline"]) == 2
        assert lineage["pipeline"][0]["step"] == "fetch"
        assert lineage["pipeline"][1]["tool"] == "trafilatura"

    def test_hash_content(self):
        h1 = DataLineageTracker.hash_content("hello")
        h2 = DataLineageTracker.hash_content("hello")
        h3 = DataLineageTracker.hash_content("world")

        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 64


class TestComplianceHeaders:
    def test_basic_headers(self):
        headers = ComplianceHeaders()
        d = headers.to_dict()

        assert d["X-Data-Origin-Verified"] == "true"
        assert d["X-AI-License-Type"] == "publisher-terms"
        assert d["X-Fairfetch-Version"] == "0.2"

    def test_headers_with_signature(self, signer: Ed25519Signer):
        sig = signer.sign(b"test content")
        headers = ComplianceHeaders(
            signature=sig,
            content_hash="abc123",
            license_type="commercial",
        )
        d = headers.to_dict()

        assert d["X-AI-License-Type"] == "commercial"
        assert "X-FairFetch-Origin-Signature" in d
        assert "X-Origin-Public-Key" in d
        assert d["X-Origin-Signature-Algorithm"] == "Ed25519"
        assert d["X-Content-Hash"] == "sha256:abc123"

    def test_headers_with_license_id(self):
        headers = ComplianceHeaders(license_id="grant123:sig_prefix")
        d = headers.to_dict()
        assert d["X-FairFetch-License-ID"] == "grant123:sig_prefix"

    def test_opted_out_license(self):
        headers = ComplianceHeaders(license_type="opt-out")
        d = headers.to_dict()
        assert d["X-AI-License-Type"] == "opt-out"


class TestCopyrightOptOut:
    def test_add_and_check(self, tmp_path: Path):
        log = CopyrightOptOutLog(log_path=tmp_path / "optout.jsonl")

        entry = OptOutEntry(
            domain="example.com",
            opt_out_scope="training",
            declared_by="publisher",
        )
        log.add(entry)

        assert log.is_opted_out("example.com") is True
        assert log.is_opted_out("other.com") is False
        assert log.count == 1

    def test_persistence(self, tmp_path: Path):
        path = tmp_path / "optout.jsonl"

        log1 = CopyrightOptOutLog(log_path=path)
        log1.add(OptOutEntry(domain="persist.com", opt_out_scope="all"))

        log2 = CopyrightOptOutLog(log_path=path)
        assert log2.is_opted_out("persist.com") is True
        assert log2.count == 1

    def test_scope_none_not_opted_out(self, tmp_path: Path):
        log = CopyrightOptOutLog(log_path=tmp_path / "optout.jsonl")
        log.add(OptOutEntry(domain="allowed.com", opt_out_scope="none"))

        assert log.is_opted_out("allowed.com") is False

    def test_get_entries_filters_by_domain(self, tmp_path: Path):
        log = CopyrightOptOutLog(log_path=tmp_path / "optout.jsonl")
        log.add(OptOutEntry(domain="a.com", opt_out_scope="training"))
        log.add(OptOutEntry(domain="b.com", opt_out_scope="training"))
        log.add(OptOutEntry(domain="a.com", opt_out_scope="all", url_pattern="/private/*"))

        entries = log.get_entries("a.com")
        assert len(entries) == 2
        assert all(e.domain == "a.com" for e in entries)
