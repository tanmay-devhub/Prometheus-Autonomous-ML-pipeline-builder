"use client";

import { useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useRouter } from "next/navigation";
import { autoCreateJob } from "@/lib/auto-api";

const card = { initial: { opacity: 0, y: 20 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.4 } };

const TASK_LABELS: Record<string, { label: string; color: string; path: string }> = {
  binary_classification:    { label: "Binary Classification",    color: "#3B82F6", path: "classification" },
  multiclass_classification: { label: "Multi-Class Classification", color: "#F59E0B", path: "multiclassification" },
  regression:               { label: "Regression",               color: "#8B5CF6", path: "regression" },
};

function QuickStart() {
  const router = useRouter();
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState<"idle" | "loading" | "detected" | "error">("idle");
  const [result, setResult] = useState<{ label: string; color: string; path: string; reasoning: string; confidence: number } | null>(null);
  const [error, setError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && f.name.endsWith(".csv")) setFile(f);
  }, []);

  const handleSubmit = async () => {
    if (!file || !description.trim()) return;
    setState("loading");
    setError("");
    try {
      const res = await autoCreateJob(file, description);
      const meta = TASK_LABELS[res.task_type] ?? TASK_LABELS.binary_classification;
      setResult({ ...meta, reasoning: res.reasoning, confidence: res.confidence });
      setState("detected");
      setTimeout(() => {
        router.push(`/${meta.path}?job=${res.job_id}`);
      }, 2200);
    } catch (e: any) {
      setError(e.message || "Detection failed.");
      setState("error");
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.25 }}
      className="w-full max-w-[1100px] mt-6 rounded-2xl border border-ink-700/60 overflow-hidden"
      style={{ background: "linear-gradient(135deg,rgba(15,23,42,.95),rgba(15,23,42,.80))" }}>
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-ink-700/50"
        style={{ background: "linear-gradient(90deg,rgba(255,255,255,.03),transparent)" }}>
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-blue/30 to-accent-violet/30 border border-ink-600 flex items-center justify-center">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="text-ink-300">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div>
          <div className="text-[13px] font-semibold tracking-tight text-ink-100">Not sure what to pick?</div>
          <div className="text-[11px] text-ink-500 mt-0.5">Describe your goal, upload your data — Prometheus will detect the right approach automatically.</div>
        </div>
        <div className="ml-auto px-2.5 py-1 rounded-full bg-accent-emerald/10 border border-accent-emerald/25 text-accent-emerald text-[10px] font-mono">
          AI-powered
        </div>
      </div>

      <div className="p-6">
        <AnimatePresence mode="wait">
          {state === "detected" && result ? (
            <motion.div key="detected" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-8 gap-4 text-center">
              <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 180, damping: 14 }}
                className="w-16 h-16 rounded-2xl flex items-center justify-center border"
                style={{ background: `${result.color}15`, borderColor: `${result.color}40` }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ color: result.color }}>
                  <path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </motion.div>
              <div>
                <div className="text-[12px] text-ink-500 mb-1">Detected task type</div>
                <div className="text-[22px] font-semibold tracking-tight" style={{ color: result.color }}>{result.label}</div>
                <div className="text-[12px] text-ink-400 mt-1.5 max-w-[400px] mx-auto">{result.reasoning}</div>
                <div className="text-[11px] font-mono text-ink-500 mt-1">Confidence: {Math.round(result.confidence * 100)}%</div>
              </div>
              <div className="flex items-center gap-2 text-[12px] text-ink-400">
                <svg width="13" height="13" viewBox="0 0 24 24" className="spin-slow text-ink-500"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" fill="none" strokeOpacity=".3"/><path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
                Routing to {result.label} pipeline...
              </div>
            </motion.div>
          ) : state === "loading" ? (
            <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-10 gap-4">
              <div className="relative">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-blue/20 to-accent-violet/20 border border-ink-600 flex items-center justify-center">
                  <svg width="24" height="24" viewBox="0 0 24 24" className="spin-slow text-accent-blueGlow"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2" fill="none" strokeOpacity=".3"/><path d="M12 3a9 9 0 0 1 9 9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
                </div>
              </div>
              <div className="text-center">
                <div className="text-[14px] font-medium text-ink-200">Analyzing your data...</div>
                <div className="text-[12px] text-ink-500 mt-1">Reading dataset structure · Inferring task type · Starting pipeline</div>
              </div>
            </motion.div>
          ) : (
            <motion.div key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Description */}
              <div>
                <label className="eyebrow text-[9px] mb-2 block">Describe your problem</label>
                <textarea
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="e.g. Predict whether a customer will churn based on their usage patterns and demographics..."
                  rows={4}
                  className="w-full bg-ink-900/60 border border-ink-700 rounded-xl px-4 py-3 text-[13px] text-ink-100 placeholder-ink-600 resize-none hover:border-ink-500 focus:border-accent-blue/50 focus:outline-none transition-colors leading-relaxed"
                />
              </div>

              {/* CSV upload */}
              <div>
                <label className="eyebrow text-[9px] mb-2 block">Upload your CSV</label>
                <div
                  onDragOver={e => { e.preventDefault(); setDragging(true); }}
                  onDragLeave={() => setDragging(false)}
                  onDrop={onDrop}
                  onClick={() => fileRef.current?.click()}
                  className="h-[108px] rounded-xl border-2 border-dashed flex flex-col items-center justify-center cursor-pointer transition-all"
                  style={{
                    borderColor: dragging ? "rgba(59,130,246,.6)" : file ? "rgba(16,185,129,.4)" : "rgba(55,65,81,.5)",
                    background: dragging ? "rgba(59,130,246,.05)" : file ? "rgba(16,185,129,.04)" : "rgba(15,23,42,.3)",
                  }}>
                  <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={e => { if (e.target.files?.[0]) setFile(e.target.files[0]); }} />
                  {file ? (
                    <>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-accent-emerald mb-1.5"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      <div className="text-[12.5px] font-medium text-accent-emerald">{file.name}</div>
                      <div className="text-[10.5px] text-ink-500 mt-0.5">{(file.size / 1024).toFixed(1)} KB · click to change</div>
                    </>
                  ) : (
                    <>
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" className="text-ink-500 mb-1.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      <div className="text-[12.5px] text-ink-400">Drop CSV here or click to browse</div>
                      <div className="text-[10.5px] text-ink-600 mt-0.5">Any tabular dataset works</div>
                    </>
                  )}
                </div>
              </div>

              {/* Submit row */}
              <div className="md:col-span-2 flex items-center justify-between">
                {error && <div className="text-[12px] text-accent-rose font-mono">{error}</div>}
                {!error && <div className="text-[12px] text-ink-500">The AI will determine whether your problem is classification, multi-class, or regression.</div>}
                <button
                  onClick={handleSubmit}
                  disabled={!file || !description.trim()}
                  className="inline-flex items-center gap-2.5 px-5 py-2.5 rounded-xl font-medium text-[13px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-35 disabled:cursor-not-allowed"
                  style={{ background: "linear-gradient(135deg,rgba(59,130,246,.9),rgba(139,92,246,.9))", borderColor: "rgba(99,102,241,.4)", color: "white", boxShadow: "0 0 20px -4px rgba(99,102,241,.4)" }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  Analyze &amp; Build
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  const router = useRouter();

  return (
    <div className="min-h-screen w-full flex flex-col relative">
      <div className="fixed inset-0 bg-grid opacity-40 pointer-events-none" />

      {/* Header */}
      <div className="flex items-center gap-3 px-8 pt-6 pb-2 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-blue to-accent-violet flex items-center justify-center shadow-glow-blue">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L4 7L4 17L12 22L20 17L20 7Z" stroke="white" strokeWidth="1.5" fill="none"/>
            <path d="M12 2L12 22M4 7L20 17M20 7L4 17" stroke="white" strokeWidth="1" opacity=".6"/>
          </svg>
        </div>
        <div>
          <div className="text-[13px] font-semibold tracking-tight">Prometheus</div>
          <div className="eyebrow text-[9.5px] -mt-px">autonomous ml pipeline · v3</div>
        </div>
      </div>

      {/* Hero */}
      <div className="flex flex-col items-center px-8 py-12 pb-20">
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="text-center mb-8"
        >
          <div className="eyebrow mb-3">choose your task</div>
          <h1 className="text-[32px] font-semibold tracking-tight mb-3">What are you building?</h1>
          <p className="text-ink-400 text-[14px] max-w-[420px] mx-auto leading-relaxed">
            Describe your problem, upload a CSV, and Prometheus autonomously designs, trains, and deploys a model.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 w-full max-w-[1100px]">
          {/* Classification Card */}
          <motion.button
            {...card}
            transition={{ duration: 0.4, delay: 0.05 }}
            onClick={() => router.push("/classification")}
            className="group text-left rounded-2xl bg-ink-900/60 border border-ink-700 hover:border-accent-blue/50 hover:bg-ink-800/60 p-7 transition-all duration-200 active:scale-[.98] relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-accent-blue/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-accent-blue/10 border border-accent-blue/30 flex items-center justify-center mb-5 text-accent-blueGlow group-hover:bg-accent-blue/20 transition-colors">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <circle cx="8" cy="8" r="3" stroke="currentColor" strokeWidth="1.5"/>
                  <circle cx="16" cy="16" r="3" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M8 11v6M16 8v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M3 12h5M16 12h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity=".4"/>
                </svg>
              </div>
              <div className="text-[18px] font-semibold tracking-tight mb-2">Classification</div>
              <div className="text-ink-400 text-[13px] leading-relaxed mb-5">
                Predict binary outcomes — two classes only.
              </div>
              <div className="flex flex-wrap gap-2">
                {["Yes / No", "Survived / Died", "Disease / Healthy", "Spam / Not Spam"].map(ex => (
                  <span key={ex} className="px-2 py-1 rounded-md bg-ink-800 border border-ink-700 text-ink-300 text-[11px] font-mono">
                    {ex}
                  </span>
                ))}
              </div>
              <div className="mt-5 flex items-center gap-2 text-accent-blueGlow text-[12px] font-medium">
                Start classification
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="group-hover:translate-x-0.5 transition-transform">
                  <path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            </div>
          </motion.button>

          {/* Regression Card */}
          <motion.button
            {...card}
            transition={{ duration: 0.4, delay: 0.1 }}
            onClick={() => router.push("/regression")}
            className="group text-left rounded-2xl bg-ink-900/60 border border-ink-700 hover:border-accent-violet/50 hover:bg-ink-800/60 p-7 transition-all duration-200 active:scale-[.98] relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-accent-violet/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-accent-violet/10 border border-accent-violet/30 flex items-center justify-center mb-5 text-accent-violet group-hover:bg-accent-violet/20 transition-colors">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path d="M3 20l4-8 4 3 4-9 4 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                  <circle cx="7" cy="12" r="1.5" fill="currentColor"/>
                  <circle cx="11" cy="15" r="1.5" fill="currentColor"/>
                  <circle cx="15" cy="6" r="1.5" fill="currentColor"/>
                  <circle cx="19" cy="11" r="1.5" fill="currentColor"/>
                </svg>
              </div>
              <div className="text-[18px] font-semibold tracking-tight mb-2">Regression</div>
              <div className="text-ink-400 text-[13px] leading-relaxed mb-5">
                Predict continuous numeric values.
              </div>
              <div className="flex flex-wrap gap-2">
                {["House prices", "Salaries", "Temperatures", "Sales forecasts"].map(ex => (
                  <span key={ex} className="px-2 py-1 rounded-md bg-ink-800 border border-ink-700 text-ink-300 text-[11px] font-mono">
                    {ex}
                  </span>
                ))}
              </div>
              <div className="mt-5 flex items-center gap-2 text-accent-violet text-[12px] font-medium">
                Start regression
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="group-hover:translate-x-0.5 transition-transform">
                  <path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            </div>
          </motion.button>

          {/* Multi-Class Classification Card */}
          <motion.button
            {...card}
            transition={{ duration: 0.4, delay: 0.15 }}
            onClick={() => router.push("/multiclassification")}
            className="group text-left rounded-2xl bg-ink-900/60 border border-ink-700 hover:border-accent-amber/50 hover:bg-ink-800/60 p-7 transition-all duration-200 active:scale-[.98] relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-accent-amber/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="relative">
              <div className="w-12 h-12 rounded-xl bg-accent-amber/10 border border-accent-amber/30 flex items-center justify-center mb-5 text-accent-amber group-hover:bg-accent-amber/20 transition-colors">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <circle cx="6" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                  <circle cx="12" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                  <circle cx="18" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                  <circle cx="12" cy="19" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
                  <path d="M8 11L10.5 7M14 7L16 10M16 14L14 17M10 17L8 14" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".5"/>
                </svg>
              </div>
              <div className="text-[18px] font-semibold tracking-tight mb-2">Multi-Class</div>
              <div className="text-ink-400 text-[13px] leading-relaxed mb-5">
                Predict one of 3+ categories with per-class analysis.
              </div>
              <div className="flex flex-wrap gap-2">
                {["Wine quality", "News topics", "Iris species", "Customer tier"].map(ex => (
                  <span key={ex} className="px-2 py-1 rounded-md bg-ink-800 border border-ink-700 text-ink-300 text-[11px] font-mono">
                    {ex}
                  </span>
                ))}
              </div>
              <div className="mt-5 flex items-center gap-2 text-accent-amber text-[12px] font-medium">
                Start multi-class
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" className="group-hover:translate-x-0.5 transition-transform">
                  <path d="M5 12h14M14 7l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
            </div>
          </motion.button>
        </div>

        {/* Quick Start */}
        <div className="w-full max-w-[1100px] flex items-center gap-4 mt-6">
          <div className="flex-1 h-px bg-ink-800" />
          <span className="text-[11px] text-ink-600 font-mono uppercase tracking-widest shrink-0">or let AI decide</span>
          <div className="flex-1 h-px bg-ink-800" />
        </div>
        <QuickStart />

        {/* Footer note */}
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4, duration: 0.5 }}
          className="mt-8 text-ink-500 text-[12px] text-center"
        >
          Powered by Ollama · Gemini · E2B sandboxes · LangGraph · No paid LLM required
        </motion.div>
      </div>
    </div>
  );
}
