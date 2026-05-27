﻿"use client";

import { useEffect, useRef, useLayoutEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ExperimentResult } from "@/lib/api";
import CountUp from "./CountUp";

function TerminalLog({ lines, running }: { lines: { kind: string; text: string }[]; running: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [lines]);
  return (
    <div className="rounded-lg bg-[#070A12] border border-ink-700/70 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-ink-850/80 border-b border-ink-700/50">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-[#FF5F57]/70" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#FEBC2E]/70" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#28C840]/70" />
        </div>
        <div className="font-mono text-[10px] text-ink-500">train.log / tail -f</div>
        <span className={`dot bg-accent-blue ${running ? "pulse-dot" : ""}`} />
      </div>
      <div ref={ref} className="px-3 py-2 font-mono text-[11px] leading-relaxed no-scrollbar overflow-y-auto" style={{ height: 200 }}>
        {lines.length === 0 && running && (
          <div className="text-ink-500 italic">Waiting for sandbox to start...</div>
        )}
        {lines.map((l, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-ink-600 select-none w-7 text-right shrink-0">{String(i + 1).padStart(3, "0")}</span>
            <span className="text-ink-600 select-none">›</span>
            <span className={l.kind === "err" ? "text-accent-rose" : l.kind === "ok" ? "text-accent-emerald" : l.kind === "warn" ? "text-accent-amber" : "text-ink-400"}>{l.text}</span>
          </div>
        ))}
        {running && lines.length > 0 && (
          <div className="flex gap-2 mt-0.5">
            <span className="text-ink-600 select-none w-7 text-right shrink-0">{String(lines.length + 1).padStart(3, "0")}</span>
            <span className="text-ink-600 select-none">›</span>
            <span className="blink inline-block w-2 h-3.5 bg-accent-blue align-middle" />
          </div>
        )}
      </div>
    </div>
  );
}

function parseLogLines(stdout: string, fixHistory: ExperimentResult["fix_history"]) {
  const lines = stdout ? stdout.split("\n").filter(Boolean).map(t => {
    const kind = t.includes("Error") || t.includes("ERROR") || t.includes("Traceback") ? "err"
      : t.includes("Warning") || t.includes("WARN") || t.includes("autofix") ? "warn"
      : t.includes("roc_auc") || t.includes("r2_score") || t.includes("done") || t.includes("[ok]") ? "ok"
      : "log";
    return { kind, text: t.slice(0, 120) };
  }) : [];

  const retryLines = fixHistory.map(f => ({
    kind: "warn" as const,
    text: `[autofix] retry #${f.retry} - ${f.failure_type}: ${f.fix_applied?.slice(0, 80) || ""}`,
  }));

  return [...retryLines, ...lines];
}

function CircularProgress({ value, total = 3, color = "#3B82F6" }: { value: number; total?: number; color?: string }) {
  const size = 44, stroke = 4;
  const r = (size - stroke) / 2, c = 2 * Math.PI * r;
  const dash = c * Math.max(0, Math.min(1, value / total));
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="rgba(148,163,184,.18)" strokeWidth={stroke} fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={stroke} fill="none" strokeLinecap="round"
          strokeDasharray={`${dash} ${c}`} style={{ transition: "stroke-dasharray .6s cubic-bezier(.4,0,.2,1)" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="font-mono text-[11px] font-semibold text-ink-100">{value}<span className="text-ink-500">/{total}</span></div>
        <div className="eyebrow text-[8px]">retries</div>
      </div>
    </div>
  );
}

function ExperimentCard({ exp, idx, isWinner, allDone }: {
  exp: ExperimentResult | null; idx: number; isWinner: boolean; allDone: boolean;
}) {
  const isPlaceholder = !exp;
  const running = isPlaceholder || (!exp.success && exp.retry_count < 3);
  const status = isPlaceholder ? "running" : exp.success ? "success" : exp.retry_count >= 3 ? "failed" : exp.retry_count > 0 ? "retrying" : "running";
  const score = exp?.parsed_metrics ? Object.values(exp.parsed_metrics)[0] : 0;
  const logLines = exp ? parseLogLines(exp.stdout, exp.fix_history) : [];
  const accentColors = ["#10B981", "#3B82F6"];
  const accent = accentColors[idx];

  const statusMap: Record<string, { dot: string; bg: string; text: string; border: string; label: string }> = {
    running:  { dot: "bg-accent-blue",    bg: "bg-accent-blue/10",    text: "text-accent-blueGlow", border: "border-accent-blue/30",    label: "Running"  },
    retrying: { dot: "bg-accent-amber",   bg: "bg-accent-amber/10",   text: "text-accent-amber",    border: "border-accent-amber/30",   label: "Retrying" },
    success:  { dot: "bg-accent-emerald", bg: "bg-accent-emerald/10", text: "text-accent-emerald",  border: "border-accent-emerald/30", label: "Success"  },
    failed:   { dot: "bg-accent-rose",    bg: "bg-accent-rose/10",    text: "text-accent-rose",     border: "border-accent-rose/30",    label: "Failed"   },
  };
  const s = statusMap[status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: isWinner ? -6 : (allDone && !isWinner ? 4 : 0), scale: isWinner ? 1.01 : (allDone && !isWinner ? 0.985 : 1) }}
      transition={{ duration: 0.5, delay: idx * 0.08 }}
      className={`glass-strong rounded-xl p-5 relative overflow-hidden card-lift ${allDone && !isWinner ? "opacity-70" : ""}`}
      style={isWinner ? { boxShadow: "0 0 0 1px rgba(251,191,36,.6), 0 0 40px -6px rgba(251,191,36,.45)" } : {}}>

      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-7 rounded-full" style={{ background: accent }} />
          <div>
            <div className="text-[15px] font-semibold tracking-tight">
              {isPlaceholder ? `Experiment ${idx + 1}` : exp.architecture_name || `Experiment ${idx + 1}`}
            </div>
            <div className="font-mono text-[11px] text-ink-400 mt-0.5">
              {isPlaceholder ? "queued..." : exp.architecture_name?.toLowerCase()}
            </div>
          </div>
        </div>
        <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${s.bg} ${s.border} ${s.text}`}>
          <span className={`dot ${s.dot} ${status === "running" || status === "retrying" ? "pulse-dot" : ""}`} />
          <span className="text-[11px] font-medium">{s.label}</span>
        </div>
      </div>

      <TerminalLog lines={logLines} running={running} />

      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-4">
          <CircularProgress value={exp?.retry_count ?? 0}
            color={status === "retrying" ? "#F59E0B" : status === "failed" ? "#F43F5E" : accent} />
          {isPlaceholder && (
            <div className="text-[12px] text-ink-500 font-mono italic">waiting...</div>
          )}
        </div>
        <div className="text-right">
          <div className="eyebrow">{exp?.parsed_metrics ? Object.keys(exp.parsed_metrics)[0]?.toUpperCase().replace("_", "-") : "METRIC"}</div>
          <div className={`font-mono font-semibold text-[28px] leading-none mt-1 ${exp?.success ? (idx === 0 ? "text-accent-emerald" : "text-accent-blueGlow") : "text-ink-500"}`}>
            {exp?.success && score > 0 ? <CountUp to={score} decimals={4} /> : "--"}
          </div>
        </div>
      </div>

      {isWinner && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
          className="absolute top-4 right-4">
          <div className="px-2 py-0.5 rounded-full bg-accent-gold/15 border border-accent-gold/50 text-accent-gold text-[10px] font-mono uppercase tracking-widest font-semibold">Winner</div>
        </motion.div>
      )}
    </motion.div>
  );
}

export default function ExperimentPanel({ experiments, evaluationMetric }: {
  experiments: ExperimentResult[];
  evaluationMetric?: string;
}) {
  const allDone = experiments.length > 0 && experiments.every(e => e.success || e.retry_count >= 3);
  const winner = allDone ? experiments.reduce((best, e) => {
    const bs = best ? Object.values(best.parsed_metrics ?? {})[0] ?? 0 : 0;
    const es = Object.values(e.parsed_metrics ?? {})[0] ?? 0;
    return e.success && es > bs ? e : best;
  }, null as ExperimentResult | null) : null;

  const slots = experiments.length >= 2 ? experiments : [
    experiments[0] ?? null,
    experiments[1] ?? null,
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
      className="max-w-[1280px] w-full mx-auto px-8 py-6">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="eyebrow">04 / phase</div>
          <div className="text-[26px] font-semibold tracking-tight mt-1">Experiments running</div>
          <div className="text-ink-400 text-[13.5px] mt-1.5">Two architectures training in parallel. Autofix handles errors - up to 3 retries each.</div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-ink-800/60 border border-ink-700">
          <span className={`dot bg-accent-blue ${!allDone ? "pulse-dot" : ""}`} />
          <span className="font-mono text-[11px] text-ink-200">{allDone ? "complete" : "running"}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {slots.map((exp, i) => (
          <ExperimentCard key={i} exp={exp} idx={i} isWinner={!!winner && exp?.experiment_id === winner.experiment_id} allDone={allDone} />
        ))}
      </div>

      {experiments.length === 0 && (
        <div className="mt-4 text-center text-ink-500 text-[12px] font-mono">
          E2B sandbox is installing packages and running your ML pipeline - typically 2-4 minutes.
        </div>
      )}
    </motion.div>
  );
}


