"""Package the complete conversion and smoke-test a relocated ZIP extraction."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT.parent / "digit-dash-python.zip"
    excluded = {"node_modules", "__pycache__", ".pytest_cache", ".venv", "build", "dist"}
    files = sorted(p for p in ROOT.rglob("*") if p.is_file()
                   and not (set(p.relative_to(ROOT).parts) & excluded)
                   and p.suffix not in (".pyc", ".pyo"))
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, Path("digit_dash") / file.relative_to(ROOT))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert "digit_dash/main.py" in archive.namelist()
        assert not any("node_modules" in n for n in archive.namelist())
        with tempfile.TemporaryDirectory(prefix="digit-dash-zip-") as folder:
            archive.extractall(folder)
            extracted = Path(folder) / "digit_dash"
            subprocess.run([sys.executable, str(extracted / "main.py"), "--headless", "--frames", "180"],
                           cwd=folder, check=True)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(f"{digest}  {output.name}\n")
    print(json.dumps({"archive": str(output), "bytes": output.stat().st_size,
                      "files": len(files), "sha256": digest,
                      "zip_integrity": "passed", "relocated_launch": "passed"}, indent=2))


if __name__ == "__main__":
    main()
