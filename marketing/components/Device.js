/**
 * A phone frame around a real capture.
 *
 * The captures ARE phone recordings (the tour is an iPhone 17 Pro Max at 9:41
 * with a full status bar), so the frame is there to say "this is software on a
 * device" rather than to fake one. `tilt` opts an individual frame into the
 * scroll-driven 3D tilt; it is off by default because every frame tilting at
 * once reads as a gimmick.
 */
export default function Device({ tilt = false, className = '', children }) {
  return (
    <div className={`[perspective:1400px] ${className}`}>
      <div
        {...(tilt ? { 'data-tilt': '' } : {})}
        className="overflow-hidden rounded-[2.2rem] border border-border bg-panel p-1.5
                   shadow-[0_30px_80px_-20px_rgba(0,0,0,0.9)] will-change-transform"
      >
        <div className="relative overflow-hidden rounded-[1.8rem]">{children}</div>
      </div>
    </div>
  );
}

/** A capture that plays on its own: short loops that carry a single beat. */
export function Loop({ src, poster, className = '', ...rest }) {
  return (
    <video
      src={src}
      poster={poster}
      muted
      playsInline
      loop
      autoPlay
      preload="none"
      className={`w-full ${className}`}
      {...rest}
    />
  );
}

/** A capture whose playback head follows the scroll instead of a clock. */
export function Scrubbed({ src, poster, className = '' }) {
  return (
    <video
      src={src}
      poster={poster}
      muted
      playsInline
      preload="auto"
      className={`w-full ${className}`}
    />
  );
}
