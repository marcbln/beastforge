/**
 * Manifest inspector with three tabs: Manifest, Clips, Events.
 *
 * Values are displayed verbatim from the manifest. Missing optional fields read
 * "not declared"; unknown fields are ignored for behaviour and shown in the
 * collapsible raw view.
 */

const NOT_DECLARED = "not declared";

function el(tag, attributes = {}, text) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (value === undefined || value === null) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function display(value) {
  if (value === undefined || value === null || value === "") return NOT_DECLARED;
  if (Array.isArray(value)) return value.length ? value.join(", ") : NOT_DECLARED;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function factGrid(rows) {
  const list = el("dl", { class: "fact-grid" });
  for (const [label, value] of rows) {
    list.append(el("dt", {}, label), el("dd", {}, display(value)));
  }
  return list;
}

function table(headers, rows) {
  const node = el("table");
  const head = el("thead");
  const headRow = el("tr");
  for (const header of headers) headRow.append(el("th", { scope: "col" }, header));
  head.append(headRow);
  const body = el("tbody");
  if (rows.length === 0) {
    const row = el("tr");
    const cell = el("td", { colspan: String(headers.length) }, NOT_DECLARED);
    row.append(cell);
    body.append(row);
  } else {
    for (const values of rows) {
      const row = el("tr");
      for (const value of values) row.append(el("td", {}, display(value)));
      body.append(row);
    }
  }
  node.append(head, body);
  return node;
}

function manifestPanel(manifest, raw) {
  const panel = el("div", { class: "tab-panel", role: "tabpanel" });
  const creature = manifest.creature || {};
  const provenance = manifest.provenance || {};
  const skeleton = manifest.skeleton || {};
  const playback = manifest.playback || {};
  const budgets = manifest.budgets || {};
  panel.append(
    factGrid([
      ["name", creature.name],
      ["category", creature.category],
      ["description", creature.description],
      ["manifest schema", manifest.schemaVersion],
      ["tool version", manifest.toolVersion],
      ["generator", manifest.generator],
      ["units", manifest.units],
      ["up axis", manifest.upAxis],
      ["forward axis", manifest.forwardAxis],
      ["bounds min", manifest.bounds && manifest.bounds.min],
      ["bounds max", manifest.bounds && manifest.bounds.max],
      ["suggested scale", manifest.suggestedScale],
      ["recipe path", provenance.recipePath],
      ["recipe sha256", provenance.recipeSha256],
      ["recipe version", provenance.recipeVersion],
      ["texforge version", provenance.texforgeVersion],
      ["skeleton root", skeleton.root],
      ["joints", Array.isArray(skeleton.joints) ? skeleton.joints.length : undefined],
      ["playback", playback.eventTimeScaling],
      ["playback warning", playback.warning],
      ["budget vertices", budgets.vertices],
      ["budget bones", budgets.bones],
      ["budget triangles", budgets.triangles],
    ])
  );

  panel.append(el("h3", {}, "Sockets"));
  panel.append(
    table(
      ["name", "target", "offset"],
      (manifest.sockets || []).map((socket) => [socket.name, socket.target, socket.offset])
    )
  );
  panel.append(el("h3", {}, "Volumes"));
  panel.append(
    table(
      ["name", "role", "center", "extents", "bone"],
      (manifest.volumes || []).map((volume) => [
        volume.name,
        volume.role,
        volume.center,
        volume.extents,
        volume.bone,
      ])
    )
  );
  panel.append(el("h3", {}, "Phases"));
  panel.append(
    table(
      ["name", "threshold"],
      (manifest.phases || []).map((phase) => [phase.name, phase.threshold])
    )
  );
  panel.append(el("h3", {}, "Materials"));
  panel.append(
    table(
      ["name", "slot", "metallic", "roughness", "texture", "sha256"],
      (manifest.materials || []).map((material) => [
        material.name,
        material.slot,
        material.metallic,
        material.roughness,
        material.texture && material.texture.recipe,
        material.texture && material.texture.sha256,
      ])
    )
  );

  const details = el("details");
  details.append(el("summary", {}, "Raw manifest"));
  details.append(el("pre", {}, JSON.stringify(raw, null, 2)));
  panel.append(details);
  return panel;
}

function clipsPanel(manifest) {
  const panel = el("div", { class: "tab-panel", role: "tabpanel" });
  panel.append(el("h3", {}, "Declared clips"));
  panel.append(
    table(
      ["name", "duration", "loop", "generator"],
      (manifest.clips || []).map((clip) => [clip.name, clip.duration, clip.loop, clip.generator])
    )
  );
  return panel;
}

function eventsPanel(manifest) {
  const panel = el("div", { class: "tab-panel", role: "tabpanel" });
  panel.append(el("h3", {}, "Declared events"));
  panel.append(
    table(
      ["clip", "time", "name"],
      (manifest.events || []).map((event) => [event.clip, event.time, event.name])
    )
  );
  return panel;
}

export function renderInspector(host, { manifest, raw }) {
  host.textContent = "";
  const tabs = [
    { id: "manifest", label: "Manifest", build: () => manifestPanel(manifest, raw) },
    { id: "clips", label: "Clips", build: () => clipsPanel(manifest) },
    { id: "events", label: "Events", build: () => eventsPanel(manifest) },
  ];
  const bar = el("div", { class: "tabs", role: "tablist", "aria-label": "Manifest views" });
  const body = el("div");
  const buttons = new Map();
  const panels = new Map();

  const select = (id) => {
    for (const [tabId, button] of buttons) {
      const active = tabId === id;
      button.setAttribute("aria-selected", active ? "true" : "false");
      button.tabIndex = active ? 0 : -1;
    }
    body.textContent = "";
    body.append(panels.get(id));
  };

  for (const tab of tabs) {
    const button = el("button", {
      type: "button",
      role: "tab",
      class: "tab",
      id: `tab-${tab.id}`,
      "aria-controls": `panel-${tab.id}`,
    }, tab.label);
    const panel = tab.build();
    panel.id = `panel-${tab.id}`;
    panel.setAttribute("aria-labelledby", `tab-${tab.id}`);
    buttons.set(tab.id, button);
    panels.set(tab.id, panel);
    button.addEventListener("click", () => select(tab.id));
    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const index = tabs.findIndex((candidate) => candidate.id === id);
      const next = tabs[(index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length];
      select(next.id);
      buttons.get(next.id).focus();
    });
    bar.append(button);
  }
  host.append(bar, body);
  select("manifest");
}
