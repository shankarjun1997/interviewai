import { type HTMLAttributes } from "react";
import { cn } from "../../lib/cn";

type Tone = "error" | "info" | "success";

const tones: Record<Tone, string> = {
  error: "border-red-500/30 bg-red-500/10 text-red-300",
  info: "border-blue-500/30 bg-blue-500/10 text-blue-200",
  success: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone;
}

export function Alert({ tone = "info", className, children, ...rest }: AlertProps) {
  if (!children) return null;
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn("rounded-lg border px-4 py-3 text-sm", tones[tone], className)}
      {...rest}
    >
      {children}
    </div>
  );
}
