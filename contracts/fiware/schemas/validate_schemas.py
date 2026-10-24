#!/usr/bin/env python3
"""Validate all JSON schemas in this directory."""
import json
import sys
import os

def main():
    schemas = ['base.json', 'geojson.json', 'device.json', 'module.json', 
               'job.json', 'material.json', 'operator.json', 'alert.json', 'incident.json',
               'robot.json']
    errors = []

    for schema_file in schemas:
        try:
            with open(schema_file) as f:
                json.load(f)
            print(f'OK: {schema_file}')
        except json.JSONDecodeError as e:
            errors.append(f'{schema_file}: {e}')
            print(f'FAIL: {schema_file}: {e}')

    if errors:
        sys.exit(1)
    print('\nAll schemas are valid JSON!')

def validate_entities():
    """Validate the canonical example entities against their schemas.

    Returns the number of validation failures.
    """
    try:
        import jsonschema
    except ImportError:
        print('SKIP: jsonschema is not installed')
        return 0

    here = os.path.dirname(os.path.abspath(__file__))
    cases = [
        ('robot.json', {
            "id": "urn:ngsi-ld:Robot:yanshee-01",
            "type": "Robot",
            "name": {"type": "Text", "value": "UBTECH Yanshee"},
            "robotId": {"type": "Text", "value": "yanshee-01"},
            "status": {"type": "Text", "value": "UNKNOWN"},
            "batteryLevel": {"type": "Text", "value": "UNKNOWN"},
            "supportedActions": {"type": "Array", "value": []},
            "verificationStatus": {"type": "Text", "value": "UNVERIFIED"},
            "verificationSource": {"type": "Text", "value": "unverified-no-sdk-audit"},
            "dataQuality": {"type": "Text", "value": "UNKNOWN"},
        }),
    ]
    failures = 0
    for schema_file, entity in cases:
        schema_path = os.path.join(here, schema_file)
        with open(schema_path) as f:
            schema = json.load(f)
        try:
            jsonschema.validate(instance=entity, schema=schema)
            print(f'OK: {schema_file} entity valid')
        except jsonschema.ValidationError as error:
            failures += 1
            print(f'FAIL: {schema_file} entity invalid: {error.message}')
    return failures

if __name__ == '__main__':
    sys.exit(main() or (1 if validate_entities() else 0))
