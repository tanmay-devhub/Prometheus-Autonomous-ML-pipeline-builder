﻿"use client";

import { useState, useCallback } from "react";
import { motion } from "framer-motion";
import { createJob } from "@/lib/api";

const fadeUp = { initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.45 } };

export default function UploadPanel({ onJobCreated }: { onJobCreated: (id: string) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f?.name.endsWith(".csv")) { setFile(f); setError(""); }
    else setError("Please upload a CSV file.");
  }, []);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f?.name.endsWith(".csv")) { setFile(f); setError(""); }
    else setError("Please upload a CSV file.");
  };

  const handleSubmit = async () => {
    if (!file || !description.trim()) { setError("Please provide both a CSV file and a description."); return; }
    setLoading(true); setError("");
    try {
      const { job_id } = await createJob(file, description);
      onJobCreated(job_id);
    } catch (e: any) { setError(e.message || "Failed to create job."); }
    finally { setLoading(false); }
  };

  const canStart = !!file && description.trim().length > 10;

  return (
    <motion.div {...fadeUp} className="max-w-[860px] w-full mx-auto px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="eyebrow mb-1">01 / phase</div>
        <div className="text-[26px] font-semibold tracking-tight">New ML Job</div>
        <div className="text-ink-400 text-[13.5px] mt-1.5">
          Drop a CSV, describe the problem in plain English. Prometheus picks the task, trains contender models, and packages a deployable endpoint.
        </div>
      </div>

      <div className="grid gap-5">
        {/* Dropzone */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.05 }}>
          <label
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            className={`dropzone ${dragging ? "dragging" : ""} rounded-xl block px-7 py-7 cursor-pointer bg-ink-900/40`}>
            <input id="csv-input" type="file" accept=".csv" className="hidden" onChange={handleFile} />
            <div className="flex items-center gap-5">
              <div className={`w-14 h-14 rounded-xl flex items-center justify-center shrink-0 transition-colors ${dragging ? "bg-accent-blue/15 text-accent-blueGlow" : file ? "bg-accent-emerald/15 text-accent-emerald" : "bg-ink-800 text-ink-300"}`}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path d="M12 16V4M12 4l-5 5M12 4l5 5M4 18v2h16v-2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="flex-1">
                {file ? (
                  <div>
                    <div className="flex items-center gap-3">
                      <div className="font-mono text-[13px] text-ink-100">{file.name}</div>
                      <span className="px-2 py-0.5 rounded bg-accent-emerald/10 border border-accent-emerald/30 text-accent-emerald text-[10px] font-mono uppercase tracking-wider">ready</span>
                    </div>
                    <div className="text-[12px] text-ink-400 mt-1 font-mono">{(file.size / 1024).toFixed(1)} KB</div>
                  </div>
                ) : (
                  <div>
                    <div className="text-[14px] text-ink-100 font-medium">Drop CSV here or click to browse</div>
                    <div className="text-[12px] text-ink-400 mt-1">Up to 500 MB . UTF-8 . header row required</div>
                  </div>
                )}
              </div>
              {file && (
                <button onClick={(e) => { e.preventDefault(); setFile(null); }} className="text-ink-500 hover:text-ink-200 p-1.5">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 6L18 18M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                </button>
              )}
            </div>
          </label>
        </motion.div>

        {/* Description */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.1 }}>
          <div className="flex items-center justify-between mb-2">
            <label className="eyebrow">Problem description</label>
            <span className="font-mono text-[11px] text-ink-500">{description.length} / 800</span>
          </div>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value.slice(0, 800))}
            rows={5}
            placeholder="What are you trying to predict? Which column is the target? Any constraints or class-balance concerns..."
            className="w-full bg-ink-900/60 border border-ink-700 rounded-lg px-4 py-3 text-[13.5px] text-ink-100 placeholder-ink-500 resize-none font-sans leading-relaxed focus:border-accent-blue/50 transition-colors"
          />
        </motion.div>

        {/* Pipeline preview */}
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.15 }}
          className="rounded-lg bg-ink-900/40 border border-ink-700/60 px-5 py-4">
          <div className="eyebrow mb-3">Pipeline / 6 steps</div>
          <div className="flex items-center gap-1.5 flex-wrap">
            {["Analyze CSV", "Profile data", "Approve plan", "Run experiments", "Select model", "Generate endpoint"].map((s, i) => (
              <div key={s} className="flex items-center gap-1.5">
                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-ink-800/60 border border-ink-700/60">
                  <span className="font-mono text-[10px] text-ink-500">0{i + 1}</span>
                  <span className="text-[11.5px] text-ink-200">{s}</span>
                </div>
                {i < 5 && <span className="text-ink-600 text-[11px]">-&gt;</span>}
              </div>
            ))}
          </div>
        </motion.div>

        {error && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-accent-rose/10 border border-accent-rose/30 text-accent-rose text-[13px]">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M12 3L22 20H2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M12 10v4M12 17v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
            {error}
          </div>
        )}

        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.2 }}
          className="flex items-center justify-between pt-1">
          <div className="text-[12px] text-ink-400">Estimated <span className="text-ink-200 font-mono">3-8 min</span> total pipeline time</div>
          <button onClick={handleSubmit} disabled={loading || !canStart}
            className="inline-flex items-center gap-2 px-5 py-3 rounded-md font-medium text-[14px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-40 disabled:cursor-not-allowed bg-accent-blue hover:bg-accent-blueDim border-accent-blue/40 text-white shadow-glow-blue">
            {loading ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,.3)" strokeWidth="2" fill="none"/><path d="M12 3a9 9 0 0 1 9 9" stroke="white" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>
                Starting...
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14l7 0L11 22 20 10 13 10Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>
                Start Pipeline
              </>
            )}
          </button>
        </motion.div>
      </div>
    </motion.div>
  );
}


