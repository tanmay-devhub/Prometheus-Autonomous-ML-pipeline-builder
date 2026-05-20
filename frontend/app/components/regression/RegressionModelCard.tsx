"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface SuccessMetrics {
  r2?: number | null;
  rmse_pct_of_mean?: number | null;
  within_10_pct?: number | null;
  within_15_pct?: number | null;
  within_20_pct?: number | null;
  mae?: number | null;
  target_mean?: number | null;
}

interface Props {
  modelCard?: string;
  plainExplanation?: string;
  shapFeatures?: Array<{ feature: string; importance: number }>;
  winningJustification?: string;
  successMetrics?: SuccessMetrics;
}

function r2Color(v: number): string {
  if (v >= 0.8) return "bg-accent-emerald";
  if (v >= 0.6) return "bg-accent-amber";
  return "bg-accent-rose";
}

function toleranceColor(v: number): string {
  if (v >= 70) return "bg-accent-emerald";
  if (v >= 50) return "bg-accent-amber";
  return "bg-accent-rose";
}

function rmseColor(v: number): string {
  if (v <= 15) return "bg-accent-emerald";
  if (v <= 30) return "bg-accent-amber";
  return "bg-accent-rose";
}

function ProgressBar({
  label, value, max = 100, colorClass, suffix = "%", hint,
}: {
  label: string; value: number; max?: number; colorClass: string; suffix?: string; hint?: string;
}) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[12.5px] text-ink-200 font-medium">{label}</span>
          {hint && <span className="text-[10.5px] text-ink-500">{hint}</span>}
        </div>
        <span className={`text-[13px] font-mono font-semibold ${colorClass.replace("bg-", "text-")}`}>
          {value.toFixed(1)}{suffix}
        </span>
      </div>
      <div className="h-2 rounded-full bg-ink-800 overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${colorClass}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

function R2Bar({ value }: { value: number }) {
  // R2 can be negative; clamp display to 0–100% but keep label honest
  const displayPct = Math.min(Math.max(value * 100, 0), 100);
  const color = r2Color(value);
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[12.5px] text-ink-200 font-medium">R² Score</span>
          <span className="text-[10.5px] text-ink-500">variance explained</span>
        </div>
        <span className={`text-[13px] font-mono font-semibold ${color.replace("bg-", "text-")}`}>
          {value.toFixed(3)}
        </span>
      </div>
      <div className="h-2 rounded-full bg-ink-800 overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          animate={{ width: `${displayPct}%` }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

export default function RegressionModelCard({ modelCard, plainExplanation, shapFeatures, winningJustification, successMetrics }: Props) {
  const [showFullCard, setShowFullCard] = useState(false);
  const m = successMetrics ?? {};

  const hasMetrics = m.r2 != null || m.within_20_pct != null;

  return (
    <div className="space-y-4">
      {/* ── Success Rate Panel ──────────────────────────────────────── */}
      {hasMetrics && (
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="rounded-xl bg-ink-900/50 border border-ink-700 overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-700/60">
            <div>
              <div className="eyebrow text-[9px]">model quality</div>
              <div className="text-[14px] font-semibold mt-0.5">Success Rate</div>
            </div>
            <div className="flex items-center gap-2">
              {m.mae != null && m.target_mean != null && (
                <span className="px-2.5 py-1 rounded-full bg-ink-800 border border-ink-700 text-[11px] font-mono text-ink-300">
                  MAE {m.mae.toLocaleString(undefined, { maximumFractionDigits: 2 })} units
                </span>
              )}
              {m.r2 != null && (
                <span className={`px-2.5 py-1 rounded-full border text-[11px] font-mono font-semibold ${
                  m.r2 >= 0.8 ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald" :
                  m.r2 >= 0.6 ? "bg-accent-amber/10 border-accent-amber/30 text-accent-amber" :
                  "bg-accent-rose/10 border-accent-rose/30 text-accent-rose"
                }`}>
                  R² {m.r2.toFixed(3)}
                </span>
              )}
            </div>
          </div>

          <div className="p-5 space-y-4">
            {/* R² */}
            {m.r2 != null && <R2Bar value={m.r2} />}

            {/* RMSE % of mean — inverted: lower is better, display as accuracy */}
            {m.rmse_pct_of_mean != null && (
              <ProgressBar
                label="RMSE % of mean"
                value={m.rmse_pct_of_mean}
                max={50}
                colorClass={rmseColor(m.rmse_pct_of_mean)}
                hint="lower is better"
              />
            )}

            {/* Tolerance bands */}
            {m.within_10_pct != null && (
              <ProgressBar
                label="Within 10% tolerance"
                value={m.within_10_pct}
                colorClass={toleranceColor(m.within_10_pct)}
                hint="% predictions within ±10%"
              />
            )}
            {m.within_15_pct != null && (
              <ProgressBar
                label="Within 15% tolerance"
                value={m.within_15_pct}
                colorClass={toleranceColor(m.within_15_pct)}
                hint="% predictions within ±15%"
              />
            )}
            {m.within_20_pct != null && (
              <ProgressBar
                label="Within 20% tolerance"
                value={m.within_20_pct}
                colorClass={toleranceColor(m.within_20_pct)}
                hint="% predictions within ±20%"
              />
            )}

            {/* Legend */}
            <div className="flex items-center gap-4 pt-1 border-t border-ink-800/60">
              {[["bg-accent-emerald", "Good"], ["bg-accent-amber", "Acceptable"], ["bg-accent-rose", "Needs work"]].map(([c, l]) => (
                <div key={l} className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${c}`} />
                  <span className="text-[10.5px] text-ink-500">{l}</span>
                </div>
              ))}
            </div>
          </div>
        </motion.div>
      )}

      {/* ── SHAP features ───────────────────────────────────────────── */}
      {shapFeatures && shapFeatures.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.05 }}
          className="rounded-xl bg-ink-900/50 border border-ink-700 overflow-hidden"
        >
          <div className="px-5 py-3.5 border-b border-ink-700/60">
            <div className="eyebrow text-[9px]">feature importance</div>
            <div className="text-[14px] font-semibold mt-0.5">Top Predictors (SHAP)</div>
          </div>
          <div className="p-5 space-y-2.5">
            {shapFeatures.slice(0, 8).map((f, i) => {
              const maxImp = shapFeatures[0]?.importance ?? 1;
              const pct = (f.importance / maxImp) * 100;
              return (
                <div key={f.feature} className="flex items-center gap-3">
                  <span className="font-mono text-[10px] text-ink-500 w-4">{i + 1}</span>
                  <span className="text-[12px] text-ink-200 w-32 truncate" title={f.feature}>{f.feature}</span>
                  <div className="flex-1 h-1.5 rounded-full bg-ink-800 overflow-hidden">
                    <motion.div
                      className="h-full rounded-full bg-accent-violet"
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.6, delay: i * 0.04 }}
                    />
                  </div>
                  <span className="font-mono text-[10.5px] text-ink-400 w-14 text-right">{f.importance.toFixed(4)}</span>
                </div>
              );
            })}
          </div>
          {plainExplanation && (
            <div className="px-5 pb-5 text-[12.5px] text-ink-300 leading-relaxed border-t border-ink-800/60 pt-4">
              {plainExplanation}
            </div>
          )}
        </motion.div>
      )}

      {/* ── Model card (collapsible) ─────────────────────────────────── */}
      {modelCard && (
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}
          className="rounded-xl bg-ink-900/50 border border-ink-700 overflow-hidden"
        >
          <button
            onClick={() => setShowFullCard(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3.5 border-b border-ink-700/60 hover:bg-ink-800/30 transition-colors"
          >
            <div className="text-left">
              <div className="eyebrow text-[9px]">documentation</div>
              <div className="text-[14px] font-semibold mt-0.5">Model Card</div>
            </div>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className={`text-ink-400 transition-transform ${showFullCard ? "rotate-180" : ""}`}>
              <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {showFullCard && (
            <div className="px-5 py-4 prose prose-invert prose-sm max-w-none text-[12.5px] leading-relaxed">
              <pre className="whitespace-pre-wrap text-ink-300 font-sans">{modelCard}</pre>
            </div>
          )}
          {winningJustification && (
            <div className="px-5 pb-4 pt-2 text-[12px] text-ink-400 italic border-t border-ink-800/60">
              {winningJustification}
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
