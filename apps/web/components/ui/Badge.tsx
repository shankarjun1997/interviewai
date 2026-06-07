import { type HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Tone = "emerald" | "neutral" | "amber" | "red" | "blue";

const tones: Record<Tone, string> = {
  emerald: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  neutral: "bg-neutral-700/30 text-neutral-300 border-neutral-600/40",
  amber: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  red: "bg-red-500/10 text-red-300 border-red-500/30",
  blue: "bg-blue-500/10 text-blue-300 border-blue-500/30",
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ tone = "neutral", className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        tones[tone],
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  );
}
