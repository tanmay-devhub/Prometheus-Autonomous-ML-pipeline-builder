"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { approveProblem } from "@/lib/api";

const METRICS: Record<string, { value: string; label: string }[]> = {
  binary_classification: [
    { value: "roc_auc",  label: "ROC-AUC" },
    { value: "f1",       label: "F1 Score" },
    { value: "accuracy", label: "Accuracy" },
    { value: "pr_auc",   label: "PR-AUC" },
    { value: "log_loss", label: "Log-loss" },
  ],
  regression: [
    { value: "r2",   label: "R² Score" },
    { value: "rmse", label: "RMSE" },
    { value: "mae",  label: "MAE" },
  ],
};

const DEFAULT_METRIC: Record<string, string> = {
  binary_classification: "roc_auc",
  regression: "r2",
};

interface Props {
  jobId: string;
  taskType: string;
  targetColumn: string;
  metric: string;
  allColumns: string[];
  validationWarnings: Array<{ severity: string; message: string; column: string }>;
  leakageWarnings: string[];
  onApproved: () => void;
  onReset?: () => void;
}

export default function ApprovalGate({ jobId, taskType, targetColumn, metric, allColumns, validationWarnings, leakageWarnings, onApproved, onReset }: Props) {
  const [task, setTask] = useState(taskType || "binary_classification");
  const [target, setTarget] = useState(targetColumn || "");
  const [selectedMetric, setSelectedMetric] = useState(metric || DEFAULT_METRIC[taskType] || "roc_auc");
  const [loading, setLoading] = useState(false);
  const [showRegressionModal, setShowRegressionModal] = useState(taskType === "regression");

  // Show modal whenever task switches to regression
  useEffect(() => {
    if (task === "regression") setShowRegressionModal(true);
  }, [task]);

  // Auto-switch metric when task type changes
  useEffect(() => {
    const available = METRICS[task] ?? METRICS.binary_classification;
    const isValid = available.some(m => m.value === selectedMetric);
    if (!isValid) setSelectedMetric(DEFAULT_METRIC[task] ?? available[0].value);
  }, [task]);

  const warnings = [
    ...validationWarnings.map(w => ({ id: w.column, title: w.message, detail: `Column: ${w.column}` })),
    ...leakageWarnings.map((w, i) => ({ id: `leak-${i}`, title: "Possible target leakage", detail: w })),
  ];

  const handleApprove = async () => {
    setLoading(true);
    try {
      await approveProblem(jobId, true, { target_column: target, task_type: task });
      onApproved();
    } catch {}
    finally { setLoading(false); }
  };

  const handleReject = async () => {
    await approveProblem(jobId, false);
    if (onReset) onReset(); else window.location.reload();
  };

  const handleSwitchToClassification = () => {
    setTask("binary_classification");
    setShowRegressionModal(false);
  };

  const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <div className="flex items-center justify-between py-3 border-b border-ink-800 last:border-b-0">
      <div className="eyebrow">{label}</div>
      {children}
    </div>
  );

  const metricOptions = METRICS[task] ?? METRICS.binary_classification;
  const isRegression = task === "regression";

  return (
    <>
      {/* Regression not-supported modal */}
      <AnimatePresence>
        {showRegressionModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.94, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.94, y: 8 }}
              transition={{ duration: 0.25 }}
              className="relative w-full max-w-[440px] mx-4 rounded-2xl glass-strong border border-ink-700 p-7 shadow-2xl"
            >
              {/* Icon */}
              <div className="w-12 h-12 rounded-xl bg-accent-amber/15 border border-accent-amber/30 flex items-center justify-center mb-5">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" className="text-accent-amber">
                  <path d="M12 3L22 20H2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
                  <path d="M12 10v4M12 17v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                </svg>
              </div>

              <div className="eyebrow text-accent-amber mb-2">v1 limitation</div>
              <div className="text-[18px] font-semibold tracking-tight mb-3">
                Regression not available
              </div>
              <p className="text-[13px] text-ink-300 leading-relaxed mb-1">
                This version of Prometheus is configured for <span className="text-ink-100 font-medium">binary classification</span> only.
              </p>
              <p className="text-[13px] text-ink-400 leading-relaxed mb-7">
                Regression support will be added in the next version.
              </p>

              <div className="flex flex-col gap-2.5">
                <button
                  onClick={handleSwitchToClassification}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium text-[13px] tracking-tight border transition-all active:scale-[.98] bg-accent-blue hover:bg-accent-blueDim border-accent-blue/40 text-white shadow-glow-blue"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Switch to Binary Classification
                </button>
                <button
                  onClick={handleReject}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium text-[13px] tracking-tight border transition-all active:scale-[.98] bg-transparent border-ink-700 text-ink-300 hover:border-ink-500 hover:text-ink-100"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M3 3v5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  Start New Job
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
        className="max-w-[860px] w-full mx-auto px-8 py-8">
        <div className="flex items-end justify-between mb-6">
          <div>
            <div className="eyebrow">02 / phase</div>
            <div className="text-[26px] font-semibold tracking-tight mt-1">Confirm the plan</div>
            <div className="text-ink-400 text-[13.5px] mt-1.5">Prometheus inferred this from your description and dataset. Review before training kicks off.</div>
          </div>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border bg-accent-amber/10 border-accent-amber/30 text-accent-amber">
            <span className="dot bg-accent-amber pulse-dot" />
            <span className="text-[11px] font-medium tracking-wide">Awaiting approval</span>
          </div>
        </div>

        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.05 }}
          className="glass-strong rounded-xl p-1">
          <div className="px-5 pt-2">
            <Field label="Task Type">
              <select value={task} onChange={e => setTask(e.target.value)}
                className="bg-ink-850 border border-ink-700 rounded-md px-3 py-1.5 text-[12.5px] text-ink-100 hover:border-accent-blue/40 transition-colors">
                <option value="binary_classification">Binary Classification</option>
                <option value="regression">Regression</option>
              </select>
            </Field>
            <Field label="Target Column">
              {allColumns.length > 0 ? (
                <select value={target} onChange={e => setTarget(e.target.value)}
                  className="bg-ink-850 border border-ink-700 rounded-md px-3 py-1.5 text-[12.5px] font-mono text-accent-blueGlow hover:border-accent-blue/40 transition-colors">
                  {allColumns.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              ) : (
                <input value={target} onChange={e => setTarget(e.target.value)}
                  className="bg-ink-850 border border-ink-700 rounded-md px-3 py-1.5 text-[12.5px] font-mono text-accent-blueGlow text-right hover:border-accent-blue/40 transition-colors" />
              )}
            </Field>
            <Field label="Evaluation Metric">
              <select value={selectedMetric} onChange={e => setSelectedMetric(e.target.value)}
                className="bg-ink-850 border border-ink-700 rounded-md px-3 py-1.5 text-[12.5px] font-mono text-ink-100 hover:border-accent-blue/40 transition-colors">
                {metricOptions.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
              </select>
            </Field>
          </div>

          {warnings.length > 0 && (
            <div className="px-5 pt-3 pb-5">
              <div className="eyebrow mb-3">Detected issues</div>
              <div className="grid gap-2">
                {warnings.map((w, i) => (
                  <motion.div key={w.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35, delay: 0.1 + i * 0.05 }}
                    className="flex items-start gap-3 rounded-lg px-3.5 py-3 bg-accent-amber/8 border border-accent-amber/25">
                    <div className="text-accent-amber mt-0.5">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M12 3L22 20H2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M12 10v4M12 17v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
                    </div>
                    <div>
                      <div className="text-[12.5px] text-accent-amber font-medium">{w.title}</div>
                      <div className="text-[12px] text-ink-300 mt-0.5">{w.detail}</div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          )}
        </motion.div>

        {/* Task-specific info */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}
          className="mt-4 px-4 py-3 rounded-lg bg-ink-900/60 border border-ink-700/50 flex items-start gap-3">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="text-accent-blueGlow mt-0.5 shrink-0">
            <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.6"/>
            <path d="M12 8v4M12 16v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
          </svg>
          <div className="text-[12px] text-ink-300">
            {isRegression ? (
              <>
                <span className="text-ink-100 font-medium">Regression mode:</span> predicts a continuous numeric value.
                {" "}Optimizing for <span className="font-mono text-accent-blueGlow">{selectedMetric.toUpperCase()}</span>.
                {" "}Use this for price prediction, forecasting, or any continuous target.
              </>
            ) : (
              <>
                <span className="text-ink-100 font-medium">Binary classification mode:</span> predicts class 0 or 1.
                {" "}Optimizing for <span className="font-mono text-accent-blueGlow">{selectedMetric.toUpperCase().replace("_", "-")}</span>.
                {" "}Use this for churn prediction, fraud detection, medical diagnosis, etc.
              </>
            )}
          </div>
        </motion.div>

        <div className="flex items-center justify-between mt-5">
          <div className="text-[12px] text-ink-400">You can <span className="text-ink-200">adjust any field</span> above before approval.</div>
          <div className="flex items-center gap-3">
            <button onClick={handleReject}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md font-medium text-[13px] tracking-tight border bg-transparent transition-all active:scale-[.98] border-accent-rose/50 text-accent-rose hover:bg-accent-rose/10">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 6L18 18M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
              Reject
            </button>
            <button onClick={handleApprove} disabled={loading || isRegression}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-md font-medium text-[13px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-40 bg-accent-emerald hover:bg-accent-emeraldDim border-accent-emerald/40 text-white shadow-glow-emerald">
              {loading ? (
                <svg width="13" height="13" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,.3)" strokeWidth="2" fill="none"/><path d="M12 3a9 9 0 0 1 9 9" stroke="white" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
              )}
              Approve &amp; Train
            </button>
          </div>
        </div>
      </motion.div>
    </>
  );
}
