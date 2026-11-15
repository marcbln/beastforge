/**
 * Tolerant catalog and manifest readers.
 *
 * Known fields are read; unknown fields are ignored so a newer minor document
 * stays usable. A different major `schemaVersion` is rejected with an explicit
 * message instead of being partially interpreted.
 */

const SUPPORTED_MAJOR = "1";

export class CompatibilityError extends Error {
  constructor(kind, version) {
    super(
      `${kind} major version ${version} is not supported; this viewer understands ${SUPPORTED_MAJOR}.x.`
    );
    this.name = "CompatibilityError";
    this.kind = kind;
    this.version = version;
  }
}

function assertMajor(kind, payload) {
  const version = payload && payload.schemaVersion;
  if (typeof version !== "string" || !/^\d+\.\d+$/.test(version)) {
    throw new Error(`${kind} schemaVersion must be MAJOR.MINOR.`);
  }
  if (version.split(".", 1)[0] !== SUPPORTED_MAJOR) {
    throw new CompatibilityError(kind, version);
  }
  return version;
}

export function parseCatalog(payload) {
  const version = assertMajor("catalog", payload);
  for (const key of ["toolVersion", "generatedBy", "categories", "creatures", "warnings"]) {
    if (!(key in payload)) {
      throw new Error(`catalog is missing required field ${key}.`);
    }
  }
  const entries = Array.isArray(payload.creatures) ? payload.creatures : [];
  const byName = new Map();
  for (const entry of entries) {
    if (!entry || typeof entry.name !== "string") continue;
    byName.set(entry.name, entry);
  }
  return {
    schemaVersion: version,
    toolVersion: payload.toolVersion,
    generatedBy: payload.generatedBy,
    categories: Array.isArray(payload.categories) ? payload.categories.slice() : [],
    creatures: entries.slice(),
    warnings: Array.isArray(payload.warnings) ? payload.warnings.slice() : [],
    byName,
  };
}

export async function fetchCatalog(url = "catalog.json") {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load catalog.json (HTTP ${response.status}).`);
  }
  return parseCatalog(await response.json());
}

export async function fetchManifest(entry, base = document.baseURI) {
  const url = new URL(entry.manifest, base).href;
  const response = await fetch(url, { cache: "no-cache" });
  if (!response.ok) {
    throw new Error(`Could not load the manifest for ${entry.name} (HTTP ${response.status}).`);
  }
  const payload = await response.json();
  const version = assertMajor("manifest", payload);
  return { payload, raw: payload, schemaVersion: version };
}

export function manifestUrl(entry, base = document.baseURI) {
  return new URL(entry.manifest, base).href;
}

export function assetUrl(entry, base = document.baseURI) {
  return new URL(entry.asset, base).href;
}
