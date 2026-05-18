"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ScatterChart, Scatter, XAxis, YAxis, ReferenceLine,
  Tooltip, ResponsiveContainer, Cell, ZAxis,
} from "recharts";

// ── Normalize target values ("Yes"/"No", "True"/"False", 0/1, etc.) ───────────
function normalizeTarget(val: any): number | null {
  if (val == null) return null;
  const s = String(val).toLowerCase().trim();
  if (s === "yes" || s === "true"  || s === "1" || s === "1.0") return 1;
  if (s === "no"  || s === "false" || s === "0" || s === "0.0") return 0;
  const n = Number(val);
  return isNaN(n) ? null : n;
}

// ── CountUp ────────────────────────────────────────────────────────────────────
function CountUp({ to, decimals = 1, suffix = "" }: { to: number; decimals?: number; suffix?: string }) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    const start = performance.now();
    let raf: number;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 900);
      setVal(to * (1 - Math.pow(1 - t, 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <span>{val.toFixed(decimals)}{suffix}</span>;
}

// ── Prediction history entry ────────────────────────────────────────────────────
interface PredEntry {
  idx: number;
  probability: number;
  predictionRaw: any;         // raw value from API (0, 1, "Yes", "No", ...)
  predictionNorm: number;     // normalized to 0/1 for comparison
  actual: number | null;      // normalized to 0/1 for comparison & plot coloring
  actualRaw: string | null;   // original CSV label for display
  correct: boolean | null;
  unseen: boolean;
}

// ── Scatter plot ───────────────────────────────────────────────────────────────
function PredictionPlot({ history, targetColumn, labelMap }: { history: PredEntry[]; targetColumn: string; labelMap: Record<number, string> }) {
  if (history.length === 0) return null;

  const data = history.map((h) => ({
    x: h.idx, y: h.probability, actual: h.actual, actualRaw: h.actualRaw, correct: h.correct, unseen: h.unseen,
  }));

  const CustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    if (cx == null || cy == null) return null;
    const fill   = payload.actual === 1 ? "#10B981" : payload.actual === 0 ? "#5A6985" : "#3B82F6";
    const stroke = payload.correct === true ? "#10B981" : payload.correct === false ? "#F43F5E" : "#3B82F6";
    if (payload.unseen) {
      // Diamond: rotated square — more reliable than <polygon> in Recharts
      const s = 10;
      return (
        <g transform={`translate(${cx},${cy}) rotate(45)`}>
          <rect x={-s / 2} y={-s / 2} width={s} height={s}
            fill={fill} fillOpacity={0.9} stroke={stroke} strokeWidth={2.5} />
        </g>
      );
    }
    return <circle cx={cx} cy={cy} r={6} fill={fill} fillOpacity={0.85} stroke={stroke} strokeWidth={2} />;
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="glass-strong rounded-lg px-3 py-2 text-[11px] font-mono space-y-0.5">
        <div className="text-ink-200">Sample #{d.x}{d.unseen ? <span className="ml-1.5 text-accent-amber">unseen</span> : ""}</div>
        <div className="text-accent-blueGlow">prob: {d.y.toFixed(3)}</div>
        {d.actual !== null && <div className={d.actual === 1 ? "text-accent-emerald" : "text-ink-400"}>actual: {d.actualRaw ?? d.actual}</div>}
        {d.correct !== null && <div className={d.correct ? "text-accent-emerald" : "text-accent-rose"}>{d.correct ? "correct" : "wrong"}</div>}
      </div>
    );
  };

  const unseenCount = history.filter(h => h.unseen).length;
  const correctCount = history.filter(h => h.correct === true).length;
  const totalKnown = history.filter(h => h.correct !== null).length;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
      className="glass-strong rounded-xl p-5 mb-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="eyebrow mb-0.5">Prediction confidence</div>
          <div className="text-[12px] text-ink-400 flex items-center gap-3 flex-wrap">
            <span>Circle = in-sample &nbsp; <span className="text-accent-amber">Diamond = unseen</span></span>
            <span className="text-ink-600">|</span>
            <span>Fill: <span className="text-accent-emerald">{labelMap[1] ?? "1"}</span> / <span className="text-ink-300">{labelMap[0] ?? "0"}</span> / <span className="text-accent-blue">unknown</span></span>
            <span className="text-ink-600">|</span>
            <span>Border: <span className="text-accent-emerald">correct</span> / <span className="text-accent-rose">wrong</span></span>
          </div>
        </div>
        <div className="text-right font-mono text-[11px] text-ink-500 space-y-0.5">
          <div>{history.length} prediction{history.length !== 1 ? "s" : ""}{unseenCount > 0 ? ` (${unseenCount} unseen)` : ""}</div>
          {totalKnown > 0 && <div className={correctCount / totalKnown >= 0.5 ? "text-accent-emerald" : "text-accent-rose"}>{correctCount}/{totalKnown} correct ({Math.round(correctCount / totalKnown * 100)}%)</div>}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={165}>
        <ScatterChart margin={{ top: 10, right: 80, bottom: 18, left: 0 }}>
          <XAxis dataKey="x" type="number" name="Sample" tick={{ fill: "#5A6985", fontSize: 10, fontFamily: "JetBrains Mono" }}
            label={{ value: "Sample #", position: "insideBottom", offset: -6, fill: "#5A6985", fontSize: 10 }} />
          <YAxis dataKey="y" type="number" name="Probability" domain={[0, 1]}
            tick={{ fill: "#5A6985", fontSize: 10, fontFamily: "JetBrains Mono" }}
            label={{ value: "P(1)", angle: -90, position: "insideLeft", fill: "#5A6985", fontSize: 10 }} />
          <ZAxis range={[60, 60]} />
          <ReferenceLine y={0.5} stroke="rgba(251,191,36,.6)" strokeDasharray="4 4"
            label={{ value: "0.5 threshold", position: "right", fill: "#FBBF24", fontSize: 9, fontFamily: "JetBrains Mono" }} />
          <Tooltip content={<CustomTooltip />} cursor={false} />
          <Scatter data={data} shape={<CustomDot />} />
        </ScatterChart>
      </ResponsiveContainer>
    </motion.div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
interface Props {
  jobId: string;
  featureColumns: string[];
  targetColumn: string;
  taskType?: string;
  sampleRow?: Record<string, any>;
  sampleRows?: Record<string, any>[];
  heldOutRows?: Record<string, any>[];
}

export default function TestModelPanel({ jobId, featureColumns, targetColumn, taskType, sampleRow, sampleRows = [], heldOutRows = [] }: Props) {
  const [inputs, setInputs] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    featureColumns.forEach(c => { init[c] = sampleRow?.[c] != null ? String(sampleRow[c]) : ""; });
    return init;
  });
  const [result, setResult] = useState<{ prediction: number; probability?: number; target_column: string } | null>(null);
  const [actual, setActual] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [ripple, setRipple] = useState<{ x: number; y: number; id: number } | null>(null);
  const [history, setHistory] = useState<PredEntry[]>([]);
  const [sampleIdx, setSampleIdx] = useState<number | null>(null);
  const [classFilter, setClassFilter] = useState<string | null>(null); // raw label e.g. "Yes", "0"
  const [useUnseen, setUseUnseen] = useState(false);

  // Show RAW labels from the CSV — "Yes"/"No", "0"/"1", whatever the data contains.
  const availableClasses = useMemo(() => {
    const vals = new Set<string>();
    sampleRows.forEach(r => {
      if (r[targetColumn] != null) vals.add(String(r[targetColumn]));
    });
    const arr = Array.from(vals);
    const allNumeric = arr.every(v => !isNaN(Number(v)));
    return allNumeric ? arr.sort((a, b) => Number(a) - Number(b)) : arr.sort();
  }, [sampleRows, targetColumn]);

  // Reverse map: normalized 0/1 → original label ("No"/"Yes") for decoding predictions
  const labelMap = useMemo(() => {
    const m: Record<number, string> = {};
    availableClasses.forEach(cls => {
      const n = normalizeTarget(cls);
      if (n !== null && !(n in m)) m[n] = cls;
    });
    return m;
  }, [availableClasses]);

  const runPrediction = useCallback(async (e: React.MouseEvent<HTMLButtonElement>, overrideInputs?: Record<string, string>, overrideActual?: number | null) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setRipple({ x: e.clientX - rect.left, y: e.clientY - rect.top, id: Date.now() });
    setRunning(true); setResult(null); setError("");
    const payload = overrideInputs ?? inputs;
    try {
      const res = await fetch(`http://localhost:8000/jobs/${jobId}/test-predict`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data);
      const act = overrideActual !== undefined ? overrideActual : actual;
      const prob = data.probability ?? (data.prediction === 1 ? 0.9 : 0.1);
      // Normalize both sides: the API may return 0/1 OR "Yes"/"No"
      const predNorm = normalizeTarget(data.prediction) ?? data.prediction;
      const isCorrect = act !== null ? predNorm === act : null;
      setHistory(h => [...h, {
        idx: h.length + 1, probability: prob,
        predictionRaw: data.prediction, predictionNorm: predNorm,
        actual: act, actualRaw: null, correct: isCorrect, unseen: false,
      }]);
    } catch (e: any) { setError(e.message || "Prediction failed."); }
    finally { setRunning(false); }
  }, [inputs, actual, jobId]);

  const pickRandom = useCallback(async (e: React.MouseEvent<HTMLButtonElement>) => {
    const basePool = useUnseen ? (heldOutRows.length > 0 ? heldOutRows : sampleRows) : sampleRows;
    if (basePool.length === 0) return;

    // Stratified pick: count how many times each class has been picked in history,
    // then prefer the under-represented class to ensure balanced exploration.
    const classCounts: Record<number, number> = {};
    history.forEach(h => {
      if (h.actual !== null) classCounts[h.actual] = (classCounts[h.actual] ?? 0) + 1;
    });

    // Group by RAW label string — preserves "Yes"/"No", "0"/"1", etc.
    const byClass: Record<string, typeof basePool> = {};
    basePool.forEach(r => {
      const key = r[targetColumn] != null ? String(r[targetColumn]) : "__unknown__";
      (byClass[key] ||= []).push(r);
    });

    let pool = basePool;

    if (classFilter !== null) {
      // User pinned a specific raw label
      const pinned = byClass[classFilter];
      pool = pinned && pinned.length > 0 ? pinned : basePool;
    } else {
      // Auto-alternate: normalize raw labels → 0/1 to look up counts, pick under-represented
      const classes = Object.keys(byClass).filter(k => k !== "__unknown__");
      if (classes.length >= 2) {
        const minClass = classes.reduce((least, cls) => {
          const normCls   = normalizeTarget(cls)   ?? 0;
          const normLeast = normalizeTarget(least)  ?? 0;
          return (classCounts[normCls] ?? 0) < (classCounts[normLeast] ?? 0) ? cls : least;
        }, classes[0]);
        pool = byClass[minClass].length > 0 ? byClass[minClass] : basePool;
      }
    }

    const row = pool[Math.floor(Math.random() * pool.length)];
    const newInputs: Record<string, string> = {};
    featureColumns.forEach(c => { newInputs[c] = row[c] != null ? String(row[c]) : ""; });
    const newActual    = normalizeTarget(row[targetColumn]);          // 0/1 for comparison
    const newActualRaw = row[targetColumn] != null ? String(row[targetColumn]) : null; // "Yes"/"No" for display
    setInputs(newInputs);
    setActual(newActual);
    setSampleIdx(sampleRows.indexOf(row));
    setResult(null);
    // Auto-run prediction
    const rect = e.currentTarget.getBoundingClientRect();
    setRipple({ x: e.clientX - rect.left, y: e.clientY - rect.top, id: Date.now() + 1 });
    setRunning(true); setError("");
    try {
      const res = await fetch(`http://localhost:8000/jobs/${jobId}/test-predict`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newInputs),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setResult(data);
      const prob = data.probability ?? (data.prediction === 1 ? 0.9 : 0.1);
      const predNorm = normalizeTarget(data.prediction) ?? data.prediction;
      const isCorrect = newActual !== null ? predNorm === newActual : null;
      setHistory(h => [...h, {
        idx: h.length + 1, probability: prob,
        predictionRaw: data.prediction, predictionNorm: predNorm,
        actual: newActual, actualRaw: newActualRaw, correct: isCorrect, unseen: useUnseen,
      }]);
    } catch (e: any) { setError(e.message || "Prediction failed."); }
    finally { setRunning(false); }
  }, [sampleRows, heldOutRows, featureColumns, targetColumn, jobId, classFilter, useUnseen]);

  const cols = featureColumns.slice(0, 12);
  // Normalize the raw prediction (could be 0/1 or "Yes"/"No") to 0/1
  const predNormResult = result != null ? (normalizeTarget(result.prediction) ?? result.prediction) : null;
  const isPositive = predNormResult === 1;
  const isCorrect = result && actual !== null ? predNormResult === actual : null;
  // Labels for display (use raw labels if available, fall back to 0/1)
  const predLabel = result != null ? (labelMap[predNormResult as number] ?? String(result.prediction)) : null;
  const actualLabel = (history[history.length - 1]?.actualRaw) ?? (actual !== null ? (labelMap[actual] ?? String(actual)) : null);

  return (
    <div>
      <PredictionPlot history={history} targetColumn={targetColumn} labelMap={labelMap} />

      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }}
        className="glass-strong rounded-2xl p-6">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-accent-blue/15 border border-accent-blue/40 flex items-center justify-center text-accent-blueGlow">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M6 4L20 12L6 20Z" fill="currentColor"/></svg>
            </div>
            <div>
              <div className="text-[15px] font-semibold tracking-tight">Test the model</div>
              <div className="text-[12px] text-ink-400 mt-0.5">Run predictions and compare against actual values from your dataset</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {sampleRows.length > 0 && (
              <div className="flex items-center gap-1.5">
                {/* Pool selector: in-sample vs held-out */}
                <div className="flex items-center rounded-md border border-ink-700 overflow-hidden">
                  <button onClick={() => { setUseUnseen(false); setClassFilter(null); }}
                    className={`px-2.5 py-1.5 text-[11px] font-mono font-medium transition-colors border-r border-ink-700 ${!useUnseen && classFilter === null ? "bg-accent-violet/25 text-accent-violet" : "text-ink-400 hover:text-ink-200 hover:bg-ink-800/60"}`}>
                    Any
                  </button>
                  {availableClasses.map(cls => {
                    const isActive = !useUnseen && classFilter === cls;
                    const isPositiveClass = normalizeTarget(cls) === 1;
                    return (
                      <button key={cls}
                        onClick={() => { setUseUnseen(false); setClassFilter(isActive ? null : cls); }}
                        className={`px-2.5 py-1.5 text-[11px] font-mono font-medium transition-colors border-r border-ink-700 ${
                          isActive
                            ? isPositiveClass ? "bg-accent-emerald/20 text-accent-emerald" : "bg-ink-600/40 text-ink-200"
                            : "text-ink-400 hover:text-ink-200 hover:bg-ink-800/60"
                        }`}>
                        {cls}
                      </button>
                    );
                  })}
                  {heldOutRows.length > 0 && (
                    <button onClick={() => { setUseUnseen(u => !u); setClassFilter(null); }}
                      className={`px-2.5 py-1.5 text-[11px] font-mono font-medium transition-colors ${
                        useUnseen ? "bg-accent-amber/20 text-accent-amber" : "text-ink-400 hover:text-ink-200 hover:bg-ink-800/60"
                      }`}>
                      Unseen
                    </button>
                  )}
                </div>
                {/* Random sample trigger */}
                <button onClick={pickRandom} disabled={running}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md font-medium text-[12px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-40 ${
                    useUnseen
                      ? "bg-accent-amber/15 hover:bg-accent-amber/25 border-accent-amber/40 text-accent-amber"
                      : "bg-accent-violet/15 hover:bg-accent-violet/25 border-accent-violet/40 text-accent-violet"
                  }`}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                    <path d="M4 4h4v4H4zM16 4h4v4h-4zM4 16h4v4H4zM10 10h4v4h-4z" fill="currentColor" opacity=".7"/>
                    <path d="M16 16h4v4h-4z" fill="currentColor"/>
                  </svg>
                  {useUnseen ? "Sample unseen" : classFilter !== null ? `Sample "${classFilter}"` : "Random"}
                </button>
              </div>
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
                  className="w-full bg-ink-900/60 border border-ink-700 rounded-md px-2.5 py-2 text-[12.5px] text-ink-100 font-mono hover:border-accent-blue/40 transition-colors" />
              </div>
            ))}
          </div>
        )}

        {actual !== null && (
          <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
            <span className="eyebrow text-[9px]">actual {targetColumn}</span>
            <span className={`font-mono text-[14px] font-semibold ${actual === 1 ? "text-accent-emerald" : "text-ink-300"}`}>{actualLabel ?? actual}</span>
            <span className="text-ink-600 text-[11px] ml-auto font-mono">from dataset sample</span>
          </div>
        )}

        <div className="flex items-center justify-between">
          <button onClick={(e) => runPrediction(e)} disabled={running}
            className="relative overflow-hidden inline-flex items-center gap-2 px-4 py-2.5 rounded-md font-medium text-[13px] tracking-tight border transition-all active:scale-[.98] disabled:opacity-40 bg-accent-blue hover:bg-accent-blueDim border-accent-blue/40 text-white shadow-glow-blue">
            {running ? (
              <><svg width="13" height="13" viewBox="0 0 24 24" className="spin-slow"><circle cx="12" cy="12" r="9" stroke="rgba(255,255,255,.3)" strokeWidth="2" fill="none"/><path d="M12 3a9 9 0 0 1 9 9" stroke="white" strokeWidth="2" strokeLinecap="round" fill="none"/></svg>Predicting...</>
            ) : (
              <><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14l7 0L11 22 20 10 13 10Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/></svg>Run Prediction</>
            )}
            {ripple && (
              <motion.span key={ripple.id} initial={{ width: 0, height: 0, opacity: 0.6 }} animate={{ width: 400, height: 400, opacity: 0 }}
                transition={{ duration: 0.8 }} onAnimationComplete={() => setRipple(null)}
                className="absolute rounded-full bg-white pointer-events-none"
                style={{ left: ripple.x, top: ripple.y, transform: "translate(-50%,-50%)" }} />
            )}
          </button>
          <span className="font-mono text-[10.5px] text-ink-500">target: {targetColumn}</span>
        </div>

        {error && <div className="mt-4 text-accent-rose text-[13px] font-mono">{error}</div>}

        <AnimatePresence mode="wait">
          {result && (
            <motion.div key={String(history.length)} initial={{ opacity: 0, scale: 0.9, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.45 }}
              className="mt-5 rounded-xl p-5 overflow-hidden"
              style={{
                background: isPositive ? "linear-gradient(135deg,rgba(244,63,94,.12),rgba(244,63,94,.04))" : "linear-gradient(135deg,rgba(16,185,129,.12),rgba(16,185,129,.04))",
                border: `1px solid ${isPositive ? "rgba(244,63,94,.35)" : "rgba(16,185,129,.35)"}`,
              }}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="eyebrow">Predicted / {targetColumn}</div>
                  <motion.div initial={{ scale: 0, rotate: -8 }} animate={{ scale: 1, rotate: 0 }} transition={{ type: "spring", stiffness: 200, damping: 14 }}
                    className={`font-mono font-bold text-[40px] leading-none mt-2 ${isPositive ? "text-accent-rose" : "text-accent-emerald"}`}>
                    {predLabel}
                  </motion.div>
                  {actual !== null && (
                    <div className="mt-2 flex items-center gap-2">
                      <span className="eyebrow text-[9px]">actual</span>
                      <span className={`font-mono text-[16px] font-semibold ${actual === 1 ? "text-accent-emerald" : "text-ink-300"}`}>{actualLabel}</span>
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
                {result.probability != null && (
                  <div className="text-right">
                    <div className="eyebrow">confidence</div>
                    <div className={`font-mono font-semibold text-[30px] mt-1 ${isPositive ? "text-accent-rose" : "text-accent-emerald"}`}>
                      <CountUp to={result.probability * 100} decimals={1} suffix="%" />
                    </div>
                  </div>
                )}
              </div>
              {result.probability != null && (
                <div className="mt-4">
                  <div className="h-2 rounded-full bg-ink-800 overflow-hidden">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${result.probability * 100}%` }} transition={{ duration: 1.0, delay: 0.15 }}
                      className="h-full rounded-full"
                      style={{ background: isPositive ? "linear-gradient(90deg,#F43F5E,#FB7185)" : "linear-gradient(90deg,#10B981,#34D399)" }} />
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
