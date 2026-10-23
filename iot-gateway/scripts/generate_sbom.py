#!/usr/bin/env python3
"""Generate CycloneDX v1.5 JSON SBOM for iot-gateway."""
import json
import sys
from datetime import datetime
try:
    import tomllib
except ImportError:
    import tomli as tomllib

def generate_sbom():
    try:
        with open("iot-gateway/pyproject.toml", "rb") as f:
            data = tomllib.load(f)
    except Exception:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

    project = data.get("project", {})
    dependencies = project.get("dependencies", [])
    optional_deps = project.get("optional-dependencies", {})

    components = []
    for dep in dependencies:
        components.append({
            "type": "library",
            "name": dep.split(">=")[0].split("==")[0].split("<")[0].strip(),
            "version": dep,
            "purl": f"pkg:pypi/{dep.split('>')[0].split('=')[0].split('<')[0].strip()}"
        })

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:6c2d1b7a-8f9e-4a3b-9c1e-5f6a7b8c9d0e",
        "version": 1,
        "metadata": {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tools": [{
                "vendor": "Smart Factory",
                "name": "iot-gateway-sbom-generator",
                "version": "1.0.0"
            }],
            "component": {
                "type": "application",
                "name": project.get("name", "iot-gateway"),
                "version": project.get("version", "0.1.0"),
                "description": project.get("description", "")
            }
        },
        "components": components
    }

    output_path = "iot-gateway/sbom.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sbom, f, indent=2)
    print(f"SBOM successfully generated at {output_path} with {len(components)} dependencies.")

if __name__ == "__main__":
    generate_sbom()
