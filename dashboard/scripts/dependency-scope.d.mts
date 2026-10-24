/**
 * Type declarations for `scripts/dependency-scope.mjs`.
 *
 * The analyser is a plain ES module so it can be executed directly by Node
 * (including the release-evidence generator) without a build step. These
 * declarations give the TypeScript test suite a typed contract for the
 * module's exported API.
 */

export type DependencyScope = 'runtime' | 'development/build' | 'unresolved';

export interface LockfilePackage {
  name: string;
  version: string;
  dev: boolean;
  optional: boolean;
  peer: boolean;
  depth: number;
}

export interface LockfileIndex {
  get(path: string): LockfilePackage | undefined;
  has(path: string): boolean;
  readonly size: number;
  entries(): IterableIterator<[string, LockfilePackage]>;
  [Symbol.iterator](): IterableIterator<[string, LockfilePackage]>;
}

export interface InstallPath {
  chain: string[];
  isDev: boolean;
}

export interface ScopeClassification {
  version: string;
  scope: DependencyScope;
  runtime: InstallPath[];
  dev: InstallPath[];
}

export interface AdvisoryViaEntry {
  title?: string;
  severity?: string;
  vulnerableRange?: string;
  url?: string;
  ghsa?: string | null;
  cve?: string | null;
  cwe?: string | null;
  cvss?: number | null;
  source?: string;
}

export interface FixAvailable {
  name?: string;
  version?: string;
  isSemVerMajor?: boolean;
}

export interface InstalledAdvisory {
  nodePath: string;
  version: string;
  scope: DependencyScope;
  runtimePaths: string[][];
  developmentPaths: string[][];
}

export interface Advisory {
  package: string;
  severity: string;
  isDirect: boolean;
  vulnerableRange: string;
  fixAvailable: FixAvailable | null;
  via: AdvisoryViaEntry[];
  installed: InstalledAdvisory[];
  pathScope: DependencyScope;
  inProductionClosure: boolean | null;
  runtimeReachable: boolean;
  developmentOnly: boolean;
}

export interface AdvisoryTotals {
  info?: number;
  low?: number;
  moderate?: number;
  high?: number;
  critical?: number;
  total?: number;
}

export interface AdvisoryReport {
  generatedFrom: string;
  lockfile: string;
  npmVersion: string | null;
  totals: AdvisoryTotals | null;
  productionClosureAvailable: boolean;
  productionClosureSize: number | null;
  advisories: Advisory[];
}

export declare function indexLockfile(lock: object): LockfileIndex;

export declare function resolveFrom(
  index: LockfileIndex,
  fromPath: string,
  depName: string,
): string | null;

export declare function declaredDependencies(
  lock: object,
  path: string,
): Record<string, string>;

export declare function findInstallPaths(
  lock: object,
  index: LockfileIndex,
  targetPath: string,
  maxDepth?: number,
): InstallPath[];

export declare function classifyScope(
  lock: object,
  index: LockfileIndex,
  path: string,
): ScopeClassification;

export declare function runNpm(args: string[]): string;

export declare function productionClosureNames(): Set<string> | null;

export declare function productionClosure(): Map<string, string> | null;

export declare function lockfileProductionClosure(lock: object): Map<string, string>;

export declare function analyseAdvisories(
  audit: object,
  lock: object,
  productionClosure?: Set<string> | null,
): AdvisoryReport;

export declare function formatSummary(report: AdvisoryReport): string;
