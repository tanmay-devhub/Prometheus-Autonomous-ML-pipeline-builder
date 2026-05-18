"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function DebugLog({ debugLog }: { debugLog: any[] }) {
  const [open, setOpen] = useState<Record<number, boolean>>({});

  if (!debugLog?.length) return null;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
      className="max-w-[1280px] w-full mx-auto px-8 pb-6">
      <div className="rounded-xl bg-ink-900/40 border border-ink-700/40 overflow-hidden">
        <div className="px-5 py-3 border-b border-ink-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="dot bg-accent-blue" />
            <span className="text-[13px] font-medium text-ink-100">Debug log</span>
            <span className="font-mono text-[11px] text-ink-500">{debugLog.length} entries</span>
          </div>
        </div>

        {debugLog.map((entry, i) => {
          const isOpen = open[i];
          const sev = entry.phase === "failed" || entry.error ? "err"
            : entry.phase?.includes("retry") || entry.warning ? "warn"
            : "ok";
          const title = entry.message || entry.phase || entry.timestamp || `Entry ${i + 1}`;
          const ts = entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString("en", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
          const payload = { ...entry };
          delete payload.timestamp;

          return (
            <div key={i} className="border-b border-ink-800 last:border-b-0">
              <button onClick={() => setOpen({ ...open, [i]: !isOpen })}
                className="w-full flex items-center gap-4 px-5 py-3 hover:bg-ink-800/30 transition-colors text-left">
                <span className={`shrink-0 text-ink-400 transition-transform ${isOpen ? "rotate-180" : ""}`}>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none"><path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </span>
                <span className={`px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider border shrink-0 ${
                  sev === "err"  ? "bg-accent-rose/10 text-accent-rose border-accent-rose/30"
                  : sev === "warn" ? "bg-accent-amber/10 text-accent-amber border-accent-amber/30"
                  : "bg-accent-blue/10 text-accent-blueGlow border-accent-blue/30"}`}>
                  {entry.phase || "log"}
                </span>
                {ts && <span className="font-mono text-[11px] text-ink-500 shrink-0">{ts}</span>}
                <span className="text-[12.5px] text-ink-100 flex-1 truncate">{String(title)}</span>
              </button>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }}
                    className="overflow-hidden bg-[#070A12]">
                    <pre className="px-12 py-3 font-mono text-[11px] text-ink-300 leading-relaxed whitespace-pre-wrap overflow-x-auto">
                      {JSON.stringify(payload, null, 2)}
                    </pre>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}


