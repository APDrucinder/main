"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import Image from "next/image";

interface LoadingScreenProps {
  onComplete: () => void;
}

export function LoadingScreen({ onComplete }: LoadingScreenProps) {
  const [phase, setPhase] = useState<"enter" | "exit">("enter");

  useEffect(() => {
    const timer = setTimeout(() => setPhase("exit"), 2400);
    return () => clearTimeout(timer);
  }, []);

  return (
    <motion.div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 100,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#0a0a0a",
      }}
      animate={phase === "exit" ? { opacity: 0 } : { opacity: 1 }}
      transition={{
        duration: 0.5,
        delay: phase === "exit" ? 0.55 : 0,
        ease: [0.22, 1, 0.36, 1],
      }}
      onAnimationComplete={() => {
        if (phase === "exit") onComplete();
      }}
    >
      {/* Pulsing glow behind logo */}
      <motion.div
        style={{
          position: "absolute",
          width: 260,
          height: 260,
          borderRadius: "50%",
          background:
            "radial-gradient(circle, rgba(204,255,0,0.18) 0%, rgba(204,255,0,0.04) 50%, transparent 70%)",
          pointerEvents: "none",
        }}
        animate={
          phase === "exit"
            ? { scale: 0.3, opacity: 0 }
            : {
              scale: [1, 1.15, 1],
              opacity: [0.6, 1, 0.6],
            }
        }
        transition={
          phase === "exit"
            ? { duration: 0.6, ease: [0.65, 0, 0.35, 1] }
            : { duration: 2.4, repeat: Infinity, ease: "easeInOut" }
        }
      />

      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, scale: 0.82 }}
        animate={
          phase === "exit"
            ? {
              scale: 0.32,
              y: "calc(-50vh + 38px)",
              x: "calc(-50vw + 90px)",
              opacity: 0,
            }
            : { opacity: 1, scale: 1, x: 0, y: 0 }
        }
        transition={
          phase === "exit"
            ? { duration: 0.75, ease: [0.65, 0, 0.35, 1] }
            : { duration: 0.55, ease: [0.22, 1, 0.36, 1] }
        }
      >
        <Image
          src="/celerix-logo-transparent.png"
          alt="CelerixAi"
          width={240}
          height={72}
          priority
          draggable={false}
          style={{ userSelect: "none", filter: "invert(1)" }}
        />
      </motion.div>

      {/* Progress bar */}
      <motion.div
        style={{
          position: "absolute",
          bottom: "18%",
          width: 140,
          height: 2,
          borderRadius: 2,
          backgroundColor: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
        animate={phase === "exit" ? { opacity: 0, y: 8 } : { opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <motion.div
          style={{
            height: "100%",
            backgroundColor: "#ffffff",
            borderRadius: 2,
            transformOrigin: "left",
          }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 2.2, ease: [0.4, 0, 0.2, 1] }}
        />
      </motion.div>

      {/* Subtle tagline */}
      <motion.p
        style={{
          position: "absolute",
          bottom: "22%",
          fontSize: 11,
          fontWeight: 500,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: "rgba(255,255,255,0.3)",
        }}
        initial={{ opacity: 0 }}
        animate={phase === "exit" ? { opacity: 0, y: 6 } : { opacity: 1 }}
        transition={{
          duration: 0.4,
          delay: phase === "exit" ? 0 : 0.6,
        }}
      >
        AI agents for work
      </motion.p>
    </motion.div>
  );
}
