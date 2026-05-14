"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { ArrowRight, Lock, Mail } from "lucide-react";
import { login, type LoginState } from "@/app/actions/auth";

const initialState: LoginState = {};

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      className="h-12 w-full rounded-xl bg-white px-5 text-sm font-bold text-black shadow-[0_0_22px_rgba(255,255,255,0.08)] transition hover:bg-zinc-200 disabled:cursor-not-allowed disabled:opacity-70"
    >
      <span className="flex items-center justify-center gap-2">
        {pending ? "Signing in" : "Sign in"}
        <ArrowRight className="h-4 w-4" />
      </span>
    </button>
  );
}

export function LoginForm() {
  const [state, formAction] = useActionState(login, initialState);

  return (
    <form action={formAction} className="space-y-5">
      <div className="space-y-2">
        <label htmlFor="email" className="text-xs font-semibold uppercase text-white/50">
          Email
        </label>
        <div className="flex h-12 items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-4 transition focus-within:border-white/40">
          <Mail className="h-4 w-4 text-white/40" />
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/30"
            placeholder="you@example.com"
          />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="password" className="text-xs font-semibold uppercase text-white/50">
          Password
        </label>
        <div className="flex h-12 items-center gap-3 rounded-xl border border-white/10 bg-white/[0.04] px-4 transition focus-within:border-white/40">
          <Lock className="h-4 w-4 text-white/40" />
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="h-full min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/30"
            placeholder="Enter your password"
          />
        </div>
      </div>

      {state.error ? (
        <p className="rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {state.error}
        </p>
      ) : null}

      <SubmitButton />
    </form>
  );
}
