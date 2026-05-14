"use client";

import { useRef, useState } from "react";
import { AnimatePresence } from "framer-motion";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { BackgroundRipples, IridescentBlob } from "./Background";
import { Header } from "./Header";
import { HeroOrbVisual } from "./HeroOrbVisual";
import { LoadingScreen } from "./LoadingScreen";
import { MusicDevice } from "./MusicDevice";
import { Track01Orbit } from "./Track01Orbit";

gsap.registerPlugin(ScrollTrigger);

const screen1Body =
  "Explore how Celerix Ai brings together job auto-apply, deep research, and scientific paper support—so you ship real work faster without sacrificing quality.";

function CloverIcon({ className }: { className?: string }) {
  return (
    <svg className={className} width="14" height="14" viewBox="0 0 14 14" fill="currentColor" aria-hidden>
      <circle cx="7" cy="3" r="2.2" />
      <circle cx="11" cy="7" r="2.2" />
      <circle cx="7" cy="11" r="2.2" />
      <circle cx="3" cy="7" r="2.2" />
    </svg>
  );
}

function PartnerMark({ letter }: { letter: string }) {
  return (
    <span className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-neutral-700 bg-neutral-900 text-[11px] font-semibold text-neutral-200 shadow-sm">
      {letter}
    </span>
  );
}

export function PhotoLanding() {
  const [isLoaded, setIsLoaded] = useState(false);
  const [currentAgentIndex, setCurrentAgentIndex] = useState(0);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const heroOrbRef = useRef<HTMLDivElement>(null);
  const h1Ref = useRef<HTMLHeadingElement>(null);
  const pRef = useRef<HTMLParagraphElement>(null);
  const buttonRef = useRef<HTMLDivElement>(null);
  const h2Ref = useRef<HTMLHeadingElement>(null);
  const orb2Ref = useRef<HTMLDivElement>(null);
  const heroVisualRef = useRef<HTMLDivElement>(null);

  useGSAP(() => {
    // Parallax hero orb
    gsap.to(heroOrbRef.current, {
      y: -48,
      ease: "none",
      scrollTrigger: {
        trigger: document.body,
        start: "top top",
        end: "12% top",
        scrub: true,
      }
    });

    // Intro elements timeline
    const tl = gsap.timeline({ delay: 0.1 });
    
    tl.from(heroVisualRef.current, { opacity: 0, scale: 0.96, duration: 0.7, ease: "power2.out" })
      .from(h1Ref.current, { opacity: 0, y: 22, duration: 0.65, ease: "power2.out" }, "-=0.5")
      .from(pRef.current, { opacity: 0, y: 16, duration: 0.6, ease: "power2.out" }, "-=0.4")
      .from(buttonRef.current, { opacity: 0, y: 14, duration: 0.55, ease: "power2.out" }, "-=0.4");

    // Screen 2 elements
    gsap.from(h2Ref.current, {
      opacity: 0,
      y: 24,
      duration: 0.7,
      ease: "power2.out",
      scrollTrigger: {
        trigger: h2Ref.current,
        start: "top 80%",
      }
    });

    gsap.from(orb2Ref.current, {
      opacity: 0,
      scale: 0.94,
      duration: 0.65,
      ease: "power2.out",
      scrollTrigger: {
        trigger: orb2Ref.current,
        start: "top 85%",
      }
    });
  }, { scope: containerRef });

  return (
    <div ref={containerRef} className="bg-[#0a0a0a] text-neutral-100">
      {/* Loading screen overlay */}
      <AnimatePresence>
        {!isLoaded && (
          <LoadingScreen key="loader" onComplete={() => setIsLoaded(true)} />
        )}
      </AnimatePresence>

      <Header logoVisible={isLoaded} />

      {/* Screen 1 */}
      <section className="relative flex min-h-[100dvh] flex-col bg-[radial-gradient(circle_at_50%_38%,rgba(255,255,255,0.05)_0%,transparent_52%)] px-5 pb-6 pt-24 md:px-10">
        <div className="flex flex-1 flex-col items-center justify-center gap-8 md:gap-10">
          <div ref={heroOrbRef} className="pointer-events-none absolute inset-0 flex items-center justify-center">
            <IridescentBlob size={420} blur={56} delay={0} className="opacity-90" />
          </div>

          <div ref={heroVisualRef}>
            <HeroOrbVisual variant="screen1" />
          </div>

          <h1
            ref={h1Ref}
            className="relative z-10 max-w-4xl text-center font-[family-name:var(--font-anton)] text-[clamp(2rem,6.2vw,3.75rem)] font-normal uppercase leading-[0.95] tracking-[-0.02em] text-white"
          >
            The new way to work with AI agents
          </h1>

          <p
            ref={pRef}
            className="relative z-10 max-w-lg text-center text-[14px] leading-relaxed text-neutral-400 md:text-[15px]"
          >
            {screen1Body}
          </p>

          <div ref={buttonRef}>
            <a
              href="#early-access"
              className="inline-block rounded-md bg-[#ccff00] px-7 py-3.5 text-[12px] font-bold uppercase tracking-wide text-neutral-900 shadow-sm transition hover:brightness-105 active:scale-[0.98]"
            >
              Get early access
            </a>
          </div>
        </div>

        <footer className="mt-auto flex flex-col gap-4 border-t border-neutral-800/80 pt-6 text-[9px] font-medium uppercase leading-snug tracking-[0.12em] text-neutral-500 md:flex-row md:items-end md:justify-between md:gap-6 md:pt-8">
          <p className="max-w-md uppercase md:max-w-[55%]">Celerix Ai · All rights reserved</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 md:justify-end">
            <a href="#" className="transition hover:text-neutral-300">
              Terms &amp; conditions
            </a>
            <a href="#" className="transition hover:text-neutral-300">
              Privacy policy
            </a>
            <CloverIcon className="shrink-0 text-neutral-500" />
          </div>
        </footer>
      </section>

      {/* Screen 2 */}
      <section className="relative flex min-h-[100dvh] flex-col bg-[radial-gradient(circle_at_50%_42%,rgba(255,255,255,0.05)_0%,transparent_50%)] px-5 pt-24 pb-8 md:px-10">
        <div className="flex flex-1 flex-col items-center justify-center py-6">
          <div className="relative flex w-full max-w-[1200px] flex-col items-center justify-center py-4 md:min-h-[52vh]">
            <h2
              ref={h2Ref}
              className="pointer-events-none absolute left-1/2 top-1/2 z-[1] w-[104%] max-w-none -translate-x-1/2 -translate-y-1/2 px-1 text-center font-[family-name:var(--font-anton)] text-[clamp(2.6rem,11vw,8.25rem)] font-normal uppercase leading-[0.82] tracking-[-0.03em] text-[#bfff00] md:w-full"
            >
              <span className="block">Turn your tasks into</span>
              <span className="block">Shipped work</span>
            </h2>

            <div className="relative z-[2] mt-4 md:mt-0">
              <div ref={orb2Ref}>
                <HeroOrbVisual variant="screen2" />
              </div>
            </div>
          </div>
        </div>

        <footer className="mt-auto flex flex-col justify-between gap-6 border-t border-neutral-800/80 pt-8 text-[12px] leading-relaxed text-neutral-400 md:flex-row md:items-end md:gap-12">
          <p className="max-w-md">
            Explore Celerix Ai: three agents for applications, research, and papers—run from one calm workspace.
          </p>
          <div className="flex flex-col items-start gap-3 md:items-end">
            <p className="text-right md:text-right">Works alongside your favorite tools</p>
            <div className="flex gap-2">
              <PartnerMark letter="C" />
              <PartnerMark letter="+" />
            </div>
          </div>
        </footer>
      </section>

      {/* Screen 3 — device + orbit */}
      <section
        id="early-access"
        className="relative flex min-h-[100dvh] items-center overflow-hidden bg-[#0f0f0f] px-5 py-24 md:px-10 md:py-32"
      >
        <BackgroundRipples />
        <IridescentBlob size={90} blur={18} delay={0} className="left-[4%] top-[12%] opacity-80" />
        <IridescentBlob size={64} blur={14} delay={2} className="right-[8%] top-[20%] opacity-75" />
        <IridescentBlob size={52} blur={12} delay={4} className="bottom-[18%] left-[12%] opacity-70" />
        <IridescentBlob size={76} blur={16} delay={1} className="bottom-[10%] right-[6%] opacity-72" />

        <div className="relative z-10 mx-auto flex max-w-5xl flex-col items-center justify-center gap-16 md:flex-row md:items-center md:gap-20 lg:gap-28">
          <MusicDevice
            className="md:justify-self-center"
            activeIndex={currentAgentIndex}
            onChange={setCurrentAgentIndex}
          />
          <Track01Orbit activeIndex={currentAgentIndex} />
        </div>
      </section>
    </div>
  );
}
