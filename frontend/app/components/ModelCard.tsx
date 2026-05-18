"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

function Gauge({ value }: { value: number }) {
  const r = 70, cx = 90, cy = 90;
  const pct = Math.min(1, Math.max(0, value));
  const arcLen = 270 * Math.PI / 180 * r;
  const filledLen = arcLen * pct;
  const polar = (deg: number) => ({ x: cx + r * Math.cos(deg * Math.PI / 180), y: cy + r * Math.sin(deg * Math.PI / 180) });
  const descArc = (a1: number, a2: number) => {
    const s = polar(a1), e = polar(a2);
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${a2 - a1 > 180 ? 1 : 0} 1 ${e.x} ${e.y}`;
  };
  return (
    <svg width="180" height="120" viewBox="0 0 180 130">
      <defs>
        <linearGradient id="gGrad" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#3B82F6" /><stop offset="100%" stopColor="#10B981" />
        </linearGradient>
      </defs>
      <path d={descArc(-135, 135)} className="gauge-track" strokeWidth="10" fill="none" strokeLinecap="round" />
      <motion.path d={descArc(-135, 135)} className="gauge-fill" strokeWidth="10" fill="none" strokeLinecap="round"
        strokeDasharray={`${filledLen} ${arcLen}`}
        initial={{ strokeDasharray: `0 ${arcLen}` }}
        animate={{ strokeDasharray: `${filledLen} ${arcLen}` }}
        transition={{ duration: 1.3 }} />
      <circle cx={cx} cy={cy} r="5" fill="#EEF1F7" /><circle cx={cx} cy={cy} r="2" fill="#0A0E1A" />
      <text x={cx} y={cy + 26} textAnchor="middle" fill="#EEF1F7" fontFamily="JetBrains Mono,monospace" fontWeight="600" fontSize="16">{value.toFixed(3)}</text>
    </svg>
  );
}

function Accordion({ title, children, open: defaultOpen }: { title: string; children: React.ReactNode; open?: boolean }) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <div className="border-b border-ink-800 last:border-b-0">
      <button onClick={() => setOpen(o => !o)} className="w-full flex items-center justify-between py-3 text-left hover:bg-ink-800/30 px-1 -mx-1 rounded transition-colors">
        <span className="text-[13px] font-medium text-ink-100">{title}</span>
        <span className={`text-ink-400 transition-transform ${open ? "rotate-180" : ""}`}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }} className="overflow-hidden">
            <div className="pb-3 pt-1 text-[12.5px] text-ink-300 leading-relaxed whitespace-pre-wrap">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default function ModelCard({ modelCard, plainExplanation, shapFeatures, winningJustification }: {
  modelCard?: string;
  plainExplanation?: string;
  shapFeatures?: Array<{ feature: string; importance: number }>;
  winningJustification?: string;
}) {
  const metricMatch = modelCard?.match(/(\d+\.\d+)/);
  const metricValue = metricMatch ? parseFloat(metricMatch[1]) : 0;

  const sections = modelCard
    ? modelCard.split(/\n#{1,3} /).filter(Boolean).map(s => {
        const lines = s.split("\n");
        return { title: lines[0].replace(/^#+\s*/, "").trim(), body: lines.slice(1).join("\n").trim() };
      }).filter(s => s.title && s.body)
    : [];

  const topFeatures = shapFeatures?.slice(0, 6) ?? [];
  const maxImp = topFeatures[0]?.importance ?? 1;

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.1 }}
      className="glass-strong rounded-2xl p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent-emerald/15 border border-accent-emerald/40 flex items-center justify-center text-accent-emerald">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight">Model card</div>
            <div className="text-[12px] text-ink-400 mt-0.5">Performance, limits, intended use</div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-5">
        {metricValue > 0 && (
          <div className="col-span-12 md:col-span-4 flex flex-col items-center justify-center bg-ink-900/40 rounded-xl border border-ink-700/60 py-5">
            <div className="eyebrow mb-1">Primary metric</div>
            <Gauge value={metricValue} />
          </div>
        )}

        <div className={`col-span-12 ${metricValue > 0 ? "md:col-span-8" : ""}`}>
          {sections.length > 0 ? (
            <>
              <Accordion title="Performance" open>{sections.find(s => /perf|metric|score/i.test(s.title))?.body ?? sections[0]?.body}</Accordion>
              {sections.slice(1).map((s, i) => <Accordion key={i} title={s.title}>{s.body}</Accordion>)}
            </>
          ) : modelCard ? (
            <div className="text-[12.5px] text-ink-300 leading-relaxed whitespace-pre-wrap">{modelCard}</div>
          ) : null}

          {plainExplanation && (
            <Accordion title="Plain-English Explanation" open={!sections.length}>{plainExplanation}</Accordion>
          )}
          {winningJustification && (
            <Accordion title="Selection Justification">{winningJustification}</Accordion>
          )}
        </div>
      </div>

      {topFeatures.length > 0 && (
        <div className="mt-5 pt-5 border-t border-ink-800">
          <div className="eyebrow mb-3">Top features (SHAP)</div>
          <div className="space-y-2">
            {topFeatures.map((f, i) => (
              <div key={f.feature} className="flex items-center gap-3">
                <div className="font-mono text-[11px] text-ink-200 w-28 truncate shrink-0">{f.feature}</div>
                <div className="flex-1 h-1.5 rounded-full bg-ink-800 overflow-hidden">
                  <motion.div initial={{ width: 0 }} animate={{ width: `${(f.importance / maxImp) * 100}%` }}
                    transition={{ duration: 0.8, delay: 0.05 * i }}
                    className="h-full rounded-full" style={{ background: "linear-gradient(90deg,#3B82F6,#10B981)" }} />
                </div>
                <div className="font-mono text-[11px] text-ink-400 w-14 text-right shrink-0">{f.importance.toFixed(4)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}


