"""Выполнить Jupyter Notebook текущим Python и сохранить видимые результаты."""

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import nbformat
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpecManager
from nbclient import NotebookClient


def run(output: str | Path = ROOT / "notebooks/demo_ru.ipynb") -> int:
    notebook = nbformat.read(ROOT / "notebooks/demo_ru.ipynb", as_version=4)
    with tempfile.TemporaryDirectory() as directory:
        kernel = Path(directory) / "ozon-validation"
        kernel.mkdir()
        (kernel / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "ipykernel_launcher",
                        "-f",
                        "{connection_file}",
                    ],
                    "display_name": "Python (Ozon validation)",
                    "language": "python",
                }
            )
        )
        manager = KernelManager(
            kernel_name="ozon-validation",
            kernel_spec_manager=KernelSpecManager(kernel_dirs=[directory]),
        )
        client = NotebookClient(
            notebook,
            km=manager,
            timeout=300,
            resources={"metadata": {"path": str(ROOT)}},
        )
        client.execute()
    nbformat.write(notebook, output)
    return sum(cell.cell_type == "code" for cell in notebook.cells)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default=str(ROOT / "notebooks/demo_ru.ipynb"))
    a = p.parse_args()
    print(f"Выполнено ячеек: {run(a.output)}")
