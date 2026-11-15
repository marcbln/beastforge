/**
 * Clip playback driven by the manifest.
 *
 * `manifest.clips` is the inventory; glTF animations are matched by name. The
 * manifest's duration and loop flag win over glTF metadata, because they are the
 * gameplay contract. Events come from `manifest.events`, never from keyframes.
 */

import * as THREE from "../three/three.module.js";

export function clipInventory(manifest, gltf) {
  const animationNames = new Set(
    (gltf && gltf.animations ? gltf.animations : []).map((animation) => animation.name)
  );
  return (manifest.clips || []).map((clip) => ({
    name: clip.name,
    duration: Number(clip.duration) || 0,
    loop: Boolean(clip.loop),
    generator: clip.generator,
    available: animationNames.has(clip.name),
  }));
}

export function eventsForClip(manifest, clip) {
  return (manifest.events || []).filter((event) => event.clip === clip);
}

export class ClipPlayer {
  constructor(gltf, manifest, { onTime, onClipChange } = {}) {
    this.gltf = gltf;
    this.manifest = manifest;
    this.onTime = onTime || (() => {});
    this.onClipChange = onClipChange || (() => {});
    this.clips = clipInventory(manifest, gltf);
    this.animations = new Map(
      (gltf.animations || []).map((animation) => [animation.name, animation])
    );
    this.mixer = null;
    this.action = null;
    this.current = null;
    this.time = 0;
    this.playing = false;
    this.loop = true;
    this.duration = 0;
  }

  hasClip(name) {
    return this.clips.some((clip) => clip.name === name);
  }

  play(name) {
    const clip = this.clips.find((candidate) => candidate.name === name);
    if (!clip) throw new Error(`Unknown clip ${name}.`);
    if (!clip.available) throw new Error(`Clip ${name} has no matching animation.`);
    if (this.mixer) {
      this.mixer.stopAllAction();
      this.mixer.uncacheRoot(this.gltf.scene);
    }
    this.mixer = new THREE.AnimationMixer(this.gltf.scene);
    const animation = this.animations.get(name);
    this.action = this.mixer.clipAction(animation);
    this.action.reset();
    this.action.setLoop(clip.loop ? THREE.LoopRepeat : THREE.LoopOnce, Infinity);
    this.action.clampWhenFinished = !clip.loop;
    this.action.play();
    this.current = name;
    this.loop = clip.loop;
    this.duration = clip.duration || animation.duration || 0;
    this.time = 0;
    this.playing = true;
    this.onClipChange(clip);
    this.onTime(this.time, this.duration);
  }

  toggle() {
    if (!this.current) return;
    this.playing = !this.playing;
    this.onTime(this.time, this.duration);
  }

  pause() {
    this.playing = false;
    this.onTime(this.time, this.duration);
  }

  resume() {
    if (this.current) this.playing = true;
  }

  seek(time) {
    if (!this.mixer) return;
    const value = Math.max(0, Math.min(Number(time) || 0, this.duration));
    this.mixer.setTime(value);
    this.time = value;
    this.onTime(this.time, this.duration);
  }

  update(dt) {
    if (!this.mixer || !this.playing) return;
    this.mixer.update(dt);
    if (this.loop) {
      this.time = this.duration > 0 ? this.mixer.time % this.duration : 0;
    } else {
      this.time = Math.min(this.mixer.time, this.duration);
      if (this.duration > 0 && this.time >= this.duration) {
        this.time = this.duration;
        this.playing = false;
        this.mixer.setTime(this.duration);
      }
    }
    this.onTime(this.time, this.duration);
  }

  dispose() {
    if (this.mixer) {
      this.mixer.stopAllAction();
      this.mixer.uncacheRoot(this.gltf.scene);
    }
    this.mixer = null;
    this.action = null;
  }
}
