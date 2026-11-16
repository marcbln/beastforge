/**
 * Viewer bootstrap: catalog load, gallery filters, deep-link routing, stage,
 * clips, event timeline, and the manifest inspector.
 *
 * Everything displayed comes from catalog.json and the sidecar manifest; the
 * app never derives gameplay facts or regenerates assets.
 */

import {
  CompatibilityError,
  assetUrl,
  fetchCatalog,
  fetchManifest,
} from "./lib/catalog.js";
import {
  leaveStage,
  onRouteChange,
  openCreature,
  readState,
  replaceClip,
  writeFilters,
} from "./lib/router.js";
import { ThumbnailManager } from "./lib/thumbnails.js";
import { ClipPlayer, clipInventory, eventsForClip } from "./lib/clips.js";
import { renderInspector } from "./lib/inspector.js";
import { Stage, loadModel } from "./lib/stage.js";

const els = {
  category: document.getElementById("category-filter"),
  search: document.getElementById("search"),
  clear: document.getElementById("clear-filters"),
  emptyClear: document.getElementById("empty-clear"),
  matchCount: document.getElementById("match-count"),
  gallery: document.getElementById("gallery"),
  galleryView: document.getElementById("gallery-view"),
  empty: document.getElementById("empty-state"),
  warning: document.getElementById("warning-banner"),
  compat: document.getElementById("compat-banner"),
  stageView: document.getElementById("stage-view"),
  stageTitle: document.getElementById("stage-title"),
  stageCategory: document.getElementById("stage-category"),
  stageCanvas: document.getElementById("stage-canvas"),
  stageLoading: document.getElementById("stage-loading"),
  webglBanner: document.getElementById("webgl-banner"),
  back: document.getElementById("back-to-gallery"),
  playPause: document.getElementById("play-pause"),
  timeline: document.getElementById("timeline"),
  marks: document.getElementById("event-marks"),
  clipTime: document.getElementById("clip-time"),
  clipList: document.getElementById("clip-list"),
  inspector: document.getElementById("inspector"),
  toasts: document.getElementById("toast-region"),
};

const state = {
  catalog: null,
  cards: new Map(),
  thumbnails: null,
  manifests: new Map(),
  stage: null,
  player: null,
  gltf: null,
  entry: null,
  manifest: null,
  clip: null,
  marks: [],
};

function toast(message, { error = false } = {}) {
  const node = document.createElement("div");
  node.className = error ? "toast error" : "toast";
  node.textContent = message;
  els.toasts.append(node);
  window.setTimeout(() => node.remove(), 6000);
}

function showBanner(node, message, details = []) {
  node.textContent = "";
  if (!message && details.length === 0) {
    node.hidden = true;
    return;
  }
  if (message) {
    const paragraph = document.createElement("p");
    paragraph.textContent = message;
    node.append(paragraph);
  }
  if (details.length) {
    const list = document.createElement("ul");
    for (const detail of details) {
      const item = document.createElement("li");
      item.textContent = detail;
      list.append(item);
    }
    node.append(list);
  }
  node.hidden = false;
}

async function boot() {
  let catalog;
  try {
    catalog = await fetchCatalog();
  } catch (error) {
    const message =
      error instanceof CompatibilityError
        ? error.message
        : `Could not load the catalog: ${error.message}`;
    showBanner(els.compat, message);
    return;
  }
  state.catalog = catalog;
  populateCategories(catalog);
  if (catalog.warnings.length) {
    showBanner(
      els.warning,
      "Some recipes could not be read; the rest of the gallery is available.",
      catalog.warnings.map((warning) => `${warning.path}: ${warning.message}`)
    );
  }
  try {
    state.thumbnails = new ThumbnailManager({
      onState: (name, status) => {
        const card = state.cards.get(name);
        if (card) card.dataset.state = status;
      },
      onError: (name) => {
        const card = state.cards.get(name);
        if (!card) return;
        card.dataset.state = "error";
        const error = card.querySelector(".card-error");
        if (error) error.hidden = false;
      },
    });
  } catch {
    state.thumbnails = null;
    showBanner(els.compat, "3D thumbnails are unavailable; cards remain usable.");
  }
  renderGallery(catalog.creatures);
  wireControls();
  onRouteChange((next) => route(next));
  route(readState());
}

function populateCategories(catalog) {
  for (const category of catalog.categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    els.category.append(option);
  }
}

function renderGallery(entries) {
  els.gallery.textContent = "";
  state.cards.clear();
  for (const entry of entries) {
    const card = document.createElement("article");
    card.className = "card";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Open ${entry.name}`);
    card.dataset.name = entry.name;
    card.dataset.state = "pending";

    const canvas = document.createElement("canvas");
    canvas.className = "card-canvas";
    canvas.width = 256;
    canvas.height = 256;
    canvas.setAttribute("aria-hidden", "true");

    const name = document.createElement("h2");
    name.className = "card-name";
    name.textContent = entry.name;

    const meta = document.createElement("div");
    meta.className = "card-meta";
    const category = document.createElement("span");
    category.className = "pill";
    category.textContent = entry.category;
    meta.append(category);

    const description = document.createElement("p");
    description.className = "card-description";
    description.textContent = entry.description;

    const tags = document.createElement("ul");
    tags.className = "card-tags";
    for (const tag of entry.tags || []) {
      const item = document.createElement("li");
      item.textContent = tag;
      tags.append(item);
    }

    const error = document.createElement("span");
    error.className = "card-error";
    error.textContent = "Preview unavailable. Open the card to retry.";
    error.hidden = true;

    card.append(canvas, name, meta, description, tags, error);
    card.addEventListener("click", () => select(entry));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select(entry);
      }
    });
    els.gallery.append(card);
    state.cards.set(entry.name, card);
    if (state.thumbnails) state.thumbnails.register(entry, canvas, card);
  }
}

function wireControls() {
  els.category.addEventListener("change", () => {
    writeFilters({ category: els.category.value, query: els.search.value });
    applyFilters();
  });
  els.search.addEventListener("input", () => {
    writeFilters({ category: els.category.value, query: els.search.value });
    applyFilters();
  });
  for (const button of [els.clear, els.emptyClear]) {
    button.addEventListener("click", () => {
      els.category.value = "";
      els.search.value = "";
      writeFilters({ category: "", query: "" });
      applyFilters();
    });
  }
  els.back.addEventListener("click", () => {
    if (!leaveStage()) route(readState());
  });
  els.playPause.addEventListener("click", () => {
    if (!state.player) return;
    state.player.toggle();
    updatePlayPause();
  });
  els.timeline.addEventListener("input", () => {
    if (!state.player) return;
    state.player.seek((Number(els.timeline.value) / 1000) * state.player.duration);
  });
}

function filteredEntries() {
  if (!state.catalog) return [];
  const category = els.category.value;
  const query = els.search.value.trim().toLowerCase();
  return state.catalog.creatures.filter((entry) => {
    if (category && entry.category !== category) return false;
    if (!query) return true;
    const haystack = [entry.name, entry.description, ...(entry.tags || [])]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function applyFilters() {
  if (!state.catalog) return;
  const current = readState();
  if (current.category && !state.catalog.categories.includes(current.category)) {
    els.category.value = "";
    writeFilters({ category: "", query: current.query });
    toast(`Unknown category ${current.category}; showing all categories.`);
  }
  const matches = new Set(filteredEntries().map((entry) => entry.name));
  for (const [name, card] of state.cards) card.hidden = !matches.has(name);
  const total = state.catalog.creatures.length;
  els.matchCount.textContent =
    matches.size === total
      ? `${total} creature${total === 1 ? "" : "s"}`
      : `${matches.size} of ${total} creatures`;
  els.empty.hidden = matches.size !== 0;
}

async function select(entry) {
  let manifest;
  try {
    manifest = await getManifest(entry);
  } catch (error) {
    toast(error.message, { error: true });
    return;
  }
  const firstClip = (manifest.clips && manifest.clips[0] && manifest.clips[0].name) || "";
  openCreature(entry.name, firstClip);
  route(readState());
}

async function getManifest(entry) {
  const key = `${entry.name}:${entry.recipeSha256}`;
  if (state.manifests.has(key)) return state.manifests.get(key);
  const loaded = await fetchManifest(entry);
  state.manifests.set(key, loaded.payload);
  return loaded.payload;
}

async function route(current) {
  if (current.creature) {
    await openStage(current);
    return;
  }
  closeStage();
  applyFilters();
}

async function openStage(current) {
  const entry = state.catalog.byName.get(current.creature);
  if (!entry) {
    toast(`Unknown creature ${current.creature}; returning to the gallery.`, { error: true });
    if (!leaveStage()) applyFilters();
    return;
  }
  let manifest;
  try {
    manifest = await getManifest(entry);
  } catch (error) {
    toast(error.message, { error: true });
    if (!leaveStage()) applyFilters();
    return;
  }
  const clips = clipInventory(manifest, { animations: [] });
  let clip = current.clip;
  if (clip && !clips.some((candidate) => candidate.name === clip)) {
    toast(`Unknown clip ${clip}; using the first declared clip.`);
    clip = "";
  }
  if (!clip) clip = clips.length ? clips[0].name : "";

  els.galleryView.hidden = true;
  els.stageView.hidden = false;
  els.stageTitle.textContent = entry.name;
  els.stageCategory.textContent = entry.category;
  renderInspector(els.inspector, { manifest, raw: manifest, onPlayEvent: playEvent });
  renderClipList(manifest, null);

  if (state.entry && state.entry.name === entry.name && state.gltf) {
    state.manifest = manifest;
    state.clip = clip;
    activateClip(clip, { replace: false, announce: false });
    return;
  }

  disposeStage();
  state.entry = entry;
  state.manifest = manifest;
  state.clip = clip;
  els.stageLoading.hidden = false;
  els.webglBanner.hidden = true;
  try {
    state.stage = new Stage(els.stageCanvas);
  } catch {
    state.stage = null;
    els.webglBanner.hidden = false;
    els.stageLoading.hidden = true;
    renderClipList(manifest, null);
    return;
  }
  try {
    const gltf = await loadModel(assetUrl(entry));
    state.gltf = gltf;
    state.stage.setModel(gltf, manifest);
    state.stage.start();
    const player = new ClipPlayer(gltf, manifest, {
      onTime: updateTime,
      onClipChange: () => {},
    });
    state.player = player;
    state.stage.onFrame = (dt) => player.update(dt);
    renderClipList(manifest, player);
    activateClip(clip, { replace: false, announce: false });
    els.stageLoading.hidden = true;
  } catch (error) {
    els.stageLoading.hidden = true;
    toast(`Could not load ${entry.name}: ${error.message}`, { error: true });
  }
}

function renderClipList(manifest, player) {
  els.clipList.textContent = "";
  const inventory = clipInventory(manifest, state.gltf || { animations: [] });
  for (const clip of inventory) {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "clip-button";
    button.dataset.clip = clip.name;
    button.textContent = `${clip.name} · ${clip.duration.toFixed(2)}s${clip.loop ? " ↻" : ""}`;
    button.setAttribute("aria-pressed", "false");
    button.disabled = !clip.available;
    if (!clip.available) {
      button.title = "This clip has no matching animation in the GLB.";
    } else {
      button.addEventListener("click", () => activateClip(clip.name, { replace: true }));
    }
    item.append(button);
    if (!clip.available) {
      const warning = document.createElement("span");
      warning.className = "clip-warning";
      warning.textContent = " no matching animation";
      item.append(warning);
    }
    els.clipList.append(item);
  }
  if (player) updateClipButtons(player.current);
}

function activateClip(name, { replace = true, announce = true } = {}) {
  if (!state.manifest || !state.entry) return;
  const inventory = clipInventory(state.manifest, state.gltf || { animations: [] });
  const clip = inventory.find((candidate) => candidate.name === name);
  state.clip = name;
  if (replace && state.entry) replaceClip(state.entry.name, name);
  renderMarks(state.manifest, name);
  if (announce && !clip) toast(`Clip ${name} is not declared.`);
  if (!state.player || !clip || !clip.available) {
    els.playPause.disabled = true;
    updateClipButtons(name);
    return;
  }
  try {
    state.player.play(name);
  } catch (error) {
    toast(error.message, { error: true });
    return;
  }
  els.playPause.disabled = false;
  updatePlayPause();
  updateClipButtons(name);
  updateTime(0, state.player.duration);
}

function playEvent(event) {
  if (!state.manifest || !state.entry) return;
  if (!state.player) {
    toast("The creature is still loading; try again in a moment.", { error: true });
    return;
  }
  const inventory = clipInventory(state.manifest, state.gltf || { animations: [] });
  const clip = inventory.find((candidate) => candidate.name === event.clip);
  if (!clip || !clip.available) {
    toast(`Clip ${event.clip} has no matching animation in the GLB.`, { error: true });
    return;
  }
  activateClip(event.clip, { replace: true, announce: true });
  if (!state.player || state.player.current !== event.clip) return;
  const eventTime = Number(event.time);
  const start = Math.max(0, (Number.isFinite(eventTime) ? eventTime : 0) - 0.35);
  state.player.seek(start);
  state.player.resume();
  updatePlayPause();
}

function updateClipButtons(active) {
  const buttons = els.clipList.querySelectorAll(".clip-button");
  buttons.forEach((button) => {
    button.setAttribute("aria-pressed", button.dataset.clip === active ? "true" : "false");
  });
}

function updatePlayPause() {
  const playing = state.player && state.player.playing;
  els.playPause.textContent = playing ? "Pause" : "Play";
}

function renderMarks(manifest, clip) {
  els.marks.textContent = "";
  state.marks = [];
  const events = eventsForClip(manifest, clip);
  const declared = (manifest.clips || []).find((candidate) => candidate.name === clip);
  const duration = declared && declared.duration ? declared.duration : 0;
  for (const event of events) {
    const mark = document.createElement("button");
    mark.type = "button";
    mark.className = "event-mark";
    mark.textContent = event.name;
    const ratio = duration > 0 ? Math.min(Math.max(event.time / duration, 0), 1) : 0;
    mark.style.left = `${ratio * 100}%`;
    mark.title = `${event.name} at ${Number(event.time).toFixed(2)}s`;
    mark.addEventListener("click", () => {
      if (!state.player) return;
      state.player.seek(event.time);
      els.timeline.value = String(Math.round(ratio * 1000));
    });
    els.marks.append(mark);
    state.marks.push({ element: mark, time: Number(event.time) });
  }
  updateTime(state.player ? state.player.time : 0, state.player ? state.player.duration : duration);
}

function updateTime(time, duration) {
  const safeDuration = duration > 0 ? duration : 0;
  const ratio = safeDuration > 0 ? Math.min(Math.max(time / safeDuration, 0), 1) : 0;
  els.timeline.value = String(Math.round(ratio * 1000));
  els.clipTime.textContent = `${Number(time).toFixed(2)} s`;
  let nearest = null;
  let best = Infinity;
  for (const mark of state.marks) {
    const delta = Math.abs(mark.time - time);
    if (delta < best) {
      best = delta;
      nearest = mark;
    }
  }
  for (const mark of state.marks) {
    if (mark === nearest && safeDuration > 0 && best <= safeDuration * 0.05) {
      mark.element.setAttribute("aria-current", "true");
    } else {
      mark.element.removeAttribute("aria-current");
    }
  }
  updatePlayPause();
}

function closeStage() {
  els.stageView.hidden = true;
  els.galleryView.hidden = false;
  disposeStage();
}

function disposeStage() {
  if (state.player) {
    state.player.dispose();
    state.player = null;
  }
  if (state.stage) {
    state.stage.dispose();
    state.stage = null;
  }
  state.gltf = null;
  state.entry = null;
  state.manifest = null;
  state.marks = [];
}

window.addEventListener("beforeunload", () => {
  if (state.thumbnails) state.thumbnails.dispose();
  disposeStage();
});

boot();
