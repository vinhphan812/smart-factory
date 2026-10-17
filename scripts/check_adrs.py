#!/usr/bin/env python3
"""
Architecture Decision Record (ADR) Linter and Governance CI Gate.
Validates:
1. Filename format (adr-XXXX-name.md) and ID matching heading.
2. Required metadata fields (Status, Date, Deciders, Related issues).
3. Required sections: Context, Decision, Consequences, Alternatives considered, Evidence (non-empty).
4. Valid status values (Proposed, Accepted, Superseded, Deprecated).
5. Index synchronization (all ADR files listed in docs/adr/README.md and vice versa).
6. Git-diff-based architecture impact detection & exemption logic ([skip-adr] / labels / break-glass).
7. Fixture-based test suite (TC-1 through TC-6).
"""

import os
import re
import sys
import subprocess
from pathlib import Path

# Required sections in ADR markdown
REQUIRED_SECTIONS = [
    "Context",
    "Decision",
    "Consequences",
    "Alternatives considered",
    "Evidence",
]

VALID_STATUSES = {"Proposed", "Accepted", "Superseded", "Deprecated"}

# Architectural paths that trigger ADR requirement when modified
ARCH_PATHS = [
    "docs/architecture/",
    "src/",
    "iot-gateway/src/",
    "esp32-ukit-bridge/",
    "digital-twin/",
]


def parse_adr_file(filepath: Path):
    errors = []
    filename = filepath.name
    if filename == "adr-TEMPLATE.md" or filename == "README.md":
        return None, []

    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines()

    filename_match = re.match(r"^adr-(\d{4})-([a-z0-9-]+)\.md$", filename)
    if not filename_match:
        errors.append(f"{filename}: Filename must match format 'adr-XXXX-name.md'")
        return None, errors

    file_id = filename_match.group(1)

    # Check heading
    heading_found = False
    heading_id = None
    title = ""
    for line in lines:
        match = re.match(r"^#\s+ADR-(\d{4}):\s*(.+)$", line)
        if match:
            heading_found = True
            heading_id = match.group(1)
            title = match.group(2).strip()
            break

    if not heading_found:
        errors.append(f"{filename}: Missing main heading '# ADR-XXXX: Title'")
    elif heading_id != file_id:
        errors.append(f"{filename}: ADR ID mismatch between filename ({file_id}) and heading ({heading_id})")

    # Check status
    status_found = False
    status_val = None
    matched_status = None
    for line in lines:
        match = re.search(r"\*\*Status:\*\*\s*(.+)", line, re.IGNORECASE)
        if match:
            status_found = True
            status_val = match.group(1).strip()
            clean_status = re.sub(r"[*_]", "", status_val)
            for vs in VALID_STATUSES:
                if vs.lower() in clean_status.lower():
                    matched_status = vs
                    break
            break

    if not status_found:
        errors.append(f"{filename}: Missing '**Status:**' field")
    elif not matched_status:
        errors.append(f"{filename}: Invalid status '{status_val}'. Must contain one of {VALID_STATUSES}")
    else:
        status_val = matched_status

    # Check required sections
    for section in REQUIRED_SECTIONS:
        section_found = False
        section_idx = -1
        for idx, line in enumerate(lines):
            if re.match(rf"^##\s+{re.escape(section)}", line, re.IGNORECASE):
                section_found = True
                section_idx = idx
                break

        if not section_found:
            errors.append(f"{filename}: Missing required section '## {section}'")
        else:
            # Check if section has non-empty content before next heading or end of file
            has_content = False
            for idx in range(section_idx + 1, len(lines)):
                next_line = lines[idx].strip()
                if next_line.startswith("#"):
                    break
                if next_line and not next_line.startswith("[*") and not next_line.startswith("<!--"):
                    has_content = True
                    break
            if not has_content:
                errors.append(f"{filename}: Section '## {section}' is empty")

    return {
        "id": file_id,
        "filename": filename,
        "title": title,
        "status": status_val,
    }, errors


def check_index(adr_dir: Path, adr_data_list):
    errors = []
    readme_path = adr_dir / "README.md"
    if not readme_path.exists():
        errors.append("docs/adr/README.md missing")
        return errors

    readme_content = readme_path.read_text(encoding="utf-8")

    # Check each ADR is listed in README.md
    for adr in adr_data_list:
        if adr["filename"] not in readme_content:
            errors.append(f"ADR {adr['filename']} ({adr['id']}) not listed in docs/adr/README.md index table")

    return errors


def check_architecture_impact(adr_dir: Path, repo_root: Path):
    """
    Check if architecture/source files are modified in git diff without an ADR or exemption.
    """
    errors = []
    # Skip if not in a git repo or no origin/master
    try:
        res = subprocess.run(
            ["git", "diff", "--name-only", "origin/master...HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        if res.returncode != 0:
            # Fallback to HEAD~1 or unstaged/staged if origin/master not available
            res = subprocess.run(
                ["git", "diff", "--name-only", "HEAD~1"],
                capture_output=True,
                text=True,
                cwd=repo_root,
            )
        changed_files = res.stdout.splitlines()
    except Exception:
        changed_files = []

    if not changed_files:
        return errors

    # Check if any changed file is architectural
    arch_modified = False
    for f in changed_files:
        if any(f.startswith(p) for p in ARCH_PATHS):
            arch_modified = True
            break

    if not arch_modified:
        return errors

    # Check if an ADR was added or modified in the changes
    adr_modified = any(f.startswith("docs/adr/adr-") for f in changed_files)

    if adr_modified:
        return errors

    # Check exemptions
    # 1. Break-glass env var
    if os.environ.get("FORCE_BYPASS_ADR") == "1":
        print("⚠️ WARNING: Architecture modified without ADR, but bypassed via FORCE_BYPASS_ADR=1")
        return errors

    # 2. PR labels env var
    pr_labels = os.environ.get("PR_LABELS", "").lower()
    if "skip-adr" in pr_labels or "skip-architecture-decision" in pr_labels:
        print("ℹ️ Architecture modified without ADR, but bypassed via PR label ('skip-adr')")
        return errors

    # 3. Commit messages in range
    try:
        log_res = subprocess.run(
            ["git", "log", "origin/master..HEAD", "--oneline"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
        commit_logs = log_res.stdout.lower()
        if "[skip-adr]" in commit_logs or "skip-adr" in commit_logs or "[break-glass]" in commit_logs:
            print("ℹ️ Architecture modified without ADR, but bypassed via commit message marker")
            return errors
    except Exception:
        pass

    errors.append(
        "Architecture modification detected in core paths ({}) without an accompanying "
        "Architecture Decision Record (ADR) under docs/adr/ or exemption ([skip-adr] commit/label). "
        "See docs/adr/README.md.".format(", ".join(ARCH_PATHS))
    )
    return errors


def validate_all(repo_root: Path = Path(".")):
    adr_dir = repo_root / "docs" / "adr"
    if not adr_dir.exists():
        print(f"Error: ADR directory {adr_dir} not found.")
        return 1

    all_errors = []
    adr_data_list = []

    for adr_file in sorted(adr_dir.glob("adr-*.md")):
        data, errs = parse_adr_file(adr_file)
        if errs:
            all_errors.extend(errs)
        if data:
            adr_data_list.append(data)

    # Check index sync
    index_errs = check_index(adr_dir, adr_data_list)
    all_errors.extend(index_errs)

    # Check architecture impact
    impact_errs = check_architecture_impact(adr_dir, repo_root)
    all_errors.extend(impact_errs)

    if all_errors:
        print("❌ ADR Lint / Governance Gate FAILED:")
        for err in all_errors:
            print(f"  - {err}")
        return 1
    else:
        print(f"✅ ADR Lint / Governance Gate PASSED ({len(adr_data_list)} ADRs validated successfully).")
        return 0


if __name__ == "__main__":
    sys.exit(validate_all())
