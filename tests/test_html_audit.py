"""Regression test suite to ensure zero raw HTML, CSS, or markup leaks across SK Holidays UI."""

import re
from pathlib import Path
import pytest
from travel_agency.data import load_packages
from travel_agency.package_service import PackageService
from travel_agency.booking_service import get_booking_service
from travel_agency.bank_service import get_demo_bank_service

WORKSPACE = Path(__file__).resolve().parent.parent

UI_FILES = [
    WORKSPACE / "app.py",
    WORKSPACE / "travel_agency" / "booking_ui.py",
    WORKSPACE / "travel_agency" / "package_ui.py",
    WORKSPACE / "travel_agency" / "bank_ui.py",
    WORKSPACE / "travel_agency" / "profile_ui.py",
    WORKSPACE / "travel_agency" / "theme.py",
]


def audit_file_for_issues(filepath: Path):
    """Scan a Python file for unintended raw HTML / markdown rendering flaws."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines()

    issues = []

    # 1. Search for st.write, st.text, st.code with HTML markup
    write_text_pattern = re.compile(r'st\.(write|text|code)\((.*?)\)', re.DOTALL)
    for m in write_text_pattern.finditer(content):
        arg = m.group(2)
        if any(tag in arg for tag in ["<div", "<span", "<p", "<table", "<h1", "<h2", "<h3", "style="]):
            line_no = content[:m.start()].count("\n") + 1
            issues.append({
                "line": line_no,
                "type": f"st.{m.group(1)} with HTML",
                "snippet": m.group(0)[:120]
            })

    # 2. Search for st.markdown calls containing HTML
    markdown_pattern = re.compile(r'st\.markdown\((.*?)\)', re.DOTALL)
    for m in markdown_pattern.finditer(content):
        call_text = m.group(1)
        start_line = content[:m.start()].count("\n") + 1

        has_html = any(tag in call_text for tag in ["<div", "<span", "<p", "<table", "<tr", "<td", "<h1", "<h2", "<h3", "<img", "<hr", "<strong", "<em", "<b", "<i", "<a "])
        has_unsafe = "unsafe_allow_html=True" in call_text

        if has_html and not has_unsafe:
            issues.append({
                "line": start_line,
                "type": "st.markdown with HTML but missing unsafe_allow_html=True",
                "snippet": call_text[:120].strip()
            })

        # Check for CommonMark 4+ space indentation inside markdown string that causes code block leak
        if '"""' in call_text or "'''" in call_text:
            call_lines = call_text.splitlines()
            prev_blank = True
            for idx, cl in enumerate(call_lines):
                stripped = cl.strip()
                if not stripped:
                    prev_blank = True
                    continue
                indent = len(cl) - len(cl.lstrip())
                if indent >= 4 and any(tag in stripped for tag in ["<div", "<span", "<table", "<tr", "<td", "<p", "<img", "<strong"]):
                    if prev_blank or stripped.startswith("<"):
                        issues.append({
                            "line": start_line + idx,
                            "type": "CommonMark 4+ space indented HTML in markdown string (causes code block leak)",
                            "snippet": cl[:120]
                        })
                prev_blank = False

    # 3. Search for escaped HTML entities in visible strings
    for idx, line in enumerate(lines, 1):
        if any(ent in line for ent in ["&lt;div", "&lt;span", "&lt;p", "&gt;"]):
            if not line.strip().startswith("#"):
                issues.append({
                    "line": idx,
                    "type": "Escaped HTML entity in UI source",
                    "snippet": line.strip()[:120]
                })

    # 4. Search for standalone raw HTML tags passed as plain string
    orphan_close_tags = ["</div>", "</span>", "</table>"]
    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped in [f'st.markdown("{t}")' for t in orphan_close_tags] or stripped in [f"st.markdown('{t}')" for t in orphan_close_tags]:
            issues.append({
                "line": idx,
                "type": "Orphan closing HTML tag without unsafe_allow_html",
                "snippet": stripped
            })

    return issues


def test_ui_files_audit_zero_suspicious_patterns():
    """All UI files in SK Holidays must have 0 raw HTML rendering defects."""
    total_issues = {}
    for f in UI_FILES:
        assert f.exists(), f"File {f} does not exist"
        issues = audit_file_for_issues(f)
        if issues:
            total_issues[str(f.name)] = issues

    assert total_issues == {}, f"Found raw HTML rendering defects: {total_issues}"


def test_package_data_no_html_tags():
    """Verify package data fields do not accidentally contain raw HTML strings."""
    svc = PackageService()
    packages = svc.get_all_packages()
    assert len(packages) >= 20

    for pkg in packages:
        # Check text fields
        for field_val in [pkg.name, pkg.destination_name, pkg.tagline, pkg.hotel_name, pkg.transport_mode, pkg.meal_plan]:
            assert "<div" not in field_val, f"Found <div in {pkg.id} field: {field_val}"
            assert "<span" not in field_val, f"Found <span in {pkg.id} field: {field_val}"
            assert "&lt;" not in field_val, f"Found &lt; in {pkg.id} field: {field_val}"

        for inc in pkg.inclusions:
            assert "<" not in inc and ">" not in inc, f"Found markup in inclusion: {inc}"
        for exc in pkg.exclusions:
            assert "<" not in exc and ">" not in exc, f"Found markup in exclusion: {exc}"


def test_bank_data_no_html_tags(tmp_path):
    """Verify bank account and transaction data are clean plain text without markup."""
    db_file = tmp_path / "test_bank.db"
    bank_svc = get_demo_bank_service(db_path=db_file)
    acc = bank_svc.get_account()

    assert "<div" not in acc.account_holder
    assert "<span" not in acc.bank_name
    assert "<div" not in acc.account_number

    txs = bank_svc.get_transactions(limit=5)
    for tx in txs:
        assert "<div" not in tx.description
        assert "<span" not in tx.description
        assert "&lt;" not in tx.description


def test_no_orphan_html_tags_in_travel_agency():
    """Verify travel_agency Python modules have no orphan closing tags."""
    for py_file in (WORKSPACE / "travel_agency").glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert 'st.markdown("</div>")' not in content
        assert "st.markdown('</div>')" not in content
