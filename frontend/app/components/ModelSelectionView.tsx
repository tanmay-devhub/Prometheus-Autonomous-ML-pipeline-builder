﻿"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ExperimentResult } from "@/lib/api";
import CountUp from "./CountUp";

function TypeIn({ text }: { text: string }) {
  const [out, setOut] = useState("");
  useEffect(() => {
    let i = 0;
    const t = setTimeout(() => {
      const id = setInterval(() => { i++; setOut(text.slice(0, i)); if (i >= text.length) clearInterval(id); }, 16);
    }, 400);
    return () => clearTimeout(t);
  }, [text]);
  return <span>{out}<span className="blink inline-block w-1.5 h-3.5 bg-accent-emerald align-middle ml-0.5" /></span>;
}

function Confetti() {
  const pieces = Array.from({ length: 50 }).map((_, i) => ({
    id: i, x: 30 + Math.random() * 40, dx: (Math.random() - 0.5) * 500,
    dy: -150 - Math.random() * 250, rot: Math.random() * 720 - 360,
    color: ["#3B82F6", "#10B981", "#FBBF24", "#8B5CF6", "#F43F5E"][i % 5],
    circle: Math.random() > 0.5, delay: Math.random() * 0.2,
  }));
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {pieces.map(p => (
        <motion.div key={p.id}
          initial={{ x: 0, y: 0, rotate: 0, opacity: 1 }}
          animate={{ x: p.dx, y: p.dy + 400, rotate: p.rot, opacity: 0 }}
          transition={{ duration: 1.6, delay: p.delay }}
          style={{ position: "absolute", width: 8, height: 8, left: `${p.x}%`, top: "50%", background: p.color, borderRadius: p.circle ? "50%" : "2px" }}
        />
      ))}
    </div>
  );
}

export default function ModelSelectionView({ experiments, jobData, onApprove, loading }: {
  experiments: ExperimentResult[];
  jobData: any;
  onApprove: (selectedExperimentId?: string) => void;
  loading: boolean;
}) {
  const [showConfetti, setShowConfetti] = useState(false);
  const aiWinner = experiments.find(e => e.experiment_id === jobData?.winning_experiment?.experiment_id)
    ?? experiments.find(e => e.success)
    ?? experiments[0];
  const loser = experiments.find(e => e !== aiWinner);

  const [selected, setSelected] = useState<ExperimentResult | undefined>(aiWinner);
  useEffect(() => { setSelected(aiWinner); }, [aiWinner?.experiment_id]);

  useEffect(() => { const t = setTimeout(() => setShowConfetti(true), 300); return () => clearTimeout(t); }, []);

  const winner = selected ?? aiWinner;
  const isOverridden = selected && aiWinner && selected.experiment_id !== aiWinner.experiment_id;

  const metricKey = winner ? Object.keys(winner.parsed_metrics ?? {}).find(k => !["train_samples","test_samples"].includes(k)) ?? Object.keys(winner.parsed_metrics ?? {})[0] : undefined;
  const winnerScore = (metricKey && winner?.parsed_metrics?.[metricKey] as number) ?? 0;
  const loserScore = (metricKey && loser?.parsed_metrics?.[metricKey] as number) ?? 0;
  const metricName = metricKey?.toUpperCase().replace(/_/g, "-") ?? "METRIC";
  const justification = isOverridden
    ? `You manually selected '${winner?.architecture_name}' — overriding the AI recommendation.`
    : (jobData?.winning_justification ?? "Selected based on highest held-out metric score across all validation folds.");

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
      className="max-w-[1180px] w-full mx-auto px-8 py-6 relative">
      {showConfetti && <Confetti />}

      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="eyebrow">05 . phase</div>
          <div className="text-[26px] font-semibold tracking-tight mt-1">Model selected</div>
          <div className="text-ink-400 text-[13.5px] mt-1.5">Approve to generate the inference endpoint and packaged artifacts.</div>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-gold/10 border border-accent-gold/40 text-accent-gold">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M12 2v6M12 16v6M2 12h6M16 12h6M5 5l4 4M15 15l4 4M19 5l-4 4M9 15l-4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
          <span className="text-[11px] font-mono uppercase tracking-widest">selected</span>
        </div>
      </div>

      {/* Two equal clickable cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        {[aiWinner, loser].filter(Boolean).map((exp, idx) => {
          if (!exp) return null;
          const isAiPick = exp.experiment_id === aiWinner?.experiment_id;
          const isSelected = selected?.experiment_id === exp.experiment_id;
          const score = metricKey ? (exp.parsed_metrics?.[metricKey] as number) ?? 0 : 0;

          return (
            <motion.div
              key={exp.experiment_id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: idx * 0.1 }}
              onClick={() => setSelected(exp)}
              className="rounded-2xl p-5 border cursor-pointer relative transition-all select-none"
              style={{
                background: isSelected
                  ? isAiPick ? "rgba(251,191,36,.06)" : "rgba(59,130,246,.06)"
                  : "rgba(15,23,42,.5)",
                borderColor: isSelected
                  ? isAiPick ? "rgba(251,191,36,.6)" : "rgba(59,130,246,.55)"
                  : "rgba(55,65,81,.5)",
                boxShadow: isSelected
                  ? isAiPick ? "0 0 0 1px rgba(251,191,36,.4), 0 0 40px -8px rgba(251,191,36,.3)" : "0 0 0 1px rgba(59,130,246,.4), 0 0 40px -8px rgba(59,130,246,.25)"
                  : "none",
              }}>

              {/* Badges */}
              <div className="absolute -top-2.5 left-4 flex items-center gap-2">
                {isAiPick && (
                  <span className="px-2 py-0.5 rounded-full bg-accent-gold/15 border border-accent-gold/40 text-accent-gold text-[9px] font-mono uppercase tracking-widest flex items-center gap-1">
                    <svg width="8" height="8" viewBox="0 0 24 24" fill="none"><path d="M12 2v6M12 16v6M2 12h6M16 12h6M5 5l4 4M15 15l4 4M19 5l-4 4M9 15l-4 4" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/></svg>
                    AI pick
                  </span>
                )}
                {!isAiPick && (
                  <span className="px-2 py-0.5 rounded-full bg-ink-800 border border-ink-700 text-ink-500 text-[9px] font-mono uppercase">runner-up</span>
                )}
              </div>

              <div className="flex items-start justify-between mt-1">
                <div className="flex items-center gap-3">
                  {/* Radio circle */}
                  <div className="w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all"
                    style={{ borderColor: isSelected ? (isAiPick ? "#FBBF24" : "#3B82F6") : "rgba(75,85,99,1)" }}>
                    {isSelected && (
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: isAiPick ? "#FBBF24" : "#3B82F6" }} />
                    )}
                  </div>
                  <div>
                    <div className="text-[16px] font-semibold tracking-tight text-ink-100">{exp.architecture_name}</div>
                    <div className="font-mono text-[11px] text-ink-500 mt-0.5">{exp.architecture_name?.toLowerCase()}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="eyebrow text-[8.5px]">{metricName}</div>
                  <div className="font-mono font-semibold text-[26px] leading-none mt-1"
                    style={{ color: isSelected ? (isAiPick ? "#FBBF24" : "#60A5FA") : "#6B7280" }}>
                    {isSelected ? <CountUp to={score} decimals={4} /> : score.toFixed(4)}
                  </div>
                </div>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 pt-3 border-t border-ink-800/50">
                {[
                  { label: "retries", value: `${exp.retry_count ?? 0} / 3`, warn: (exp.retry_count ?? 0) > 0 },
                  { label: "status", value: exp.success ? "success" : "failed", warn: !exp.success },
                  { label: "experiment", value: idx === 0 ? "A" : "B", warn: false },
                ].map(({ label, value, warn }) => (
                  <div key={label}>
                    <div className="eyebrow text-[8.5px] mb-0.5">{label}</div>
                    <div className={`font-mono text-[13px] ${warn ? "text-accent-amber" : "text-ink-400"}`}>{value}</div>
                  </div>
                ))}
              </div>

              {isSelected && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}
                  className="mt-3 flex items-center gap-1.5 text-[10.5px] font-mono"
                  style={{ color: isAiPick ? "#FBBF24" : "#60A5FA" }}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  {isAiPick ? "AI recommended · currently selected" : "Manual override · currently selected"}
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </div>

      {/* Justification panel */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
        className={`rounded-xl px-5 py-4 mb-5 border ${isOverridden ? "bg-accent-blue/5 border-accent-blue/25" : "bg-accent-emerald/5 border-accent-emerald/25"}`}>
        <div className="flex items-center gap-2 mb-2">
          <span className={`dot ${isOverridden ? "bg-accent-blueGlow" : "bg-accent-emerald"}`} />
          <div className={`eyebrow text-[9px] ${isOverridden ? "text-accent-blueGlow" : "text-accent-emerald"}`}>
            {isOverridden ? "Manual override" : "Justification"}
          </div>
        </div>
        <div className="text-[13px] text-ink-200 leading-relaxed font-mono">
          <TypeIn key={justification} text={justification} />
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.2 }}
        className="flex items-center justify-between">
        <div className="text-[12px] text-ink-400">
          Approving will package <span className="font-mono text-ink-200">model.pkl</span>, generate <span className="font-mono text-ink-200">endpoint.py</span>, and prepare deployment steps.
          {isOverridden && <span className="ml-2 text-accent-blueGlow">Using manually selected model.</span>}
        </div>
        <button onClick={() => onApprove(isOverridden ? winner?.experiment_id : undefined)} disabled={loading}
          className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-medium text-[14px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-40 bg-accent-emerald hover:bg-accent-emeraldDim border-accent-emerald/40 text-white shadow-glow-emerald">
          {loading ? (
            <svg width="14" height="14" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,.3)" strokeWidth="2" fill="none"/><path d="M12 3a9 9 0 0 1 9 9" stroke="white" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14l7 0L11 22 20 10 13 10Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>
          )}
          Approve &amp; Generate Endpoint
        </button>
      </motion.div>
    </motion.div>
  );
}


