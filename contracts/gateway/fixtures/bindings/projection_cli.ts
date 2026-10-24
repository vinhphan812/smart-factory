/**
 * Projection CLI — prints the TypeScript projection of a fixture as JSON on stdout.
 *
 * Used by `contracts/gateway/fixtures/validate_fixtures.py` to prove that the
 * TypeScript binding reproduces the `react` section of the fixture's `expected_state`.
 *
 * Usage: node --experimental-strip-types projection_cli.ts <fixture-path>
 */

import { readFileSync } from 'node:fs';
import { projectFixture, type Fixture } from './gatewayClient.ts';

const path = process.argv[2];
if (path === undefined) {
  console.error('usage: projection_cli.ts <fixture-path>');
  process.exit(2);
}

const fixture = JSON.parse(readFileSync(path, 'utf8')) as Fixture;
const projected = projectFixture(fixture, 'react');
process.stdout.write(JSON.stringify(projected));
