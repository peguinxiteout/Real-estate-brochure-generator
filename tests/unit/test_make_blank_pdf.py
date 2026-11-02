import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_output_is_sample_blank_8pp_pdf_and_git_ignores_it():
    tool = load_tool("make_blank_pdf")
    assert tool.DEFAULT_OUT == ROOT / "sample" / "blank-8pp.pdf"
    ignored = subprocess.run(["git", "check-ignore", "-q", "sample/blank-8pp.pdf"], cwd=ROOT)
    assert ignored.returncode == 0, "sample/blank-8pp.pdf is not git-ignored"
