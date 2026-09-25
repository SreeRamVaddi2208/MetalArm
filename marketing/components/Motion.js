'use client';

/**
 * The motion layer: Lenis for inertial scrolling, GSAP/ScrollTrigger for the
 * pinned and scrubbed sections.
 *
 * Three rules this file exists to enforce, because getting any of them wrong
 * is what makes a site like this unbearable rather than premium:
 *
 * 1. `prefers-reduced-motion` is checked BEFORE anything is built. Not
 *    "animate, then shorten" - no Lenis, no pins, no scrubs at all. The page is
 *    written so that state is the plain document.
 * 2. Pinning is desktop-only (>=768px). On a phone the section fills the
 *    screen, so holding it still while the content changes underneath reads as
 *    a page that has frozen. Apple's own mobile pages drop these effects; so
 *    does this one.
 * 3. The hidden state lives behind `html.ma-js`, added here. If this script
 *    never runs, every word is simply visible. Copy must never need JavaScript
 *    to be readable.
 */

import { useEffect } from 'react';

export default function Motion() {
  useEffect(() => {
    let lenis;
    let ctx;
    let raf;
    let cancelled = false;

    (async () => {
      const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      if (calm) return;  // the document, as written, is the reduced version

      const [{ default: Lenis }, { gsap }, { ScrollTrigger }] = await Promise.all([
        import('lenis'),
        import('gsap'),
        import('gsap/ScrollTrigger'),
      ]);
      if (cancelled) return;

      gsap.registerPlugin(ScrollTrigger);
      document.documentElement.classList.add('ma-js');

      lenis = new Lenis({ duration: 1.05, smoothWheel: true, syncTouch: false });
      // Lenis owns the scroll position, so ScrollTrigger has to be told when it
      // moves - otherwise every trigger fires against a stale scrollTop.
      lenis.on('scroll', ScrollTrigger.update);
      const tick = (time) => { lenis.raf(time * 1000); };
      gsap.ticker.add(tick);
      gsap.ticker.lagSmoothing(0);

      ctx = gsap.context(() => {
        // --- Staged text reveal: word by word, as the line enters ----------
        document.querySelectorAll('[data-stagger]').forEach((el) => {
          gsap.to(el.querySelectorAll('.ma-word'), {
            opacity: 1,
            y: 0,
            duration: 0.75,
            ease: 'power3.out',
            stagger: 0.045,
            scrollTrigger: { trigger: el, start: 'top 82%', once: true },
          });
        });

        // --- Everything else that simply rises into place -----------------
        document.querySelectorAll('.ma-rise').forEach((el) => {
          gsap.to(el, {
            opacity: 1,
            y: 0,
            duration: 0.7,
            ease: 'power3.out',
            scrollTrigger: { trigger: el, start: 'top 88%', once: true },
          });
        });

        if (window.innerWidth < 768) return;  // rule 2

        // --- Pinned sections: hold, while the content underneath changes ---
        document.querySelectorAll('[data-pin]').forEach((wrap) => {
          const pinned = wrap.querySelector('.ma-pin');
          const steps = [...wrap.querySelectorAll('[data-step]')];
          if (!pinned) return;

          const timeline = gsap.timeline({
            scrollTrigger: {
              trigger: wrap,
              start: 'top top',
              end: () => `+=${wrap.offsetHeight - window.innerHeight}`,
              pin: pinned,
              scrub: 0.6,
            },
          });
          steps.forEach((step, index) => {
            timeline.to(step, { opacity: 1, y: 0, duration: 1 }, index * 1.2);
            if (index < steps.length - 1) {
              timeline.to(step, { opacity: 0, y: -24, duration: 1 }, index * 1.2 + 1);
            }
          });
        });

        // --- Scroll-scrubbed video ----------------------------------------
        // The playback head follows scroll instead of a clock. Seeking is the
        // expensive part, so the position is written on GSAP's ticker via a
        // quickSetter rather than on every scroll event.
        document.querySelectorAll('[data-scrub-video]').forEach((wrap) => {
          const video = wrap.querySelector('video');
          if (!video) return;
          video.pause();
          const state = { time: 0 };
          const seek = () => {
            if (video.readyState >= 1 && Number.isFinite(video.duration)) {
              video.currentTime = Math.min(state.time * video.duration, video.duration - 0.05);
            }
          };
          gsap.to(state, {
            time: 1,
            ease: 'none',
            onUpdate: seek,
            scrollTrigger: {
              trigger: wrap,
              start: 'top top',
              end: () => `+=${wrap.offsetHeight - window.innerHeight}`,
              pin: wrap.querySelector('.ma-pin'),
              scrub: 0.4,
            },
          });
        });

        // --- Parallax, used on two elements in the whole page --------------
        document.querySelectorAll('[data-parallax]').forEach((el) => {
          gsap.to(el, {
            yPercent: Number(el.dataset.parallax),
            ease: 'none',
            scrollTrigger: { trigger: el.parentElement, start: 'top bottom', end: 'bottom top', scrub: true },
          });
        });
      });

      ScrollTrigger.refresh();
    })();

    return () => {
      cancelled = true;
      if (raf) cancelAnimationFrame(raf);
      ctx?.revert();
      lenis?.destroy();
      document.documentElement.classList.remove('ma-js');
    };
  }, []);

  return null;
}
