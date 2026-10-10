"""Audit script for detecting raw HTML, CSS, or markup leaks in Streamlit files."""

import os
import re
import ast
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = Path(r"c:\Users\Admin\Desktop\multiagent")

UI_FILES = [
    WORKSPACE / "app.py",
    WORKSPACE / "travel_agency" / "booking_ui.py",
    WORKSPACE / "travel_agency" / "package_ui.py",
    WORKSPACE / "travel_agency" / "bank_ui.py",
    WORKSPACE / "travel_agency" / "profile_ui.py",
    WORKSPACE / "travel_agency" / "theme.py",
]

def audit_file(filepath: Path):
    print(f"\n========================================================")
    print(f"AUDITING: {filepath.relative_to(WORKSPACE)}")
    print(f"========================================================")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines()

    issues = []

    # 1. Search for st.write, st.text, st.code with HTML
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
    # We want to check:
    #   - If unsafe_allow_html=True is missing when HTML is present
    #   - If the markdown string has indented code blocks with HTML (lines with 4+ spaces after blank lines or start)
    #   - If orphan </div> tags exist
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
            
        # Check for CommonMark indentation triggers (triple quoted string with 4+ leading spaces on HTML lines)
        if '"""' in call_text or "'''" in call_text:
            # Check lines inside this call
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
            # exclude comments or tests
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

    print(f"Found {len(issues)} suspicious patterns:")
    for iss in issues[:30]:
        print(f"  Line {iss['line']} [{iss['type']}]: {iss['snippet']}")
    if len(issues) > 30:
        print(f"  ... and {len(issues) - 30} more.")

if __name__ == "__main__":
    for f in UI_FILES:
        if f.exists():
            audit_file(f)
