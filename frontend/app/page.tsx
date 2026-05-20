"use client";

import { motion } from "framer-motion";
import { useRouter } from "next/navigation";

const card = { initial: { opacity: 0, y: 20 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.4 } };

export default function Landing() {
  const router = useRouter();

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden relative">
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />

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
          <div className="eyebrow text-[9.5px] -mt-px">autonomous ml pipeline · v2</div>
        </div>
      </div>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 py-12">
        <motion.div
          initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <div className="eyebrow mb-3">choose your task</div>
          <h1 className="text-[32px] font-semibold tracking-tight mb-3">What are you building?</h1>
          <p className="text-ink-400 text-[14px] max-w-[420px] mx-auto leading-relaxed">
            Describe your problem, upload a CSV, and Prometheus autonomously designs, trains, and deploys a model.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 w-full max-w-[780px]">
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
                Predict categories and binary outcomes.
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
        </div>

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
