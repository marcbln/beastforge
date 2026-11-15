/**
 * Live card thumbnails.
 *
 * One shared offscreen WebGL renderer blits 256x256 frames into each card's 2D
 * canvas, so 100 cards never exhaust WebGL contexts. Assets are requested only
 * for cards that intersect the viewport, at most three requests run in flight,
 * and a 24-scene LRU disposes geometry, materials, and textures on eviction.
 */

import * as THREE from "../three/three.module.js";
import { GLTFLoader } from "../three/addons/loaders/GLTFLoader.js";

const SIZE = 256;
const MAX_IN_FLIGHT = 3;
const LRU_LIMIT = 24;
const HOVER_FPS = 15;

function disposeObject(root) {
  root.traverse((node) => {
    if (node.geometry) node.geometry.dispose();
    if (node.material) {
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      for (const material of materials) {
        for (const value of Object.values(material)) {
          if (value && value.isTexture) value.dispose();
        }
        material.dispose();
      }
    }
  });
}

export class ThumbnailManager {
  constructor({ onError, onState } = {}) {
    this.onError = onError || (() => {});
    this.onState = onState || (() => {});
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(1);
    this.renderer.setSize(SIZE, SIZE, false);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xf4f8ff, 0x20262c, 2.2));
    const key = new THREE.DirectionalLight(0xffffff, 2.0);
    key.position.set(3, 5, 4);
    this.scene.add(key);
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.01, 100);
    this.loader = new GLTFLoader();
    this.cache = new Map();
    this.queue = [];
    this.inFlight = 0;
    this.cards = new Map();
    this.reducedMotion =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.hover = null;
    this.observer = new IntersectionObserver(
      (records) => {
        for (const record of records) {
          if (record.isIntersecting) this.enqueue(record.target);
        }
      },
      { rootMargin: "200px" }
    );
  }

  register(entry, canvas, card) {
    this.cards.set(entry.name, { entry, canvas, card });
    this.observer.observe(canvas);
    card.addEventListener("pointerenter", () => this.startHover(entry.name));
    card.addEventListener("pointerleave", () => this.stopHover(entry.name));
    card.addEventListener("focus", () => this.startHover(entry.name));
    card.addEventListener("blur", () => this.stopHover(entry.name));
  }

  enqueue(canvas) {
    const item = [...this.cards.values()].find((candidate) => candidate.canvas === canvas);
    if (!item) return;
    const key = item.entry.name;
    if (this.cache.has(key) || this.queue.some((job) => job.key === key)) return;
    this.queue.push({ key, entry: item.entry, canvas, card: item.card });
    this._pump();
  }

  _pump() {
    while (this.inFlight < MAX_IN_FLIGHT && this.queue.length > 0) {
      const job = this.queue.shift();
      this.inFlight += 1;
      this.onState(job.key, "loading");
      this.loader
        .loadAsync(new URL(job.entry.asset, document.baseURI).href)
        .then((gltf) => {
          this._store(job.key, gltf);
          this.renderTo(job.key, job.canvas);
          this.onState(job.key, "ready");
        })
        .catch((error) => {
          this.onState(job.key, "error");
          this.onError(job.key, error);
        })
        .finally(() => {
          this.inFlight -= 1;
          this._pump();
        });
    }
  }

  _store(key, gltf) {
    const previous = this.cache.get(key);
    if (previous) disposeObject(previous.scene);
    this.cache.delete(key);
    this.cache.set(key, gltf);
    while (this.cache.size > LRU_LIMIT) {
      const oldest = this.cache.keys().next().value;
      const evicted = this.cache.get(oldest);
      this.cache.delete(oldest);
      if (evicted) disposeObject(evicted.scene);
    }
  }

  _prepare(gltf) {
    const object = gltf.scene;
    const box = new THREE.Box3().setFromObject(object);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);
    object.position.sub(center);
    const radius = Math.max(size.length() * 0.5, 0.001);
    this.camera.position.set(radius * 1.4, radius * 0.9, radius * 1.6);
    this.camera.near = radius * 0.01;
    this.camera.far = radius * 20;
    this.camera.updateProjectionMatrix();
    this.camera.lookAt(0, 0, 0);
    this.scene.add(object);
    return object;
  }

  renderTo(key, canvas) {
    const gltf = this.cache.get(key);
    if (!gltf) return;
    const object = this._prepare(gltf);
    this.renderer.render(this.scene, this.camera);
    const context = canvas.getContext("2d");
    if (context) {
      canvas.width = SIZE;
      canvas.height = SIZE;
      context.clearRect(0, 0, SIZE, SIZE);
      context.drawImage(this.renderer.domElement, 0, 0, SIZE, SIZE);
    }
    this.scene.remove(object);
  }

  startHover(key) {
    if (this.reducedMotion) return;
    const item = this.cards.get(key);
    if (!item) return;
    this.stopHover();
    const begin = () => {
      const gltf = this.cache.get(key);
      if (!gltf) return;
      const clip = gltf.animations.find((animation) => /idle/i.test(animation.name));
      if (!clip) return;
      const mixer = new THREE.AnimationMixer(gltf.scene);
      mixer.clipAction(clip).play();
      const object = this._prepare(gltf);
      let last = 0;
      const interval = 1000 / HOVER_FPS;
      const tick = (now) => {
        if (!this.hover || this.hover.key !== key) return;
        if (now - last >= interval) {
          last = now;
          mixer.update(interval / 1000);
          this.renderer.render(this.scene, this.camera);
          const context = item.canvas.getContext("2d");
          if (context) context.drawImage(this.renderer.domElement, 0, 0, SIZE, SIZE);
        }
        this.hover.frame = requestAnimationFrame(tick);
      };
      this.hover = { key, mixer, object, frame: requestAnimationFrame(tick) };
    };
    if (this.cache.has(key)) {
      begin();
    } else {
      this.hover = { key, pending: true };
      this.enqueue(item.canvas);
      const wait = setInterval(() => {
        if (!this.hover || this.hover.key !== key) return clearInterval(wait);
        if (this.cache.has(key)) {
          clearInterval(wait);
          this.hover = null;
          begin();
        }
      }, 120);
    }
  }

  stopHover() {
    if (!this.hover) return;
    if (this.hover.frame) cancelAnimationFrame(this.hover.frame);
    if (this.hover.object) this.scene.remove(this.hover.object);
    if (this.hover.mixer) this.hover.mixer.stopAllAction();
    this.hover = null;
  }

  dispose() {
    this.stopHover();
    this.observer.disconnect();
    for (const gltf of this.cache.values()) disposeObject(gltf.scene);
    this.cache.clear();
    this.queue.length = 0;
    this.renderer.dispose();
  }
}
