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

if __name__ == '__main__':
    main()
