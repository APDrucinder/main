"use client";

import { motion, AnimatePresence } from "framer-motion";

const pillBase =
  "rounded-full bg-white px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-900 shadow-lg";

const orbitLabels = [
  { label: "Job apply", className: "left-1/2 top-0 -translate-x-1/2 -translate-y-1/2" },
  { label: "Research", className: "right-0 top-1/2 -translate-y-1/2 translate-x-[42%]" },
  { label: "Papers", className: "left-1/2 bottom-0 -translate-x-1/2 translate-y-1/2" },
  { label: "Workflow", className: "left-0 top-1/2 -translate-x-[42%] -translate-y-1/2" },
] as const;

const agentOneHref =
  process.env.NEXT_PUBLIC_AGENT_ONE_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:3001/dashboard" : "/dashboard");

const agentVisuals = [
  {
    label: "Agent 01",
    gradient: "conic-gradient(from 130deg, #f9c8ff, #c8e8ff, #fff6c8, #f0e8ff, #f9c8ff)",
    glow: "#bfff00",
    href: agentOneHref,
  },
  {
    label: "Agent 02",
    gradient: "conic-gradient(from 130deg, #c8e8ff, #f9c8ff, #e8ffc8, #c8e8ff)",
    glow: "#00e5ff",
    href: "#",
  },
  {
    label: "Agent 03",
    gradient: "conic-gradient(from 130deg, #fff6c8, #f9c8ff, #c8e8ff, #fff6c8)",
    glow: "#ff00e5",
    href: "#",
  },
];

interface Track01OrbitProps {
  className?: string;
  activeIndex: number;
}

export function Track01Orbit({ className, activeIndex }: Track01OrbitProps) {
  const currentVisual = agentVisuals[activeIndex % agentVisuals.length];

  return (
    <motion.div
      className={`relative flex h-[min(82vw,320px)] w-[min(82vw,320px)] shrink-0 items-center justify-center ${className ?? ""}`}
      initial={{ opacity: 0, scale: 0.94 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Rotating orbit container */}
      <motion.div 
        className="absolute inset-0 z-0 pointer-events-none"
        animate={{ rotate: -activeIndex * 90 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      >
        <div className="absolute inset-0 rounded-full border border-neutral-700/90 shadow-[0_0_0_1px_rgba(0,0,0,0.65)_inset]" />
        <div className="absolute inset-[10px] rounded-full border border-neutral-700/70" />
        <div className="absolute inset-[22px] rounded-full border border-dashed border-neutral-800/90" />

        {orbitLabels.map(({ label, className: pos }, i) => (
          <div key={label} className={`absolute ${pos} z-10 pointer-events-auto`}>
            <motion.div
              className={`${pillBase} flex items-center justify-center whitespace-nowrap`}
              animate={{ 
                rotate: activeIndex * 90,
                opacity: (activeIndex === 0 && i === 0) || (activeIndex === 1 && i === 1) || (activeIndex === 2 && i === 2) || (activeIndex === 0 && i === 3) ? 1 : 0.4
              }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            >
              {label}
            </motion.div>
          </div>
        ))}
      </motion.div>

      <motion.div
        className="relative z-10 flex h-[54%] w-[54%] items-center justify-center rounded-full transition-all duration-700"
        animate={{ 
          y: [0, -6, 0],
          background: currentVisual.gradient,
          boxShadow: `0 20px 50px -18px rgba(0,0,0,0.22), 0 0 20px ${currentVisual.glow}33`,
        }}
        transition={{ 
          y: { duration: 5, repeat: Infinity, ease: "easeInOut" },
          background: { duration: 0.8 },
        }}
        whileHover={{ scale: 1.03 }}
      >
        <div className="absolute inset-2 rounded-full bg-white/10 blur-xl" />
        
        <AnimatePresence mode="wait">
          <motion.a
            href={currentVisual.href}
            key={currentVisual.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 1.1 }}
            className="relative z-10 flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-neutral-900 shadow-md cursor-pointer"
          >
            <span className="text-[8px]" aria-hidden>
              ▶
            </span>{" "}
            {currentVisual.label}
          </motion.a>
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
