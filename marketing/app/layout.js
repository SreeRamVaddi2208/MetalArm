import { Space_Grotesk, Manrope } from 'next/font/google';
import './globals.css';

// The app's own type pairing (ios/MetalARM Theme.display / Theme.body):
// Space Grotesk for headings and numbers, Manrope for prose.
const spaceGrotesk = Space_Grotesk({
  subsets: ['latin'],
  weight: ['500', '700'],
  variable: '--font-space-grotesk',
  display: 'swap',
});
const manrope = Manrope({
  subsets: ['latin'],
  weight: ['400', '600', '800'],
  variable: '--font-manrope',
  display: 'swap',
});

export const metadata = {
  title: 'MetalArm - the gym is the game',
  description:
    'A workout tracker where the training IS the game: points on every set, '
    + 'ranks you can lose, duels, and a party that sees what you lifted.',
};

export const viewport = { themeColor: '#0b0b0c' };

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${spaceGrotesk.variable} ${manrope.variable}`}>
      <body className="bg-bg text-text">{children}</body>
    </html>
  );
}
