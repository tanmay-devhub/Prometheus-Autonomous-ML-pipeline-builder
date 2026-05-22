"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface Props {
  jobId: string;
  dateColumn: string | null;
  targetColumn: string | null;
  forecastHorizon: number;
  frequency: string | null;
  evaluationMetric: string | null;
  allColumns: string[];
  validationWarnings: { severity: string; message: string; column: string }[];
  onApproved: () => void;
  onReset: () => void;
  approveProblemFn: (
    jobId: string,
    approved: boolean,
    corrections?: {
      date_column?: string;
      target_column?: string;
      forecast_horizon?: number;
      evaluation_metric?: string;
    }
  ) => Promise<any>;
}

const METRICS = ["rmse", "mae", "mape"];
const FREQUENCIES = ["daily", "weekly", "monthly", "hourly"];

export default function TimeSeriesApprovalGate({
  jobId, dateColumn, targetColumn, forecastHorizon, frequency,
  evaluationMetric, allColumns, validationWarnings, onApproved, onReset, approveProblemFn,
}: Props) {
  const [selDate, setSelDate] = useState(dateColumn || "");
  const [selTarget, setSelTarget] = useState(targetColumn || "");
  const [selHorizon, setSelHorizon] = useState(String(forecastHorizon || 30));
  const [selMetric, setSelMetric] = useState(evaluationMetric || "rmse");
  const [loading, setLoading] = useState(false);

  const hasChanges =
    selDate !== (dateColumn || "") ||
    selTarget !== (targetColumn || "") ||
    selHorizon !== String(forecastHorizon || 30) ||
    selMetric !== (evaluationMetric || "rmse");

  const blockingWarnings = validationWarnings.filter(w => w.severity === "block");

  const handleApprove = async () => {
    setLoading(true);
    try {
      const corrections: any = {};
      if (selDate !== dateColumn) corrections.date_column = selDate;
      if (selTarget !== targetColumn) corrections.target_column = selTarget;
      if (selHorizon !== String(forecastHorizon)) corrections.forecast_horizon = parseInt(selHorizon);
      if (selMetric !== evaluationMetric) corrections.evaluation_metric = selMetric;
      await approveProblemFn(jobId, true, Object.keys(corrections).length > 0 ? corrections : undefined);
      onApproved();
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      className="max-w-[860px] mx-auto px-8 py-8"
    >
      <div className="absolute inset-x-0 top-0 h-48 -z-10 pointer-events-none"
        style={{ background: "radial-gradient(600px 300px at 50% 0%,rgba(16,185,129,.12),transparent 70%)" }} />

      <div className="eyebrow mb-1">02 . approve</div>
      <h2 className="text-[26px] font-semibold tracking-tight mt-1 mb-1">Confirm time series setup</h2>
      <p className="text-ink-400 text-[13.5px] mb-6">
        The AI detected these settings. Correct anything before the pipeline runs.
      </p>

      {/* Info banner */}
      <div className="flex gap-3 rounded-xl bg-accent-emerald/8 border border-accent-emerald/25 px-4 py-3 mb-6">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="text-accent-emerald shrink-0 mt-0.5">
          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8"/>
          <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <div className="text-[12.5px] text-ink-300">
          Time series mode: predicts future values from historical sequences.
          The model will use lag features, rolling averages, and date patterns to forecast{" "}
          <span className="text-accent-emerald font-medium">{selHorizon} steps ahead</span>.
        </div>
      </div>

      {/* Blocking warnings */}
      {blockingWarnings.length > 0 && (
        <div className="rounded-xl bg-accent-rose/8 border border-accent-rose/30 px-4 py-3 mb-5 space-y-1">
          {blockingWarnings.map((w, i) => (
            <div key={i} className="flex gap-2 text-[12.5px] text-accent-rose">
              <span className="font-mono">✗</span> {w.message}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-6">
        {/* Date column */}
        <div>
          <label className="eyebrow text-[9px] mb-1.5 block">Date / Time column</label>
          <select
            value={selDate}
            onChange={e => setSelDate(e.target.value)}
            className="w-full bg-ink-900/60 border border-ink-700 rounded-lg px-3 py-2 text-[13px] text-ink-100 focus:outline-none focus:border-accent-emerald/50"
          >
            <option value="">— select —</option>
            {allColumns.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Target column */}
        <div>
          <label className="eyebrow text-[9px] mb-1.5 block">Target column (to forecast)</label>
          <select
            value={selTarget}
            onChange={e => setSelTarget(e.target.value)}
            className="w-full bg-ink-900/60 border border-ink-700 rounded-lg px-3 py-2 text-[13px] text-ink-100 focus:outline-none focus:border-accent-emerald/50"
          >
            <option value="">— select —</option>
            {allColumns.filter(c => c !== selDate).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        {/* Forecast horizon */}
        <div>
          <label className="eyebrow text-[9px] mb-1.5 block">Forecast horizon (steps ahead)</label>
          <input
            type="number"
            min={1}
            max={365}
            value={selHorizon}
            onChange={e => setSelHorizon(e.target.value)}
            className="w-full bg-ink-900/60 border border-ink-700 rounded-lg px-3 py-2 text-[13px] text-ink-100 focus:outline-none focus:border-accent-emerald/50"
          />
          <div className="text-[10.5px] text-ink-500 mt-1">How many future periods to predict</div>
        </div>

        {/* Evaluation metric */}
        <div>
          <label className="eyebrow text-[9px] mb-1.5 block">Evaluation metric</label>
          <select
            value={selMetric}
            onChange={e => setSelMetric(e.target.value)}
            className="w-full bg-ink-900/60 border border-ink-700 rounded-lg px-3 py-2 text-[13px] text-ink-100 focus:outline-none focus:border-accent-emerald/50"
          >
            {METRICS.map(m => (
              <option key={m} value={m}>{m.toUpperCase()}</option>
            ))}
          </select>
          <div className="text-[10.5px] text-ink-500 mt-1">MAPE = % error (most intuitive), RMSE = absolute error</div>
        </div>
      </div>

      {/* Validation warnings */}
      {validationWarnings.filter(w => w.severity !== "block").length > 0 && (
        <div className="mb-5 space-y-1.5">
          {validationWarnings.filter(w => w.severity !== "block").slice(0, 5).map((w, i) => (
            <div key={i} className={[
              "flex gap-2 text-[12px] px-3 py-2 rounded-lg border",
              w.severity === "warn"
                ? "bg-accent-amber/8 border-accent-amber/25 text-amber-300"
                : "bg-ink-800/60 border-ink-700 text-ink-400",
            ].join(" ")}>
              <span className="font-mono text-[10px] mt-px">{w.severity === "warn" ? "⚠" : "ℹ"}</span>
              {w.message}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleApprove}
          disabled={loading || !selDate || !selTarget || blockingWarnings.length > 0}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium text-[13px] transition-all active:scale-[.98] disabled:opacity-35 disabled:cursor-not-allowed text-white"
          style={{ background: "linear-gradient(135deg,rgba(16,185,129,.9),rgba(5,150,105,.9))", border: "1px solid rgba(16,185,129,.3)" }}
        >
          {loading ? (
            <svg width="14" height="14" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" fill="none" strokeOpacity=".3"/><path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          )}
          {loading ? "Starting pipeline..." : hasChanges ? "Approve with corrections" : "Approve & run pipeline"}
        </button>
        <button
          onClick={onReset}
          className="px-4 py-2.5 rounded-xl text-[13px] font-medium border border-ink-700 text-ink-400 hover:text-ink-200 hover:border-ink-500 transition-all"
        >
          Cancel
        </button>
      </div>
    </motion.div>
  );
}
