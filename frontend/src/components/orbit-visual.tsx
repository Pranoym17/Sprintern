"use client";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";

type Logo = { name: string; logo: string };

type NodeConfig = {
  ring: 1 | 2 | 3 | 4;
  angle: number;
  size: 58 | 78 | 88;
  shape: "round" | "square";
  glow: "violet" | "teal" | "amber";
  delay: number;
};

const RINGS: Record<NodeConfig["ring"], { diameter: number; spin: "cw" | "ccw"; duration: number }> = {
  1: { diameter: 353, spin: "ccw", duration: 30 },
  2: { diameter: 501, spin: "cw", duration: 40 },
  3: { diameter: 649, spin: "cw", duration: 50 },
  4: { diameter: 797, spin: "ccw", duration: 60 },
};

const NODES: NodeConfig[] = [
  { ring: 1, angle: 270, size: 58, shape: "square", glow: "violet", delay: 0.6 },
  { ring: 2, angle: 60, size: 58, shape: "round", glow: "amber", delay: 0.9 },
  { ring: 2, angle: 180, size: 78, shape: "round", glow: "teal", delay: 1.2 },
  { ring: 2, angle: 300, size: 58, shape: "square", glow: "violet", delay: 1.5 },
  { ring: 3, angle: 130, size: 88, shape: "round", glow: "amber", delay: 1.7 },
  { ring: 4, angle: 30, size: 58, shape: "round", glow: "teal", delay: 1.9 },
  { ring: 4, angle: 95, size: 88, shape: "square", glow: "violet", delay: 2.05 },
  { ring: 4, angle: 220, size: 88, shape: "square", glow: "amber", delay: 2.15 },
  { ring: 4, angle: 320, size: 58, shape: "round", glow: "teal", delay: 2.3 },
];

function useCountUp(target: number, delayMs = 300, durationMs = 2000) {
  const [value, setValue] = useState(0);
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const reducedMotionUpdate = window.setTimeout(() => setValue(target), 0);
      return () => window.clearTimeout(reducedMotionUpdate);
    }
    let frame = 0;
    const start = window.setTimeout(() => {
      const startTime = performance.now();
      const tick = (now: number) => {
        const progress = Math.min(1, (now - startTime) / durationMs);
        const eased = 1 - (1 - progress) ** 3;
        setValue(Math.round(eased * target));
        if (progress < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    }, delayMs);
    return () => { window.clearTimeout(start); cancelAnimationFrame(frame); };
  }, [target, delayMs, durationMs]);
  return value;
}

export function OrbitVisual({ logos, id }: { logos: Logo[]; id?: string }) {
  const count = useCountUp(logos.length);
  return (
    <div className="orbit-visual" id={id} aria-label="Companies Sprintern watches for you">
      <div className="orbit-visual__stage">
        {([1, 2, 3, 4] as const).map((ring) => (
          <div key={ring} className={`orbit-ring orbit-ring--${ring} orbit-ring--${RINGS[ring].spin}`} style={{ width: RINGS[ring].diameter, height: RINGS[ring].diameter, animationDuration: `${RINGS[ring].duration}s` }} aria-hidden="true" />
        ))}
        {NODES.map((node, index) => {
          const logo = logos[index % logos.length];
          const ring = RINGS[node.ring];
          const counterSpin = ring.spin === "cw" ? "ccw" : "cw";
          return (
            <div
              key={`${node.ring}-${node.angle}-${index}`}
              className="orbit-node"
              style={{ "--node-angle": `${node.angle}deg`, "--node-radius": `${ring.diameter / 2}px` } as React.CSSProperties}
            >
              <div className="orbit-node__enter" style={{ animationDelay: `${node.delay}s` }}>
                <div className={`orbit-node__counter orbit-node__counter--${counterSpin}`} style={{ animationDuration: `${ring.duration}s` }}>
                  <span className={`orbit-node__logo orbit-node__logo--${node.shape} orbit-node__logo--${node.size} orbit-node__logo--glow-${node.glow}`}>
                    <Image src={logo.logo} alt={logo.name} width={node.size} height={node.size} />
                  </span>
                </div>
              </div>
            </div>
          );
        })}
        <div className="orbit-center">
          <strong>{count}</strong>
          <span>Employers watched</span>
        </div>
      </div>
    </div>
  );
}
