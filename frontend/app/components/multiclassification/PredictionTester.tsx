"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface PredResult {
  prediction: string;
  prediction_encoded: number;
  confidence: number;
  all_probabilities: Record<string, number>;
  target_column: string;
}

interface Props {
  jobId: string;
  featureColumns: string[];
  targetColumn: string;
  classNames?: string[];
  sampleRow?: Record<string, any>;
  sampleRows?: Record<string, any>[];
  heldOutRows?: Record<string, any>[];
}

const API_BASE = "http://localhost:8000/multiclassification";

function ProbabilityBar({ label, probability, isWinner }: { label: string; probability: number; isWinner: boolean }) {
  const pct = Math.round(probability * 100 * 10) / 10;
  return (
    <div className="flex items-center gap-3">
      <span className={`text-[12px] font-mono w-28 truncate ${isWinner ? "text-accent-amber font-semibold" : "text-ink-400"}`}
        title={label}>
        {label}
      </span>
      <div className="flex-1 h-4 rounded bg-ink-800 overflow-hidden relative">
        <motion.div
          className={`h-full rounded ${isWinner ? "bg-accent-amber" : "bg-ink-600"}`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
        <span className={`absolute right-1.5 top-0 bottom-0 flex items-center text-[10px] font-mono font-semibold ${isWinner ? "text-ink-900" : "text-ink-300"}`}>
          {pct.toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export default function PredictionTester({
  jobId, featureColumns, targetColumn, classNames = [],
  sampleRow, sampleRows = [], heldOutRows = [],
}: Props) {
  const [inputs, setInputs] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    featureColumns.forEach(c => { init[c] = sampleRow?.[c] != null ? String(sampleRow[c]) : ""; });
    return init;
  });
  const [result, setResult] = useState<PredResult | null>(null);
  const [actual, setActual] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [useUnseen, setUseUnseen] = useState(false);

  const runPrediction = useCallback(async (overrideInputs?: Record<string, string>) => {
    setRunning(true); setResult(null); setError("");
    const payload = overrideInputs ?? inputs;
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}/test-predict`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data);
    } catch (e: any) { setError(e.message || "Prediction failed."); }
    finally { setRunning(false); }
  }, [inputs, jobId]);

  const pickRandom = useCallback(async () => {
    const pool = useUnseen && heldOutRows.length > 0 ? heldOutRows : sampleRows;
    if (pool.length === 0) return;
    const row = pool[Math.floor(Math.random() * pool.length)];
    const newInputs: Record<string, string> = {};
    featureColumns.forEach(c => { newInputs[c] = row[c] != null ? String(row[c]) : ""; });
    const newActual = row[targetColumn] != null ? String(row[targetColumn]) : null;
    setInputs(newInputs);
    setActual(newActual);
    setResult(null);
    await runPrediction(newInputs);
  }, [sampleRows, heldOutRows, featureColumns, targetColumn, useUnseen, runPrediction]);

  const cols = featureColumns.slice(0, 12);
  const sortedProbs = result
    ? Object.entries(result.all_probabilities).sort(([, a], [, b]) => b - a)
    : [];

  const isCorrect = result && actual != null ? result.prediction === actual : null;

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
      className="glass-strong rounded-2xl p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent-amber/15 border border-accent-amber/40 flex items-center justify-center text-accent-amber">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M6 4L20 12L6 20Z" fill="currentColor"/></svg>
          </div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight">Test the model</div>
            <div className="text-[12px] text-ink-400 mt-0.5">Run predictions and see probabilities for all {classNames.length > 0 ? classNames.length : "?"} classes</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {sampleRows.length > 0 && (
            <>
              {heldOutRows.length > 0 && (
                <button onClick={() => setUseUnseen(u => !u)}
                  className={`px-2.5 py-1.5 rounded-md text-[11px] font-mono font-medium transition-colors border ${
                    useUnseen ? "bg-accent-amber/20 text-accent-amber border-accent-amber/40" : "text-ink-400 hover:text-ink-200 border-ink-700 hover:bg-ink-800/60"
                  }`}>
                  {useUnseen ? "Unseen ◆" : "Unseen"}
                </button>
              )}
              <button onClick={pickRandom} disabled={running}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium text-[12px] border transition-all active:scale-[.98] disabled:opacity-40 ${
                  useUnseen
                    ? "bg-accent-amber/15 hover:bg-accent-amber/25 border-accent-amber/40 text-accent-amber"
                    : "bg-ink-800 hover:bg-ink-700 border-ink-600 text-ink-200"
                }`}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                  <path d="M4 4h4v4H4zM16 4h4v4h-4zM4 16h4v4H4zM10 10h4v4h-4zM16 16h4v4h-4z" fill="currentColor" opacity=".7"/>
                </svg>
                {useUnseen ? "Sample unseen" : "Random"}
              </button>
            </>
          )}
          <span className="font-mono text-[11px] text-ink-500">POST /test-predict</span>
        </div>
      </div>

      {cols.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-5">
          {cols.map(col => (
            <div key={col}>
              <label className="eyebrow text-[9px] mb-1.5 block">{col}</label>
              <input value={inputs[col] ?? ""} onChange={e => setInputs({ ...inputs, [col]: e.target.value })}
                className="w-full bg-ink-900/60 border border-ink-700 rounded-md px-2.5 py-2 text-[12.5px] text-ink-100 font-mono hover:border-accent-amber/40 transition-colors" />
            </div>
          ))}
        </div>
      )}

      {actual != null && (
        <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
          <span className="eyebrow text-[9px]">actual {targetColumn}</span>
          <span className="font-mono text-[14px] font-semibold text-accent-amber">{actual}</span>
          <span className="text-ink-600 text-[11px] ml-auto font-mono">from dataset sample</span>
        </div>
      )}

      <div className="flex items-center justify-between">
        <button onClick={() => runPrediction()} disabled={running}
          className="relative overflow-hidden inline-flex items-center gap-2 px-4 py-2.5 rounded-md font-medium text-[13px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-40 bg-accent-amber hover:bg-accent-amber/80 border-accent-amber/40 text-ink-900 shadow">
          {running ? (
            <><svg width="13" height="13" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="rgba(0,0,0,.3)" strokeWidth="2" fill="none"/><path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>Predicting...</>
          ) : (
            <><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14l7 0L11 22 20 10 13 10Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>Run Prediction</>
          )}
        </button>
        <span className="font-mono text-[10.5px] text-ink-500">target: {targetColumn}</span>
      </div>

      {error && <div className="mt-4 text-accent-rose text-[13px] font-mono">{error}</div>}

      <AnimatePresence mode="wait">
        {result && (
          <motion.div key={result.prediction} initial={{ opacity: 0, scale: 0.96, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.4 }}
            className="mt-5 rounded-xl p-5 border border-accent-amber/25 bg-accent-amber/5">
            <div className="flex items-start justify-between mb-4">
              <div>
                <div className="eyebrow text-[9px] mb-1">Predicted / {targetColumn}</div>
                <motion.div initial={{ scale: 0, rotate: -8 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 180, damping: 14 }}
                  className="font-mono font-bold text-[36px] leading-none text-accent-amber">
                  {result.prediction}
                </motion.div>
                {actual != null && (
                  <div className="mt-2 flex items-center gap-2">
                    <span className="eyebrow text-[9px]">actual</span>
                    <span className="font-mono text-[15px] font-semibold text-ink-200">{actual}</span>
                    {isCorrect !== null && (
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold ${isCorrect ? "bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30" : "bg-accent-rose/15 text-accent-rose border border-accent-rose/30"}`}>
                        {isCorrect ? (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        ) : (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none"><path d="M6 6L18 18M18 6L6 18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/></svg>
                        )}
                        {isCorrect ? "correct" : "incorrect"}
                      </span>
                    )}
                  </div>
                )}
              </div>
              <div className="text-right">
                <div className="eyebrow text-[9px] mb-1">confidence</div>
                <div className="font-mono font-bold text-[28px] text-accent-amber">
                  {(result.confidence * 100).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* All class probabilities */}
            <div className="space-y-2.5 mt-3 pt-3 border-t border-ink-800/60">
              <div className="eyebrow text-[9px] mb-2">All class probabilities</div>
              {sortedProbs.map(([label, prob]) => (
                <ProbabilityBar
                  key={label}
                  label={label}
                  probability={prob}
                  isWinner={label === result.prediction}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
