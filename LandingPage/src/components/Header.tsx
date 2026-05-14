"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { CenterStar } from "./icons";

interface HeaderProps {
  logoVisible?: boolean;
}

export function Header({ logoVisible = true }: HeaderProps) {
  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
      className="pointer-events-none fixed inset-x-0 top-0 z-50 grid grid-cols-3 items-center px-6 py-6 md:px-10 md:py-8"
    >
      <motion.div
        className="pointer-events-auto flex items-center gap-2 justify-self-start text-[15px] font-semibold tracking-tight text-neutral-100"
        initial={{ opacity: 0, x: -12 }}
        animate={logoVisible ? { opacity: 1, x: 0 } : { opacity: 0, x: -12 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      >
        <Image src="/celerix-hex-mark.png" alt="Celerix Logo" width={22} height={22} className="object-contain invert" />
        <span>CelerixAi</span>
      </motion.div>
      <div className="pointer-events-auto flex justify-center justify-self-center">
        <CenterStar className="text-neutral-300" />
      </div>
      <a
        href="#early-access"
        className="pointer-events-auto justify-self-end text-[11px] font-medium uppercase tracking-[0.22em] text-neutral-100 underline-offset-4 transition hover:underline"
      >
        Get early access
      </a>
    </motion.header>
  );
}
