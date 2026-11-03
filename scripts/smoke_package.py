"""Exercise the installed wheel, without the checkout on Python's import path."""

import subprocess
import sys
from importlib.metadata import distribution
from importlib.resources import files
from pathlib import Path

import scoutfit
from scoutfit.dossier import dossier_html


def main():
    checkout = Path(__file__).resolve().parents[1]
    module = Path(scoutfit.__file__).resolve()
    if module.is_relative_to(checkout) or sys.prefix == sys.base_prefix:
        raise RuntimeError("La comprobación debe usar el wheel en un entorno independiente.")
    template = files("scoutfit").joinpath("templates/individual.html").read_text(encoding="utf-8")
    if "$player_name" not in template:
        raise RuntimeError("La plantilla instalada no es válida.")
    report = {
        "player_name": "Jugador de prueba <sin datos reales>",
        "project_name": "Comprobación de distribución",
        "team_at_save": "Club de prueba",
        "status": "Pendiente",
        "generated_at": "2026-01-01T12:00:00Z",
        "assessment": {},
        "statistics": None,
        "observations": [],
        "general_note": "",
        "player_key": "smoke:1",
        "saved_snapshot": "smoke",
    }
    html = dossier_html(report)
    if "&lt;sin datos reales&gt;" not in html or "$player_name" in html:
        raise RuntimeError("El informe instalado no se ha renderizado correctamente.")
    cli = Path(sys.executable).with_name("scoutfit.exe" if sys.platform == "win32" else "scoutfit")
    result = subprocess.run([str(cli), "--help"], capture_output=True, check=True)
    if b"recommend" not in result.stdout or b"update" not in result.stdout:
        raise RuntimeError("La CLI instalada no expone los comandos esperados.")
    print(f"Wheel {distribution('scoutfit').version}: importación, CLI y HTML correctos.")
    print(f"Paquete instalado: {module}")


if __name__ == "__main__":
    main()
