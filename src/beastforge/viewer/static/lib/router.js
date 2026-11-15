/**
 * Hash + query deep-link state.
 *
 * Filters live in `?category=<category>&q=<text>` and the stage lives in
 * `#/<creature>/<clip>`. A card selection pushes one history entry; clip
 * switches replace it so Back returns to the gallery rather than walking clips.
 */

function decode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function readState(location = window.location) {
  const params = new URLSearchParams(location.search);
  const category = params.get("category") || "";
  const query = params.get("q") || "";
  const hash = location.hash.startsWith("#") ? location.hash.slice(1) : "";
  const parts = hash.replace(/^\/+/, "").split("/");
  const creature = parts[0] ? decode(parts[0]) : "";
  const clip = parts[1] ? decode(parts[1]) : "";
  return { category, query, creature, clip };
}

function buildUrl({ category = "", query = "", hash = "" }, location = window.location) {
  const params = new URLSearchParams();
  if (category) params.set("category", category);
  if (query) params.set("q", query);
  const search = params.toString();
  return `${location.pathname}${search ? `?${search}` : ""}${hash ? `#${hash}` : ""}`;
}

export function writeFilters({ category = "", query = "" }, location = window.location) {
  const hash = location.hash || "";
  window.history.replaceState({ view: "gallery" }, "", buildUrl({ category, query, hash }, location));
}

export function openCreature(creature, clip, location = window.location) {
  const params = new URLSearchParams(location.search);
  const category = params.get("category") || "";
  const query = params.get("q") || "";
  const hash = `/${encodeURIComponent(creature)}/${encodeURIComponent(clip || "")}`;
  window.history.pushState(
    { view: "stage", creature, clip },
    "",
    buildUrl({ category, query, hash }, location)
  );
}

export function replaceClip(creature, clip, location = window.location) {
  const params = new URLSearchParams(location.search);
  const category = params.get("category") || "";
  const query = params.get("q") || "";
  const hash = `/${encodeURIComponent(creature)}/${encodeURIComponent(clip || "")}`;
  window.history.replaceState(
    { view: "stage", creature, clip },
    "",
    buildUrl({ category, query, hash }, location)
  );
}

export function leaveStage(location = window.location) {
  const params = new URLSearchParams(location.search);
  const category = params.get("category") || "";
  const query = params.get("q") || "";
  if (window.history.state && window.history.state.view === "stage") {
    window.history.back();
    return true;
  }
  window.history.replaceState(
    { view: "gallery" },
    "",
    buildUrl({ category, query, hash: "" }, location)
  );
  return false;
}

export function onRouteChange(callback) {
  const run = () => callback(readState());
  window.addEventListener("popstate", run);
  window.addEventListener("hashchange", run);
  return () => {
    window.removeEventListener("popstate", run);
    window.removeEventListener("hashchange", run);
  };
}
