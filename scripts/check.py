"""Run the same offline checks locally and in CI; optionally verify distribution."""

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, cwd=ROOT, env=None):
    print("\n> " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


def check_archive(path):
    """Allow source assets, never local data, credentials or generated reports."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        if "scoutfit/templates/individual.html" not in names:
            raise RuntimeError("El wheel no contiene la plantilla del informe individual.")
    else:
        with tarfile.open(path) as archive:
            names = ["/".join(Path(n).parts[1:]) for n in archive.getnames()]
        required = {
            "app.py",
            "pyproject.toml",
            "uv.lock",
            "README.md",
            ".streamlit/config.toml",
            "scripts/check.py",
            "scripts/smoke_package.py",
            "src/scoutfit/templates/individual.html",
        }
        missing = required.difference(names)
        if missing:
            raise RuntimeError(
                f"Faltan archivos para ejecutar el proyecto fuente: {sorted(missing)}"
            )
    for name in names:
        parts = Path(name).parts
        if (
            any(p in {"data", "reports", ".venv", ".git", "__pycache__"} for p in parts)
            or any(p == ".env" or p.startswith(".env.") for p in parts)
            or "secrets.toml" in parts
        ):
            raise RuntimeError(f"Archivo local no publicable dentro del paquete: {name}")
    print(f"Contenido revisado: {path.name} ({len(names)} entradas)", flush=True)


def check_package(uv):
    # The temporary environment cannot resolve the editable src/ installation.
    with tempfile.TemporaryDirectory(prefix="scoutfit-package-") as temporary:
        directory = Path(temporary)
        artifacts = directory / "dist"
        run(uv, "build", "--no-sources", "--out-dir", artifacts)
        distributions = list(artifacts.glob("*.whl")) + list(artifacts.glob("*.tar.gz"))
        if len(distributions) != 2:
            raise RuntimeError("Se esperaba un wheel y un sdist.")
        for path in distributions:
            check_archive(path)
        requirements = directory / "requirements.txt"
        run(
            uv,
            "export",
            "--locked",
            "--no-dev",
            "--no-emit-project",
            "--format",
            "requirements-txt",
            "--output-file",
            requirements,
            "--quiet",
        )
        environment = directory / "venv"
        run(uv, "venv", "--python", sys.executable, environment)
        binary = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        # Copy dependencies so cache file permissions/locks cannot leak into this venv.
        run(uv, "pip", "sync", "--link-mode", "copy", "--python", binary, requirements)
        wheel = next(artifacts.glob("*.whl"))
        run(uv, "pip", "install", "--link-mode", "copy", "--python", binary, "--no-deps", wheel)
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        env.pop("VIRTUAL_ENV", None)
        run(binary, "-I", ROOT / "scripts/smoke_package.py", cwd=directory, env=env)


def main():
    parser = argparse.ArgumentParser(description="Verificación reproducible de ScoutFit")
    parser.add_argument("--package", action="store_true", help="Instalar y probar el wheel aislado")
    args = parser.parse_args()
    uv = shutil.which("uv")
    if uv is None:
        parser.error("Instala uv y añádelo al PATH.")
    run(uv, "lock", "--check", "--offline")
    run(sys.executable, "-m", "ruff", "check", ".")
    run(sys.executable, "-m", "ruff", "format", "--check", ".")
    # Each run owns its temporary fixtures/cache, including on shared Windows hosts.
    with tempfile.TemporaryDirectory(prefix="scoutfit-tests-") as temporary:
        directory = Path(temporary)
        run(
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--basetemp",
            directory / "fixtures",
            "-o",
            f"cache_dir={directory / 'cache'}",
        )
    if args.package:
        check_package(uv)
    print("\nVerificación completada.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
