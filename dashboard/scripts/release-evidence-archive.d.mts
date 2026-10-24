/**
 * Type declarations for `scripts/release-evidence-archive.mjs`.
 *
 * The archive orchestrator is a plain ES module so it can be executed directly
 * by Node (`npm run release:evidence:archive`). These declarations give the
 * TypeScript test suite a typed contract for the exported manifest and gate
 * helpers.
 */

export interface ArchiveArtifact {
  file: string;
  sha256: string;
  bytes: number;
}

export interface ArchiveManifest {
  schema: string;
  commit: string;
  generatedAt: string;
  generator: string;
  artifactCount: number;
  artifacts: ArchiveArtifact[];
}

export interface ManifestMismatch {
  file: string;
  issue: string;
}

export interface ManifestVerification {
  ok: boolean;
  checked: number;
  mismatches: ManifestMismatch[];
}

export interface BlockingAdvisory {
  name: string;
  severity: string;
  isDirect: boolean;
  range: string | null;
}

export declare const BLOCKING_SEVERITIES: string[];

export declare const VERIFY_COMMAND: string;

export declare function runNpmCapture(
  args: string[],
  cwd: string,
): { stdout: string; status: number };

export declare function gitHead(cwd: string): string | null;

export declare function sha256File(file: string): string;

export declare function collectFiles(dir: string, prefix?: string): string[];

export declare function createTempArchive(
  files: Record<string, string>,
): string;

export declare function cleanupTempArchive(dir: string): void;

export declare function writeArchiveFile(
  dir: string,
  name: string,
  contents: string,
): void;

export declare function removeArchiveFile(dir: string, name: string): void;

export declare function buildManifest(outDir: string, commit: string): ArchiveManifest;

export declare function writeManifest(
  outDir: string,
  commit: string,
): ArchiveManifest;

export declare function verifyManifest(outDir: string): ManifestVerification;

export declare function blockingAdvisories(
  audit: Record<string, unknown>,
  severities?: string[],
): BlockingAdvisory[];

export declare function writeSums(outDir: string, artifacts: ArchiveArtifact[]): void;
