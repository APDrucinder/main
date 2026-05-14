"use client";

import { AnimatePresence, motion } from "framer-motion";
import { IconNext, IconPause, IconPrev } from "./icons";
import { CharcoalOrb } from "./Background";

const agents = [
  {
    id: "job",
    index: "01/03",
    title: "Job agent:",
    body: "Auto-apply to roles that fit your profile—tailored resumes, batch submissions, and follow-ups without living in forms.",
    color: "#bfff00",
  },
  {
    id: "research",
    index: "02/03",
    title: "Research Agent:",
    body: "Deep-dive into any topic. Summarize papers, extract data, and find connections across thousands of sources instantly.",
    color: "#00e5ff",
  },
  {
    id: "writer",
    index: "03/03",
    title: "Paper Writer:",
    body: "Draft high-quality scientific papers and reports. Citation-ready, formatted correctly, and aligned with your research data.",
    color: "#ff00e5",
  },
];

interface MusicDeviceProps {
  className?: string;
  activeIndex: number;
  onChange: (index: number) => void;
}

export function MusicDevice({ className, activeIndex, onChange }: MusicDeviceProps) {
  const handlePrev = () => {
    onChange((activeIndex - 1 + agents.length) % agents.length);
  };

  const handleNext = () => {
    onChange((activeIndex + 1) % agents.length);
  };

  const currentAgent = agents[activeIndex];

  return (
    <motion.div
      layout
      className={`relative flex justify-center ${className ?? ""}`}
      initial={{ opacity: 0, y: 24, scale: 0.98 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Side buttons (decorative) */}
      <div className="pointer-events-none absolute left-[-10px] top-[26%] flex flex-col gap-2.5">
        <div className="h-6 w-2 rounded-full bg-neutral-200 shadow-sm" />
        <div className="h-6 w-2 rounded-full bg-neutral-200 shadow-sm" />
        <div className="h-6 w-2 rounded-full bg-neutral-200 shadow-sm" />
      </div>
      <div className="pointer-events-none absolute right-[-10px] top-[20%] flex flex-col gap-14">
        <div className="h-6 w-2 rounded-full bg-neutral-200 shadow-sm" />
        <motion.div 
          animate={{ backgroundColor: currentAgent.color }}
          className="h-8 w-2 rounded-full shadow-[0_0_0_1px_rgba(0,0,0,0.06)]" 
        />
      </div>

      {/* Cards Stack */}
      <div className="grid w-[min(100%,280px)]">
        {agents.map((agent, index) => {
          const isCurrent = index === activeIndex;
          // Calculate depth: 0 is current, 1 is next in stack (behind), 2 is last
          const depth = (index - activeIndex + agents.length) % agents.length;
          
          let positionState = "active";
          if (depth === 1) positionState = "right";
          if (depth === 2) positionState = "left";

          const variants = {
            active: {
              x: 0,
              y: 0,
              scale: 1,
              opacity: 1,
              filter: "blur(0px)",
              zIndex: 10,
              rotate: 0,
            },
            right: {
              x: 130,
              y: 16,
              scale: 0.85,
              opacity: 0.5,
              filter: "blur(1.5px)",
              zIndex: 5,
              rotate: 4,
            },
            left: {
              x: -130,
              y: 16,
              scale: 0.85,
              opacity: 0.5,
              filter: "blur(1.5px)",
              zIndex: 5,
              rotate: -4,
            }
          };

          return (
            <motion.div
              key={agent.id}
              style={{ gridArea: "1 / 1" }}
              onClick={() => !isCurrent && onChange(index)}
              animate={variants[positionState as keyof typeof variants]}
              transition={{ type: "spring", stiffness: 180, damping: 22, mass: 0.8 }}
              className={`relative rounded-[28px] bg-neutral-900 p-3 ring-1 ring-white/5 ${
                depth === 0 ? "shadow-[0_28px_60px_-20px_rgba(0,0,0,0.5),0_0_0_1px_rgba(255,255,255,0.08)_inset]" : ""
              } ${!isCurrent ? "cursor-pointer" : "hover:scale-[1.01] transition-transform"}`}
            >
              <div className="overflow-hidden rounded-[22px] bg-neutral-950 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05)]">
                <div className="relative min-h-[340px] bg-gradient-to-b from-neutral-900 to-neutral-950 px-5 pb-6 pt-4">
                  <div className="mb-4 flex items-start justify-between">
                    <span 
                      style={{ backgroundColor: agent.color }}
                      className="rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-900 transition-colors duration-500"
                    >
                      AI
                    </span>
                    <span className="text-[11px] font-medium tabular-nums text-neutral-500">
                      {agent.index}
                    </span>
                  </div>

                  <div className="flex flex-col items-center">
                    <div className="flex w-full flex-col items-center">
                      <CharcoalOrb className="h-[120px] w-[120px]" text={agent.id} color={agent.color} />
                      <p className="mt-5 w-full text-left text-[13px] font-semibold text-neutral-100">{agent.title}</p>
                      <p className="mt-1 text-left text-[12px] leading-relaxed text-neutral-400">{agent.body}</p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-[repeat(14,1fr)] gap-x-1 gap-y-1.5 border-t border-neutral-800/80 bg-neutral-900/50 px-5 py-6">
                  {Array.from({ length: 14 * 4 }).map((_, i) => (
                    <span key={`${agent.id}-${i}`} className="mx-auto block h-1 w-1 rounded-full bg-neutral-600/90" />
                  ))}
                </div>
              </div>
            </motion.div>
          );
        })}
      </div>
    </motion.div>
  );
}
