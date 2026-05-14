"use client";

import { motion } from "framer-motion";

export function BackgroundRipples() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      <div className="absolute left-1/2 top-[42%] h-[140vmin] w-[140vmin] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.55)_0%,transparent_55%)]" />
      <div className="absolute left-1/2 top-[42%] h-[95vmin] w-[95vmin] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/25" />
      <div className="absolute left-1/2 top-[42%] h-[72vmin] w-[72vmin] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/15" />
      <div className="absolute left-1/2 top-[42%] h-[52vmin] w-[52vmin] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/12" />
      <div className="absolute inset-0 bg-gradient-to-b from-white/35 via-transparent to-transparent" />
    </div>
  );
}

const blobStyle = {
  background:
    "conic-gradient(from 120deg at 50% 50%, #f9c8ff 0deg, #c8e8ff 120deg, #fff6c8 240deg, #f9c8ff 360deg)",
} as const;

export function IridescentBlob({
  className,
  size = 120,
  blur = 28,
  delay = 0,
}: {
  className?: string;
  size?: number;
  blur?: number;
  delay?: number;
}) {
  return (
    <motion.div
      className={`absolute rounded-full ${className ?? ""}`}
      style={{
        width: size,
        height: size,
        filter: `blur(${blur}px)`,
        opacity: 0.85,
        ...blobStyle,
      }}
      initial={{ scale: 0.92, opacity: 0 }}
      animate={{
        scale: [0.92, 1.04, 0.98, 1.02, 0.92],
        opacity: [0.75, 0.9, 0.8, 0.88, 0.75],
        rotate: [0, 8, -6, 4, 0],
      }}
      transition={{
        duration: 14 + delay,
        repeat: Infinity,
        ease: "easeInOut",
        delay,
      }}
    />
  );
}

export function CharcoalOrb({ className, text, color }: { className?: string; text?: string; color?: string }) {
  return (
    <div
      style={color ? { backgroundColor: color } : undefined}
      className={`relative flex items-center justify-center overflow-hidden rounded-full ${!color ? 'bg-neutral-900' : ''} shadow-[inset_0_-10px_20px_rgba(0,0,0,0.05),inset_0_10px_20px_rgba(255,255,255,0.8)] ${className ?? ""}`}
      aria-hidden
    >
      {/* White overlay to turn bright colors into pastel */}
      {color && <div className="absolute inset-0 bg-white/50 mix-blend-lighten" />}
      {color && <div className="absolute inset-0 bg-white/40" />}
      
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_25%,rgba(255,255,255,0.8),transparent_50%),repeating-conic-gradient(from_0deg,rgba(255,255,255,0.15)_0deg_4deg,transparent_4deg_9deg)]" />
      
      {text && (
        <span className="z-10 text-xs font-semibold uppercase tracking-widest text-neutral-800/60 mix-blend-multiply">
          {text}
        </span>
      )}
    </div>
  );
}
