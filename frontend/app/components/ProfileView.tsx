﻿"use client";

import { useMemo, useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ProfileReport } from "@/lib/api";

function NetworkGraph() {
  const nodes = useMemo(() => {
    const arr: { id: string; x: number; y: number; delay: number }[] = [];
    const layers = [3, 5, 5, 3]; let idx = 0;
    layers.forEach((n, li) => {
      for (let i = 0; i < n; i++) {
        arr.push({ id: `${li}-${i}`, x: 60 + li * 120, y: 50 + (i + 1) * (260 / (n + 1)), delay: idx * 0.07 });
        idx++;
      }
    });
    return arr;
  }, []);

  const edges = useMemo(() => {
    const e: { a: typeof nodes[0]; b: typeof nodes[0]; delay: number }[] = [];
    const byLayer: Record<number, typeof nodes> = {};
    nodes.forEach(n => { const li = parseInt(n.id.split("-")[0]); (byLayer[li] ||= []).push(n); });
    Object.keys(byLayer).forEach(li => {
      const next = byLayer[+li + 1];
      if (!next) return;
      byLayer[+li].forEach(a => next.forEach(b => { if (Math.random() < 0.6) e.push({ a, b, delay: Math.max(a.delay, b.delay) + 0.1 }); }));
    });
    return e;
  }, [nodes]);

  return (
    <svg viewBox="0 0 500 320" className="w-full h-full">
      <defs>
        <radialGradient id="ng" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#3B82F6" stopOpacity=".9" />
          <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
        </radialGradient>
      </defs>
      {edges.map((e, i) => (
        <motion.line key={i} x1={e.a.x} y1={e.a.y} x2={e.b.x} y2={e.b.y}
          stroke="rgba(96,165,250,.3)" strokeWidth=".75"
          initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 1 }}
          transition={{ duration: 0.8, delay: e.delay }} />
      ))}
      {nodes.map(n => (
        <motion.g key={n.id} initial={{ opacity: 0, scale: 0 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.4, delay: n.delay, ease: "backOut" }}>
          <circle cx={n.x} cy={n.y} r="13" fill="url(#ng)" />
          <circle cx={n.x} cy={n.y} r="4" fill="#60A5FA" />
          <circle cx={n.x} cy={n.y} r="1.5" fill="white" />
        </motion.g>
      ))}
    </svg>
  );
}

const LOADING_MSGS = [
  "Scanning columns...", "Detecting distributions...", "Computing correlations...",
  "Checking for target leakage...", "Estimating feature importance...", "Finalising profile...",
];

export default function ProfileView({ profile, validationWarnings, leakageWarnings, classImbalanceDetected, imbalanceRatio }: {
  profile?: ProfileReport;
  validationWarnings?: Array<{ severity: string; message: string; column: string }>;
  leakageWarnings?: string[];
  classImbalanceDetected?: boolean;
  imbalanceRatio?: number;
}) {
  const [msgIdx, setMsgIdx] = useState(0);
  const [eta, setEta] = useState(35);
  useEffect(() => {
    const i = setInterval(() => setMsgIdx(v => (v + 1) % LOADING_MSGS.length), 1800);
    const t = setInterval(() => setEta(v => Math.max(2, v - 1)), 1000);
    return () => { clearInterval(i); clearInterval(t); };
  }, []);

  const columns = profile?.columns ?? [];

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
      className="max-w-[1180px] w-full mx-auto px-8 py-6">
      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="eyebrow">03 / phase</div>
          <div className="text-[26px] font-semibold tracking-tight mt-1">Profiling data</div>
          <div className="text-ink-400 text-[13.5px] mt-1.5">Characterising each column, detecting distributions, and assembling a feature graph.</div>
        </div>
        {!profile && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-blue/10 border border-accent-blue/30 text-accent-blueGlow">
            <span className="dot bg-accent-blueGlow pulse-dot" />
            <span className="text-[11px] font-mono">ETA ~{eta}s</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-12 gap-5">
        {/* Left: animated visual */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.05 }}
          className="col-span-12 lg:col-span-7 glass-strong rounded-xl overflow-hidden relative" style={{ height: 380 }}>
          <div className="absolute inset-0 bg-grid-fine opacity-40" />
          {!profile && (
            <div className="absolute inset-0 overflow-hidden">
              {Array.from({ length: 14 }).map((_, i) => (
                <div key={i} className="waterfall-row" style={{
                  top: `${(i / 14) * 100}%`, left: `${(i % 5) * 15}%`,
                  animationDuration: `${7 + (i % 4)}s`, animationDelay: `${-(i * 0.7)}s`,
                }}>
                  {`col_${i % 5}=${(Math.random() * 100).toFixed(2)},label=${i % 2}`}
                </div>
              ))}
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-b from-ink-900/20 via-transparent to-ink-900/70" />
          <div className="absolute inset-0 flex items-center justify-center opacity-60">
            <NetworkGraph />
          </div>
          {!profile && (
            <div className="absolute inset-x-0 bottom-0 px-5 py-4">
              <AnimatePresence mode="wait">
                <motion.div key={msgIdx} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.25 }}
                  className="font-mono text-[12.5px] text-accent-blueGlow flex items-center gap-2">
                  <span className="dot bg-accent-blueGlow pulse-dot" />
                  {LOADING_MSGS[msgIdx]}
                </motion.div>
              </AnimatePresence>
            </div>
          )}
          {profile && (
            <div className="absolute inset-x-0 bottom-0 px-5 py-4">
              <div className="font-mono text-[12px] text-accent-emerald flex items-center gap-2">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                Profile complete - {profile.row_count?.toLocaleString()} rows / {profile.column_count} columns
              </div>
            </div>
          )}
        </motion.div>

        {/* Right: column stats */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.1 }}
          className="col-span-12 lg:col-span-5 glass-strong rounded-xl p-5 overflow-y-auto" style={{ maxHeight: 380 }}>
          <div className="flex items-center justify-between mb-4">
            <div className="eyebrow">Column profiles</div>
            {profile && <div className="font-mono text-[11px] text-ink-500">{profile.column_count} cols / {profile.row_count?.toLocaleString()} rows</div>}
          </div>

          {columns.length === 0 && (
            <div className="space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i}>
                  <div className="h-3 rounded shimmer mb-1.5" style={{ width: `${50 + i * 8}%` }} />
                  <div className="h-1.5 rounded-full shimmer" />
                </div>
              ))}
            </div>
          )}

          <div className="space-y-3">
            {columns.slice(0, 12).map((col, i) => {
              const isLeaky = leakageWarnings?.some(w => w.toLowerCase().includes(col.column.toLowerCase()));
              const nullPct = col.null_pct ?? 0;
              const qualityPct = Math.max(10, 100 - nullPct);
              return (
                <motion.div key={col.column} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.35, delay: 0.1 + i * 0.04 }}>
                  <div className="flex items-center justify-between text-[12px] mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-ink-100">{col.column}</span>
                      <span className="font-mono text-[10px] text-ink-500">{col.dtype}</span>
                      {isLeaky && <span className="px-1.5 py-0.5 rounded bg-accent-amber/10 border border-accent-amber/30 text-accent-amber font-mono text-[9px] uppercase">leak</span>}
                    </div>
                    <div className="font-mono text-ink-400 text-[11px]">
                      {nullPct > 0 ? <span className="text-accent-amber">{col.null_count} null</span> : "clean"}
                    </div>
                  </div>
                  <div className="h-1.5 rounded-full bg-ink-800 overflow-hidden">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${qualityPct}%` }} transition={{ duration: 0.8, delay: 0.2 + i * 0.04 }}
                      className="h-full rounded-full"
                      style={{ background: isLeaky ? "linear-gradient(90deg,#F59E0B,#FBBF24)" : "linear-gradient(90deg,#3B82F6,#10B981)" }} />
                  </div>
                </motion.div>
              );
            })}
          </div>

          {classImbalanceDetected && (
            <div className="mt-4 flex items-start gap-2 rounded-lg px-3 py-2.5 bg-accent-amber/8 border border-accent-amber/25">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="text-accent-amber mt-0.5 shrink-0"><path d="M12 3L22 20H2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M12 10v4M12 17v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
              <div className="text-[11.5px] text-accent-amber">Class imbalance detected{imbalanceRatio ? ` - ratio ${imbalanceRatio.toFixed(2)}` : ""}. Stratified sampling will be applied.</div>
            </div>
          )}
        </motion.div>
      </div>

      {profile?.llm_interpretation && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.2 }}
          className="glass-strong rounded-xl mt-5 px-5 py-4">
          <div className="eyebrow mb-2">Dataset interpretation</div>
          <p className="text-[13px] text-ink-300 leading-relaxed">{profile.llm_interpretation}</p>
        </motion.div>
      )}
    </motion.div>
  );
}


