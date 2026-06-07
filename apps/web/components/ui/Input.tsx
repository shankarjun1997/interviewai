"use client";

import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

const base =
  "w-full rounded-lg border border-neutral-800 bg-neutral-950/60 px-3.5 py-2.5 text-sm text-neutral-100 " +
  "placeholder:text-neutral-500 transition-colors focus:border-emerald-500/70 focus:outline-none " +
  "focus:ring-2 focus:ring-emerald-500/20 disabled:opacity-50";

export interface FieldProps {
  label?: string;
  hint?: string;
}

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement> & FieldProps
>(function Input({ label, hint, id, className, ...rest }, ref) {
  return (
    <label className="block space-y-1.5" htmlFor={id}>
      {label && <span className="text-xs font-medium text-neutral-400">{label}</span>}
      <input ref={ref} id={id} className={cn(base, className)} {...rest} />
      {hint && <span className="block text-xs text-neutral-500">{hint}</span>}
    </label>
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps
>(function Textarea({ label, hint, id, className, ...rest }, ref) {
  return (
    <label className="block space-y-1.5" htmlFor={id}>
      {label && <span className="text-xs font-medium text-neutral-400">{label}</span>}
      <textarea ref={ref} id={id} className={cn(base, "min-h-[7rem] resize-y", className)} {...rest} />
      {hint && <span className="block text-xs text-neutral-500">{hint}</span>}
    </label>
  );
});
