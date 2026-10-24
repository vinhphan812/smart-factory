/**
 * Type declarations for `scripts/release-evidence.mjs`.
 *
 * The generator is a plain ES module so it can be executed directly by Node
 * (`npm run release:evidence`). These declarations give the TypeScript test
 * suite a typed contract for the exported derivation helpers.
 */

export interface SbomComponent {
  name: string;
  version: string;
  'bom-ref'?: string;
  [key: string]: unknown;
}

export interface SbomDependency {
  ref: string;
  dependsOn?: string[];
  [key: string]: unknown;
}

export interface SbomMetadata {
  component?: { 'bom-ref'?: string; [key: string]: unknown };
  properties?: { name: string; value: string }[];
  [key: string]: unknown;
}

export interface SbomDocument {
  metadata: SbomMetadata;
  components: SbomComponent[];
  dependencies: SbomDependency[];
  [key: string]: unknown;
}

export interface ClosureMismatch {
  component: string;
  issue: string;
}

export interface ProductionClosureCrossCheck {
  available: boolean;
  closurePackageCount?: number;
  mismatches: ClosureMismatch[];
  consistent: boolean | null;
}

export interface Separation {
  runtimeComponentCount: number;
  developmentBuildComponentCount: number;
  totalComponentCount: number;
  runtimeComponents: string[];
  developmentBuildComponents: string[];
  productionClosureCrossCheck: ProductionClosureCrossCheck;
}

export interface SeparationResult extends Separation {}

export declare function deriveRuntimeSbom(
  fullSbom: SbomDocument,
  closureVersions: Map<string, string>,
): SbomDocument;

export declare function buildSeparation(
  fullSbom: SbomDocument | null,
  closureVersions: Map<string, string> | null,
): Separation;
