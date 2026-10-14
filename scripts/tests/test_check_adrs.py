import pytest
from pathlib import Path
import os
import sys

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import check_adrs


def create_valid_adr_content(id_str="0010", title="Test ADR"):
    return f"""# ADR-{id_str}: {title}

**Status:** Proposed
**Date:** 2026-10-14
**Deciders:** Architecture Team
**Related issues:** #80

## Context
This is the context for the test ADR.

## Decision
We will test the ADR linter successfully.

## Consequences
Tests will pass and governance will be enforced.

## Alternatives considered
- Do not test: rejected because testing is required.

## Evidence
- Test fixture TC-1.
"""


def test_tc1_valid_adr(tmp_path):
    """TC-1: Valid ADR file passes all validation checks."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    adr_file = adr_dir / "adr-0010-valid-test.md"
    adr_file.write_text(create_valid_adr_content())

    # Create README index
    readme = adr_dir / "README.md"
    readme.write_text("| ADR | Title | Status |\n|---|---|---|\n| [ADR-0010](adr-0010-valid-test.md) | Test ADR | Proposed |\n")

    data, errors = check_adrs.parse_adr_file(adr_file)
    assert not errors
    assert data["id"] == "0010"
    assert data["status"] == "Proposed"

    index_errors = check_adrs.check_index(adr_dir, [data])
    assert not index_errors


def test_tc2_invalid_filename_or_id_mismatch(tmp_path):
    """TC-2: Invalid filename format or ADR ID mismatch fails validation."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    # Bad filename
    bad_file1 = adr_dir / "invalid-name.md"
    bad_file1.write_text(create_valid_adr_content("0010"))
    _, errs1 = check_adrs.parse_adr_file(bad_file1)
    assert len(errs1) > 0

    # ID mismatch between filename and heading
    bad_file2 = adr_dir / "adr-0011-mismatch.md"
    bad_file2.write_text(create_valid_adr_content("0010", "Mismatch ADR"))
    _, errs2 = check_adrs.parse_adr_file(bad_file2)
    assert any("mismatch" in e.lower() for e in errs2)


def test_tc3_missing_required_section(tmp_path):
    """TC-3: Missing required sections (e.g. Alternatives or Consequences) fails validation."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    content = """# ADR-0012: Incomplete ADR

**Status:** Proposed
**Date:** 2026-10-14

## Context
Context here.

## Decision
Decision here.
"""  # Missing Consequences, Alternatives considered, Evidence

    adr_file = adr_dir / "adr-0012-incomplete.md"
    adr_file.write_text(content)

    _, errs = check_adrs.parse_adr_file(adr_file)
    assert len(errs) >= 3  # Missing Consequences, Alternatives considered, Evidence


def test_tc4_invalid_status(tmp_path):
    """TC-4: Invalid status value fails validation."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    content = create_valid_adr_content("0013", "Bad Status ADR").replace(
        "**Status:** Proposed", "**Status:** InvalidStatus"
    )

    adr_file = adr_dir / "adr-0013-bad-status.md"
    adr_file.write_text(content)

    _, errs = check_adrs.parse_adr_file(adr_file)
    assert any("status" in e.lower() for e in errs)


def test_tc5_architecture_change_without_adr(monkeypatch, tmp_path):
    """TC-5: Architecture modification without ADR or exemption fails governance check."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    # Mock subprocess.run to simulate git diff returning modified files in src/
    class MockResult:
        returncode = 0
        stdout = "src/main.py\n"

    monkeypatch.setattr(check_adrs.subprocess, "run", lambda *args, **kwargs: MockResult())
    monkeypatch.delenv("FORCE_BYPASS_ADR", raising=False)
    monkeypatch.delenv("PR_LABELS", raising=False)

    errors = check_adrs.check_architecture_impact(adr_dir, tmp_path)
    assert len(errors) > 0
    assert any("architecture modification" in e.lower() for e in errors)


def test_tc6_architecture_change_with_exemption(monkeypatch, tmp_path):
    """TC-6: Architecture modification with exemption (PR label or break-glass) passes."""
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)

    class MockResult:
        returncode = 0
        stdout = "src/main.py\n"

    monkeypatch.setattr(check_adrs.subprocess, "run", lambda *args, **kwargs: MockResult())

    # Exemption via label
    monkeypatch.setenv("PR_LABELS", "skip-adr,bug")
    errors = check_adrs.check_architecture_impact(adr_dir, tmp_path)
    assert not errors

    # Exemption via break-glass
    monkeypatch.delenv("PR_LABELS", raising=False)
    monkeypatch.setenv("FORCE_BYPASS_ADR", "1")
    errors = check_adrs.check_architecture_impact(adr_dir, tmp_path)
    assert not errors
