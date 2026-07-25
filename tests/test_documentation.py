import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")


def test_local_markdown_links_resolve():
    markdown_files = [*ROOT.glob("*.md"), *ROOT.joinpath("docs").glob("*.md")]
    failures = []
    for document in markdown_files:
        for target in LINK.findall(document.read_text(encoding="utf-8")):
            target = target.strip().strip("<>").split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            if not (document.parent / target).resolve().exists():
                failures.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not failures, "Broken local Markdown links:\n" + "\n".join(failures)
