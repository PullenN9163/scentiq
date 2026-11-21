"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import {
  ContactShadows,
  Environment,
  Lightformer,
  MeshTransmissionMaterial,
  OrbitControls,
  RoundedBox,
} from "@react-three/drei";
import * as THREE from "three";
import { bandStarts, type BottleSegment } from "./bottle-model";

const BODY_W = 1.5;
const BODY_H = 2.0;
const BODY_D = 0.78;
const WALL = 0.07;
const BASE_THICK = 0.2;

/** Draws the label onto a texture so no font or image has to be fetched. */
function useLabelTexture(title: string, percent: number) {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 448;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#f4efe6";
    ctx.fillRect(0, 0, 512, 448);
    ctx.strokeStyle = "#8a6a3a";
    ctx.lineWidth = 6;
    ctx.strokeRect(14, 14, 484, 420);
    ctx.lineWidth = 2;
    ctx.strokeRect(26, 26, 460, 396);
    ctx.fillStyle = "#3a3026";
    ctx.textAlign = "center";
    ctx.font = "600 30px Georgia, serif";
    ctx.fillText("SCENT IQ", 256, 92);
    ctx.font = "italic 38px Georgia, serif";
    const text = title.length > 22 ? `${title.slice(0, 21)}…` : title;
    ctx.fillText(text, 256, 200);
    ctx.font = "700 92px Georgia, serif";
    ctx.fillText(`${percent}%`, 256, 322);
    ctx.font = "24px Georgia, serif";
    ctx.fillText("BLEND MATCH", 256, 376);
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
    return texture;
  }, [title, percent]);
}

function Liquid({ segments }: { segments: BottleSegment[] }) {
  const innerW = BODY_W - WALL * 2;
  const innerD = BODY_D - WALL * 2;
  const column = BODY_H - BASE_THICK - 0.18; // liquid stops below the shoulder
  const starts = bandStarts(segments);
  return (
    <group>
      {segments.map((segment, index) => {
        const height = Math.max(0.05, column * segment.share);
        const y = -BODY_H / 2 + BASE_THICK + column * starts[index] + height / 2;
        return (
          <RoundedBox
            key={segment.id}
            args={[innerW, height - 0.004, innerD]}
            radius={0.05}
            smoothness={3}
            position={[0, y, 0]}
          >
            <meshPhysicalMaterial
              color={segment.color}
              transmission={0.62}
              thickness={0.9}
              ior={1.36}
              roughness={0.12}
              attenuationColor={segment.color}
              attenuationDistance={1.1}
              clearcoat={1}
              clearcoatRoughness={0.05}
              transparent
              opacity={0.96}
            />
          </RoundedBox>
        );
      })}
    </group>
  );
}

const PARTICLES = 140;

function Mist({ trigger, color }: { trigger: number; color: string }) {
  const points = useRef<THREE.Points>(null);
  const material = useRef<THREE.PointsMaterial>(null);
  const state = useRef({ start: -10, seeds: new Float32Array(PARTICLES * 3) });
  const [initial] = useState(() => new Float32Array(PARTICLES * 3));
  useEffect(() => {
    if (trigger === 0) return;
    const seeds = state.current.seeds;
    for (let index = 0; index < PARTICLES; index += 1) {
      seeds[index * 3] = (Math.random() - 0.5) * 0.9; // spread x
      seeds[index * 3 + 1] = (Math.random() - 0.35) * 0.7; // spread y
      seeds[index * 3 + 2] = 0.9 + Math.random() * 1.1; // forward speed
    }
    state.current.start = performance.now() / 1000;
  }, [trigger]);
  useFrame(() => {
    const age = performance.now() / 1000 - state.current.start;
    const mesh = points.current;
    const mat = material.current;
    if (!mesh || !mat) return;
    if (age < 0 || age > 1.1) {
      mat.opacity = 0;
      return;
    }
    const seeds = state.current.seeds;
    const positions = (mesh.geometry.getAttribute("position") as THREE.BufferAttribute)
      .array as Float32Array;
    for (let index = 0; index < PARTICLES; index += 1) {
      const delay = (index / PARTICLES) * 0.25;
      const t = Math.max(0, age - delay);
      const drag = 1 - Math.exp(-3 * t);
      positions[index * 3] = seeds[index * 3] * drag * 0.9;
      positions[index * 3 + 1] = seeds[index * 3 + 1] * drag * 0.9 - t * t * 0.12;
      positions[index * 3 + 2] = seeds[index * 3 + 2] * drag;
    }
    mesh.geometry.attributes.position.needsUpdate = true;
    mat.opacity = Math.max(0, 0.75 * (1 - age / 1.1));
    mat.size = 0.03 + age * 0.06;
  });
  return (
    <points ref={points} position={[0, BODY_H / 2 + 0.74, 0.18]} frustumCulled={false}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[initial, 3]} />
      </bufferGeometry>
      <pointsMaterial
        ref={material}
        color={color}
        size={0.04}
        sizeAttenuation
        transparent
        opacity={0}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function Atomizer({ trigger }: { trigger: number }) {
  const actuator = useRef<THREE.Group>(null);
  const pressedAt = useRef(-10);
  useEffect(() => {
    if (trigger !== 0) pressedAt.current = performance.now() / 1000;
  }, [trigger]);
  useFrame(() => {
    const age = performance.now() / 1000 - pressedAt.current;
    if (actuator.current)
      actuator.current.position.y =
        age >= 0 && age < 0.3 ? -0.07 * Math.sin((age / 0.3) * Math.PI) : 0;
  });
  const top = BODY_H / 2;
  const gold = { color: "#c9a45c", metalness: 1, roughness: 0.18 } as const;
  return (
    <group position={[0, top, 0]}>
      {/* glass neck */}
      <mesh position={[0, 0.1, 0]}>
        <cylinderGeometry args={[0.3, 0.34, 0.22, 48]} />
        <MeshTransmissionMaterial
          transmission={1}
          thickness={0.5}
          roughness={0.04}
          ior={1.5}
          samples={4}
          resolution={256}
          backside={false}
        />
      </mesh>
      {/* metal collar with a decorative ring */}
      <mesh position={[0, 0.3, 0]}>
        <cylinderGeometry args={[0.32, 0.32, 0.22, 64]} />
        <meshStandardMaterial {...gold} />
      </mesh>
      <mesh position={[0, 0.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.325, 0.022, 16, 64]} />
        <meshStandardMaterial {...gold} roughness={0.12} />
      </mesh>
      <mesh position={[0, 0.42, 0]}>
        <cylinderGeometry args={[0.26, 0.32, 0.06, 64]} />
        <meshStandardMaterial {...gold} />
      </mesh>
      {/* pump stem and actuator, which dips when pressed */}
      <mesh position={[0, 0.55, 0]}>
        <cylinderGeometry args={[0.07, 0.07, 0.2, 32]} />
        <meshStandardMaterial {...gold} roughness={0.1} />
      </mesh>
      <group ref={actuator}>
        <mesh position={[0, 0.7, 0]}>
          <cylinderGeometry args={[0.17, 0.15, 0.13, 48]} />
          <meshStandardMaterial {...gold} />
        </mesh>
        <mesh position={[0, 0.77, 0]}>
          <cylinderGeometry args={[0.16, 0.16, 0.02, 48]} />
          <meshStandardMaterial color="#1b1814" metalness={0.3} roughness={0.35} />
        </mesh>
        <mesh position={[0, 0.7, 0.2]} rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.032, 0.032, 0.14, 16]} />
          <meshStandardMaterial {...gold} />
        </mesh>
      </group>
      {/* dip tube */}
      <mesh position={[0, -BODY_H / 2 + 0.265, 0]}>
        <cylinderGeometry args={[0.016, 0.016, BODY_H - 0.03, 12]} />
        <meshPhysicalMaterial color="#f5f5f5" transparent opacity={0.55} roughness={0.2} />
      </mesh>
    </group>
  );
}

function Bottle({
  segments,
  title,
  percent,
  trigger,
}: {
  segments: BottleSegment[];
  title: string;
  percent: number;
  trigger: number;
}) {
  const label = useLabelTexture(title, percent);
  return (
    <group position={[0, -0.2, 0]} rotation={[0, 0.5, 0]}>
      {/* heavy glass base */}
      <RoundedBox
        args={[BODY_W, BASE_THICK, BODY_D]}
        radius={0.08}
        smoothness={4}
        position={[0, -BODY_H / 2 + BASE_THICK / 2, 0]}
      >
        <MeshTransmissionMaterial
          transmission={1}
          thickness={1.2}
          roughness={0.03}
          ior={1.52}
          chromaticAberration={0.04}
          samples={4}
          resolution={256}
          backside={false}
        />
      </RoundedBox>
      {/* glass shell */}
      <RoundedBox args={[BODY_W, BODY_H, BODY_D]} radius={0.14} smoothness={6}>
        <MeshTransmissionMaterial
          transmission={1}
          thickness={0.45}
          roughness={0.02}
          ior={1.5}
          chromaticAberration={0.03}
          anisotropicBlur={0.1}
          samples={6}
          resolution={512}
          backside
          backsideThickness={0.3}
          color="#f2fbff"
        />
      </RoundedBox>
      <Liquid segments={segments} />
      {label ? (
        <mesh position={[0, 0.05, BODY_D / 2 + 0.004]}>
          <planeGeometry args={[1.05, 0.92]} />
          <meshStandardMaterial map={label} roughness={0.7} />
        </mesh>
      ) : null}
      <Atomizer trigger={trigger} />
      <Mist trigger={trigger} color={segments[segments.length - 1]?.color ?? "#ffffff"} />
    </group>
  );
}

export default function BlendBottleScene({
  segments,
  title,
  percent,
  trigger,
  reducedMotion,
}: {
  segments: BottleSegment[];
  title: string;
  percent: number;
  trigger: number;
  reducedMotion: boolean;
}) {
  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [0, 0.6, 7.6], fov: 32 }}
      gl={{ antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping }}
    >
      <ambientLight intensity={0.35} />
      <spotLight position={[3, 5, 4]} angle={0.4} penumbra={0.8} intensity={60} />
      {/* A local studio environment: no network fetch, works offline and under strict CSP. */}
      <Environment resolution={256}>
        <Lightformer form="rect" intensity={5} position={[0, 4, 3]} scale={[9, 3, 1]} />
        <Lightformer form="rect" intensity={2.5} position={[-5, 1, -1]} rotation-y={Math.PI / 2} scale={[6, 4, 1]} />
        <Lightformer form="rect" intensity={2.5} position={[5, 1, -1]} rotation-y={-Math.PI / 2} scale={[6, 4, 1]} />
        <Lightformer form="ring" intensity={3} position={[0, 1, -5]} scale={4} />
        <Lightformer form="rect" intensity={1.2} position={[0, -3, 2]} scale={[8, 2, 1]} />
      </Environment>
      <Bottle segments={segments} title={title} percent={percent} trigger={trigger} />
      <ContactShadows position={[0, -1.22, 0]} opacity={0.5} blur={2.8} scale={6} far={2.5} />
      <OrbitControls
        target={[0, 0.35, 0]}
        enablePan={false}
        enableZoom={false}
        minPolarAngle={Math.PI / 3}
        maxPolarAngle={Math.PI / 1.8}
        autoRotate={!reducedMotion}
        autoRotateSpeed={0.9}
      />
    </Canvas>
  );
}
