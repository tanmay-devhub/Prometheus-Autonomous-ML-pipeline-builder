"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { testPredict } from "@/lib/regression-api";

interface Props {
  jobId: string;
  featureColumns: string[];
  targetColumn: string;
  sampleRows?: Record<string, any>[];
  heldOutRows?: Record<string, any>[];
}

export default function RegressionTestPanel({ jobId, featureColumns, targetColumn, sampleRows = [], heldOutRows = [] }: Props) {
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedSample, setSelectedSample] = useState<number | null>(null);
  const [showUnseen, setShowUnseen] = useState(false);

  const displayRows = showUnseen ? heldOutRows : sampleRows;

  const loadRow = (row: Record<string, any>, idx: number) => {
    const fd: Record<string, string> = {};
    for (const col of featureColumns) {
      fd[col] = row[col] != null ? String(row[col]) : "";
    }
    setFormData(fd);
    setSelectedSample(idx);
    setResult(null);
    setError("");
  };

  const handlePredict = async () => {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const payload: Record<string, any> = {};
      for (const col of featureColumns) {
        const v = formData[col];
        if (v === "" || v == null) {
          payload[col] = null;
        } else {
          const n = Number(v);
          payload[col] = isNaN(n) ? v : n;
        }
      }
      const res = await testPredict(jobId, payload);
      setResult(res);
    } catch (e: any) {
      setError(e.message || "Prediction failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl bg-ink-900/50 border border-ink-700 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-700/60">
        <div>
          <div className="eyebrow text-[9px]">live prediction</div>
          <div className="text-[14px] font-semibold mt-0.5">Test Regression Model</div>
        </div>
        {heldOutRows.length > 0 && (
          <div className="flex items-center gap-1 rounded-lg overflow-hidden border border-ink-700 text-[11px]">
            <button onClick={() => setShowUnseen(false)} className={`px-3 py-1.5 transition-colors ${!showUnseen ? "bg-ink-700 text-ink-100" : "text-ink-400 hover:text-ink-200"}`}>
              In-sample
            </button>
            <button onClick={() => setShowUnseen(true)} className={`px-3 py-1.5 transition-colors ${showUnseen ? "bg-accent-violet/20 text-accent-violet border-l border-ink-700" : "text-ink-400 hover:text-ink-200 border-l border-ink-700"}`}>
              Unseen ◆
            </button>
          </div>
        )}
      </div>

      <div className="p-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Row picker */}
        {displayRows.length > 0 && (
          <div>
            <div className="eyebrow mb-2">sample rows {showUnseen ? "(held-out ◆)" : "(in-sample)"}</div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {displayRows.slice(0, 20).map((row, i) => {
                const actual = row[targetColumn];
                return (
                  <button
                    key={i}
                    onClick={() => loadRow(row, i)}
                    className={`w-full text-left flex items-center justify-between px-3 py-2 rounded-lg border text-[11.5px] transition-colors ${selectedSample === i ? "bg-accent-violet/10 border-accent-violet/40 text-ink-100" : "bg-ink-800/60 border-ink-700/60 text-ink-300 hover:border-ink-600"}`}
                  >
                    <span className="font-mono">row {i + 1}{showUnseen ? " ◆" : ""}</span>
                    {actual != null && (
                      <span className="text-accent-violet font-mono">
                        actual: {typeof actual === "number" ? actual.toLocaleString(undefined, { maximumFractionDigits: 2 }) : actual}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Feature inputs */}
        <div>
          <div className="eyebrow mb-2">feature values</div>
          <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
            {featureColumns.slice(0, 20).map(col => (
              <div key={col}>
                <label className="block text-[10px] text-ink-500 mb-0.5 truncate" title={col}>{col}</label>
                <input
                  type="text"
                  value={formData[col] ?? ""}
                  onChange={e => setFormData(p => ({ ...p, [col]: e.target.value }))}
                  className="w-full bg-ink-800/60 border border-ink-700 rounded px-2 py-1 text-[11.5px] text-ink-100 font-mono focus:border-accent-violet/50 transition-colors"
                  placeholder="value"
                />
              </div>
            ))}
          </div>

          <button
            onClick={handlePredict}
            disabled={loading}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium text-[13px] border bg-accent-violet/80 hover:bg-accent-violet border-accent-violet/50 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-[.98]"
          >
            {loading ? (
              <><svg width="13" height="13" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,.3)" strokeWidth="2" fill="none"/><path d="M12 3a9 9 0 0 1 9 9" stroke="white" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>Predicting...</>
            ) : "Predict"}
          </button>
        </div>
      </div>

      {/* Result */}
      {result && (
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="mx-5 mb-5 rounded-lg border border-accent-violet/30 bg-accent-violet/8 px-5 py-4"
        >
          <div className="eyebrow text-[9px] text-accent-violet mb-2">prediction result</div>
          <div className="text-[28px] font-semibold tracking-tight text-ink-100">
            {result.prediction_formatted ?? (
              typeof result.prediction === "number"
                ? result.prediction.toLocaleString(undefined, { maximumFractionDigits: 4 })
                : String(result.prediction)
            )}
          </div>
          {result.mae_context && (
            <div className="text-[12px] text-ink-400 mt-1">
              {result.mae_context} · R² = {result.r2 ?? "—"}
            </div>
          )}
        </motion.div>
      )}

      {error && (
        <div className="mx-5 mb-5 px-4 py-3 rounded-lg bg-accent-rose/10 border border-accent-rose/30 text-accent-rose text-[12.5px]">
          {error}
        </div>
      )}
    </div>
  );
}
