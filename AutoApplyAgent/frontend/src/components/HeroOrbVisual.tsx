"use client";

import { motion } from "framer-motion";

function StarFour({ className }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden>
      <path d="M7 0L8.2 5.8L14 7L8.2 8.2L7 14L5.8 8.2L0 7L5.8 5.8L7 0Z" />
    </svg>
  );
}

function IconPlus({ className }: { className?: string }) {
  return (
    <svg className={className} width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
      <path d="M6 1v10M1 6h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconHeadphones({ className }: { className?: string }) {
  return (
    <svg className={className} width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M4 14v4a2 2 0 002 2h1M20 14v4a2 2 0 01-2 2h-1M6 14h2v6H6a2 2 0 01-2-2v-2a2 2 0 012-2zm12 0h2a2 2 0 012 2v2a2 2 0 01-2 2h-2v-6zM6 10a6 6 0 1112 0"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconPlaySm({ className }: { className?: string }) {
  return (
    <svg className={className} width="12" height="12" viewBox="0 0 12 12" fill="currentColor" aria-hidden>
      <path d="M2 1l9 5-9 5V1z" />
    </svg>
  );
}

export type HeroOrbVariant = "screen1" | "screen2";

export function HeroOrbVisual({ variant }: { variant: HeroOrbVariant }) {
  return (
    <div className="relative mx-auto flex aspect-square w-[min(78vw,380px)] items-center justify-center">
      <motion.div
        className="relative z-20 h-[72%] w-[72%] rounded-full shadow-[0_24px_80px_-20px_rgba(0,0,0,0.15)]"
        animate={{ y: [0, -10, 0] }}
        transition={{ duration: 4.2, repeat: Infinity, ease: "easeInOut" }}
        style={{
          background:
            "radial-gradient(circle at 32% 28%, rgba(255,255,255,0.95) 0%, transparent 42%), radial-gradient(circle at 70% 65%, rgba(200,232,255,0.9) 0%, transparent 45%), radial-gradient(circle at 40% 80%, rgba(255,200,230,0.75) 0%, transparent 40%), conic-gradient(from 200deg at 50% 50%, #f0f4ff, #fde4f2, #e8f7ff, #fff8e7, #f0f4ff)",
        }}
        aria-hidden
      >
        <div className="absolute inset-0 rounded-full bg-[radial-gradient(ellipse_at_50%_120%,rgba(0,0,0,0.06),transparent_55%)]" />
        <div
          className="absolute inset-[8%] rounded-full opacity-35 mix-blend-soft-light"
          style={{
            background:
              "repeating-conic-gradient(from 0deg, rgba(255,255,255,0.2) 0deg 3deg, transparent 3deg 7deg)",
          }}
        />
      </motion.div>

      <motion.div
        className="pointer-events-none absolute left-1/2 top-1/2 z-30 h-[88%] w-[88%] -translate-x-1/2 -translate-y-1/2"
        animate={{ rotateZ: 360 }}
        transition={{ duration: 56, repeat: Infinity, ease: "linear" }}
        aria-hidden
      >
        <div
          className="absolute inset-0 rounded-full border-[1.5px] border-neutral-950"
          style={{ transform: "rotateX(68deg) rotateY(-12deg)" }}
        />
      </motion.div>

      {variant === "screen1" && (
        <>
          <StarFour className="absolute left-[6%] top-[14%] z-40 text-white" />
          <div className="absolute right-[4%] top-[38%] z-40 h-5 w-5 rounded-full border-[1.5px] border-white" />
          <div className="absolute right-[10%] top-[22%] z-40 h-3 w-3 rounded-full bg-white" />
          <IconPlus className="absolute bottom-[12%] right-[8%] z-40 text-white" />
        </>
      )}

      {variant === "screen2" && (
        <>
          <IconHeadphones className="absolute left-[4%] top-[28%] z-40 text-white" />
          <IconPlaySm className="absolute right-[8%] top-[20%] z-40 text-white" />
          <div className="absolute bottom-[18%] left-[12%] z-40 h-2 w-2 rounded-full bg-white" />
          <StarFour className="absolute right-[6%] bottom-[24%] z-40 text-white" />
          <StarFour className="absolute left-[18%] top-[12%] z-40 scale-75 text-white" />
        </>
      )}
    </div>
  );
}
