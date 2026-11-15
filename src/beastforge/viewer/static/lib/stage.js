/**
 * Orbit stage: one renderer, manifest-driven framing, and deterministic
 * lighting. Manifest `bounds` and `suggestedScale` are the only framing inputs;
 * nothing here re-derives creature facts.
 */

import * as THREE from "../three/three.module.js";
import { OrbitControls } from "../three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "../three/addons/loaders/GLTFLoader.js";

const loader = new GLTFLoader();

export async function loadModel(url) {
  return loader.loadAsync(url);
}

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

function finiteVector(value, fallback) {
  if (!Array.isArray(value) || value.length < 3) return fallback;
  const numbers = value.slice(0, 3).map(Number);
  return numbers.every(Number.isFinite) ? numbers : fallback;
}

export class Stage {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(42, 1, 0.01, 200);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.enablePan = true;
    this.controls.screenSpacePanning = true;
    this.controls.minPolarAngle = 0.15;
    this.controls.maxPolarAngle = Math.PI - 0.15;

    this.scene.add(new THREE.HemisphereLight(0xf4f8ff, 0x1a1f24, 2.4));
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(4, 7, 5);
    this.scene.add(key);
    this.fill = new THREE.DirectionalLight(0x9fb4ff, 0.6);
    this.fill.position.set(-5, 3, -4);
    this.scene.add(this.fill);

    this.model = null;
    this.frame = null;
    this.onFrame = null;
    this._last = 0;
    this._running = false;
    this._resize = new ResizeObserver(() => this.resize());
    this._resize.observe(canvas.parentElement || canvas);
    this.resize();
  }

  resize() {
    const host = this.canvas.parentElement || this.canvas;
    const width = Math.max(host.clientWidth || 640, 1);
    const height = Math.max(host.clientHeight || 380, 1);
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  setModel(gltf, manifest) {
    this.clearModel();
    const object = gltf.scene;
    const scale = Number(manifest && manifest.suggestedScale);
    if (Number.isFinite(scale) && scale > 0 && scale !== 1) {
      object.scale.setScalar(scale);
    }
    this.scene.add(object);
    this.model = object;

    const fallback = new THREE.Vector3(1, 1, 1);
    const min = finiteVector(manifest && manifest.bounds && manifest.bounds.min, null);
    const max = finiteVector(manifest && manifest.bounds && manifest.bounds.max, null);
    let box;
    if (min && max) {
      box = new THREE.Box3(new THREE.Vector3(...min), new THREE.Vector3(...max));
      if (scale > 0) {
        box.min.multiplyScalar(scale);
        box.max.multiplyScalar(scale);
      }
    } else {
      box = new THREE.Box3().setFromObject(object);
      if (box.isEmpty()) box.setFromCenterAndSize(new THREE.Vector3(), fallback);
    }
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const radius = Math.max(sphere.radius, 0.01);
    const center = sphere.center;

    const fov = (this.camera.fov * Math.PI) / 180;
    const distance = (radius / Math.sin(fov / 2)) * 1.15;
    const direction = new THREE.Vector3(1, 0.55, 1).normalize();
    this.camera.position.copy(center).addScaledVector(direction, distance);
    this.camera.near = Math.max(radius * 0.01, 0.01);
    this.camera.far = radius * 50;
    this.camera.updateProjectionMatrix();
    this.controls.target.copy(center);
    this.controls.minDistance = radius * 0.4;
    this.controls.maxDistance = radius * 8;
    this.controls.update();
    return object;
  }

  start() {
    if (this._running) return;
    this._running = true;
    this._last = performance.now();
    const tick = (now) => {
      if (!this._running) return;
      const dt = Math.min((now - this._last) / 1000, 0.1);
      this._last = now;
      if (this.onFrame) this.onFrame(dt);
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  stop() {
    this._running = false;
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = null;
  }

  clearModel() {
    if (!this.model) return;
    this.scene.remove(this.model);
    disposeObject(this.model);
    this.model = null;
  }

  dispose() {
    this.stop();
    this.clearModel();
    this._resize.disconnect();
    this.controls.dispose();
    this.renderer.dispose();
  }
}

export { disposeObject };
