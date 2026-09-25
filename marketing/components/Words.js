/**
 * Splits a headline into per-word spans so the reveal can stage them.
 *
 * Done on the server, in the markup, rather than by walking the DOM on the
 * client: the words are in the HTML either way, so the copy is readable and
 * indexable with JavaScript off, and there is no re-layout on hydration.
 */
export default function Words({ text, className = '' }) {
  return (
    <span className={className} data-stagger="">
      {text.split(' ').map((word, i) => (
        <span key={`${word}-${i}`} className="ma-word">
          {word}
          {i < text.split(' ').length - 1 ? ' ' : ''}
        </span>
      ))}
    </span>
  );
}
