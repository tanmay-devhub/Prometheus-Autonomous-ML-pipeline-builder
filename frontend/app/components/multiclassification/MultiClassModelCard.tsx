"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface Props {
  modelCard?: string;
  plainExplanation?: string;
  shapFeatures?: Array<{ feature: string; importance: number }>;
  winningJustification?: string;
  perClassMetrics?: Record<string, number>;
  classNames?: string[];
  numClasses?: number;
  accuracy?: number | null;
  f1Macro?: number | null;
  f1Weighted?: number | null;
}

function f1Color(v: number): string {
  if (v >= 0.85) return "text-accent-emerald";
  if (v >= 0.70) return "text-accent-amber";
  return "text-accent-rose";
}

function f1BgColor(v: number): string {
  if (v >= 0.85) return "bg-accent-emerald";
  if (v >= 0.70) return "bg-accent-amber";
  return "bg-accent-rose";
}

function ClassF1Row({ className, f1 }: { className: string; f1: number }) {
  const pct = Math.min(Math.max(f1 * 100, 0), 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-[12px] text-ink-200 w-28 truncate font-mono" title={className}>{className}</span>
      <div className="flex-1 h-1.5 rounded-full bg-ink-800 overflow-hidden">
        <motion.div
          className={`h-full rounded-full ${f1BgColor(f1)}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
      </div>
      <span className={`font-mono text-[11px] w-12 text-right font-semibold ${f1Color(f1)}`}>
        {f1.toFixed(3)}
      </span>
    </div>
  );
}

export default function MultiClassModelCard({
  modelCard, plainExplanation, shapFeatures, winningJustification,
  perClassMetrics, classNames, numClasses, accuracy, f1Macro, f1Weighted,
}: Props) {
  const [showFullCard, setShowFullCard] = useState(false);

  const hasPerClass = perClassMetrics && Object.keys(perClassMetrics).length > 0;
  const hasSummaryMetrics = f1Macro != null || accuracy != null;

  return (
    <div className="space-y-4">
      {/* ── Per-Class F1 Panel ──────────────────────────────────────── */}
      {(hasPerClass || hasSummaryMetrics) && (
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
          className="rounded-xl bg-ink-900/50 border border-ink-700 overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-700/60">
            <div>
              <div className="eyebrow text-[9px]">model quality</div>
              <div className="text-[14px] font-semibold mt-0.5">Classification Results</div>
            </div>
            <div className="flex items-center gap-2">
              {numClasses != null && (
                <span className="px-2.5 py-1 rounded-full bg-ink-800 border border-ink-700 text-[11px] font-mono text-ink-300">
                  {numClasses} classes
                </span>
              )}
              {accuracy != null && (
                <span className={`px-2.5 py-1 rounded-full border text-[11px] font-mono font-semibold ${
                  accuracy >= 0.85 ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald" :
                  accuracy >= 0.70 ? "bg-accent-amber/10 border-accent-amber/30 text-accent-amber" :
                  "bg-accent-rose/10 border-accent-rose/30 text-accent-rose"
                }`}>
                  Acc {(accuracy * 100).toFixed(1)}%
                </span>
              )}
              {f1Macro != null && (
                <span className={`px-2.5 py-1 rounded-full border text-[11px] font-mono font-semibold ${
                  f1Macro >= 0.85 ? "bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald" :
                  f1Macro >= 0.70 ? "bg-accent-amber/10 border-accent-amber/30 text-accent-amber" :
                  "bg-accent-rose/10 border-accent-rose/30 text-accent-rose"
                }`}>
                  F1 {f1Macro.toFixed(3)}
                </span>
              )}
            </div>
          </div>

          <div className="p-5 space-y-4">
            {/* Summary metrics row */}
            {hasSummaryMetrics && (
              <div className="grid grid-cols-3 gap-3 pb-3 border-b border-ink-800/60">
                {[
                  { label: "F1 Macro", value: f1Macro },
                  { label: "F1 Weighted", value: f1Weighted },
                  { label: "Accuracy", value: accuracy },
                ].map(({ label, value }) => value != null && (
                  <div key={label} className="text-center">
                    <div className="eyebrow text-[9px] mb-1">{label}</div>
                    <div className={`font-mono text-[18px] font-bold ${f1Color(value)}`}>
                      {(value * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Per-class F1 bars */}
            {hasPerClass && (
              <div className="space-y-2.5">
                <div className="eyebrow text-[9px] mb-2">Per-class F1 Score</div>
                {Object.entries(perClassMetrics!).map(([cls, f1]) => (
                  <ClassF1Row key={cls} className={cls} f1={typeof f1 === "number" ? f1 : 0} />
                ))}
              </div>
            )}

            {/* Legend */}
            <div className="flex items-center gap-4 pt-1 border-t border-ink-800/60">
              {[["bg-accent-emerald", "Good (≥0.85)"], ["bg-accent-amber", "Acceptable (≥0.70)"], ["bg-accent-rose", "Needs work (<0.70)"]].map(([c, l]) => (
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
                      className="h-full rounded-full bg-accent-amber"
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
