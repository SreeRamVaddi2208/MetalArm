'use client';

/**
 * The one network call this site makes: POST /waitlist to the MetalArm API.
 *
 * The API answers the same way whether the address is new or already on the
 * list, so this component does too - anything else would let the form be used
 * to test whether somebody had signed up.
 */

import { useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Waitlist({ source = 'cta' }) {
  const [email, setEmail] = useState('');
  const [state, setState] = useState('idle');  // idle | sending | done | error
  const [message, setMessage] = useState('');

  async function submit(event) {
    event.preventDefault();
    if (!email.trim()) return;
    setState('sending');
    try {
      const response = await fetch(`${API}/waitlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), source }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setMessage(body.detail || 'That did not go through. Try again in a moment.');
        setState('error');
        return;
      }
      const body = await response.json();
      setMessage(body.message || "You're on the list.");
      setState('done');
    } catch {
      setMessage('Could not reach MetalArm. Check your connection and try again.');
      setState('error');
    }
  }

  if (state === 'done') {
    return (
      <p className="font-display text-lg text-accent" role="status">
        {message}
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="w-full max-w-md">
      <div className="flex flex-col gap-3 sm:flex-row">
        <label className="sr-only" htmlFor="waitlist-email">Email address</label>
        <input
          id="waitlist-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="flex-1 rounded-xl border border-border bg-field px-4 py-3 text-text
                     outline-none transition-colors focus:border-accent"
        />
        <button
          type="submit"
          disabled={state === 'sending'}
          className="rounded-xl bg-accent px-6 py-3 font-display text-sm font-bold tracking-widest
                     text-bg transition-transform duration-200 ease-out
                     hover:scale-[1.03] active:scale-[0.99] disabled:opacity-60"
        >
          {state === 'sending' ? 'SENDING' : 'JOIN THE WAITLIST'}
        </button>
      </div>
      {state === 'error' && (
        <p className="mt-3 text-sm text-[#e5484d]" role="alert">{message}</p>
      )}
    </form>
  );
}
