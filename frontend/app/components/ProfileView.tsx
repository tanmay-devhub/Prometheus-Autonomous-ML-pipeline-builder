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
          className="mt-5 rounded-xl overflow-hidden border border-ink-700/60"
          style={{ background: "linear-gradient(135deg,rgba(15,23,42,.95),rgba(15,23,42,.80))" }}>
          <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-ink-700/50"
            style={{ background: "linear-gradient(90deg,rgba(59,130,246,.08),transparent)" }}>
            <div className="w-6 h-6 rounded-md bg-accent-blue/15 border border-accent-blue/30 flex items-center justify-center text-accent-blueGlow shrink-0">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 15v-4m0-4V9" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="12" cy="9" r="1" fill="currentColor"/>
              </svg>
            </div>
            <div className="eyebrow text-[9px] text-accent-blueGlow tracking-widest">Dataset Interpretation</div>
            <div className="ml-auto flex items-center gap-1.5">
              <span className="dot bg-accent-blueGlow" style={{ width: 5, height: 5 }} />
              <span className="font-mono text-[10px] text-ink-500">LLM analysis</span>
            </div>
          </div>
          <div className="p-5 grid gap-2.5">
            {profile.llm_interpretation
              .split(/\n|(?=\*\s)/)
              .map(line => line.replace(/^[\*\-•]\s+/, "").trim())
              .filter(Boolean)
              .map((line, i) => {
                const m = line.match(/^\*{0,2}(.+?):{0,1}\*{0,2}\s+(.+)$/);
                const label = m ? m[1].replace(/\*+/g, "").trim() : "";
                const detail = m ? m[2] : line;
                const icons = ["M9 12l2 2 4-4M12 3v1m0 16v1M3 12h1m16 0h1","M13 16h-1v-4h-1m1-4h.01","M12 9v3m0 0v3m0-3h3m-3 0H9","M3 6l3 1M3 6v13M21 18V5M21 18l-3-1","M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"];
                const colors = ["#3B82F6","#10B981","#F59E0B","#8B5CF6","#F43F5E"];
                const c = colors[i % colors.length];
                return (
                  <motion.div key={i} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.35, delay: 0.05 * i }}
                    className="flex items-start gap-3 rounded-lg px-4 py-3 border"
                    style={{ background: `${c}08`, borderColor: `${c}20` }}>
                    <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                      style={{ background: `${c}15`, border: `1px solid ${c}30` }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" style={{ color: c }}>
                        <path d={icons[i % icons.length]} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      {label && <span className="text-[12.5px] font-semibold mr-1.5" style={{ color: c }}>{label}:</span>}
                      <span className="text-[12.5px] text-ink-300 leading-relaxed">{detail}</span>
                    </div>
                  </motion.div>
                );
              })}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}


