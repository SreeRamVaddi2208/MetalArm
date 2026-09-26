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

      // 0.9 rather than the default 1.2: long enough to feel inertial, short
      // enough that the page stops when the wheel does. Touch is left alone -
      // a phone's own scrolling is already better than anything layered on it.
      lenis = new Lenis({ duration: 0.9, smoothWheel: true, syncTouch: false });
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

        // --- Screen-to-screen morph ---------------------------------------
        // One pinned frame, three captures cross-fading in the app's real
        // navigation order. Separate videos rather than one long clip so each
        // can be a short loop that carries its own beat, and so a slow
        // connection shows the poster of the screen it is on rather than a
        // black rectangle mid-seek.
        document.querySelectorAll('[data-morph]').forEach((wrap) => {
          const screens = [...wrap.querySelectorAll('[data-screen]')];
          if (screens.length < 2) return;
          const timeline = gsap.timeline({
            scrollTrigger: {
              trigger: wrap,
              start: 'top top',
              end: () => `+=${wrap.offsetHeight - window.innerHeight}`,
              pin: wrap.querySelector('.ma-pin'),
              scrub: 0.6,
            },
          });
          screens.forEach((screen, i) => {
            if (i === 0) return;
            timeline.to(screens[i - 1], { opacity: 0, scale: 0.97, duration: 1 }, i);
            timeline.fromTo(screen, { opacity: 0, scale: 1.03 },
                            { opacity: 1, scale: 1, duration: 1 }, i);
          });
        });

        // --- Numbers counting up ------------------------------------------
        // The values are real, captured ones (see Sections.js). Counting to a
        // number somebody actually lifted is the whole reason this technique
        // is not tacky here.
        document.querySelectorAll('[data-count-to]').forEach((el) => {
          const target = Number(el.dataset.countTo);
          const decimals = (el.dataset.countTo.split('.')[1] || '').length;
          const state = { value: 0 };
          gsap.to(state, {
            value: target,
            duration: 1.4,
            ease: 'power2.out',
            // Zeroed here rather than in the markup: the number has to be
            // correct for anyone this animation never runs for.
            onStart: () => { el.textContent = (0).toFixed(decimals); },
            onUpdate: () => { el.textContent = state.value.toFixed(decimals); },
            onComplete: () => { el.textContent = target.toFixed(decimals); },
            scrollTrigger: { trigger: el, start: 'top 88%', once: true },
          });
        });

        // --- The chart drawing itself -------------------------------------
        document.querySelectorAll('[data-chart-line]').forEach((line) => {
          const length = line.getTotalLength();
          const figure = line.closest('figure');
          gsap.set(line, { strokeDasharray: length, strokeDashoffset: length });
          gsap.set(figure.querySelectorAll('[data-chart-dot]'), { opacity: 0 });
          gsap.set(figure.querySelector('[data-chart-area]'), { opacity: 0 });
          gsap.timeline({ scrollTrigger: { trigger: figure, start: 'top 78%', once: true } })
            .to(line, { strokeDashoffset: 0, duration: 1.6, ease: 'power2.inOut' })
            .to(figure.querySelector('[data-chart-area]'), { opacity: 1, duration: 0.6 }, 0.6)
            .to(figure.querySelectorAll('[data-chart-dot]'),
                { opacity: 1, duration: 0.3, stagger: 0.18 }, 0.5);
        });

        // --- Device tilt ---------------------------------------------------
        // A few degrees, driven by how far up the viewport the frame has come.
        // Enough to read as an object with depth; not enough to be noticed.
        document.querySelectorAll('[data-tilt]').forEach((el) => {
          gsap.fromTo(el, { rotateX: 9, rotateY: -7 }, {
            rotateX: -4,
            rotateY: 4,
            ease: 'none',
            scrollTrigger: { trigger: el, start: 'top bottom', end: 'bottom top', scrub: 0.8 },
          });
        });

        // --- Headline masked over the footage beneath it -------------------
        document.querySelectorAll('[data-mask-reveal]').forEach((el) => {
          gsap.fromTo(el, { clipPath: 'inset(0 100% 0 0)' }, {
            clipPath: 'inset(0 0% 0 0)',
            duration: 1.1,
            ease: 'power3.out',
            scrollTrigger: { trigger: el, start: 'top 82%', once: true },
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
