"use client";

// Matches actual backend pipeline order
const STAGES = [
  { id: "analyze",    label: "Analyze" },
  { id: "approve",    label: "Approve" },
  { id: "profile",    label: "Profile" },
  { id: "experiment", label: "Experiment" },
  { id: "select",     label: "Select Model" },
  { id: "generate",   label: "Generate" },
  { id: "complete",   label: "Complete" },
];

const VIEW_TO_STAGE: Record<string, number> = {
  awaiting_problem_approval: 1,
  profiling:                 2,
  experiments:               3,
  awaiting_model_approval:   4,
  results:                   5,
  endpoint:                  6,
};

export default function PipelineProgress({ view }: { view: string; phase?: string }) {
  const activeIndex = VIEW_TO_STAGE[view] ?? 0;

  return (
    <div className="w-full px-8 pt-5 pb-4">
      <div className="flex items-center w-full max-w-[1280px] mx-auto">
        {STAGES.map((s, i) => {
          const done   = i < activeIndex;
          const active = i === activeIndex;
          return (
            <div key={s.id} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center">
                <div className={[
                  "w-8 h-8 rounded-full flex items-center justify-center transition-all duration-300",
                  done   ? "bg-accent-emerald/15 border border-accent-emerald/60"
                         : active ? "bg-accent-blue/15 border border-accent-blue/70 pulse-ring"
                         : "bg-ink-850 border border-ink-700",
                ].join(" ")}>
                  {done ? (
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                      <path d="M5 12.5L10 17L19 7" stroke="#10B981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  ) : active ? (
                    <span className="w-2 h-2 rounded-full bg-accent-blue pulse-dot" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-ink-600" />
                  )}
                </div>
                <div className={[
                  "mt-1.5 text-[10px] font-medium whitespace-nowrap",
                  done ? "text-accent-emerald" : active ? "text-ink-100" : "text-ink-500",
                ].join(" ")}>
                  <span className="font-mono text-ink-600 mr-1">{String(i + 1).padStart(2, "0")}</span>
                  {s.label}
                </div>
              </div>
              {i < STAGES.length - 1 && (
                <div className="flex-1 h-px relative mx-2 mb-5">
                  <div className="absolute inset-0 bg-ink-700" />
                  {i < activeIndex && (
                    <div className="absolute inset-0 liquid-pour"
                      style={{ background: "linear-gradient(90deg,rgba(16,185,129,.9),rgba(59,130,246,.9))", boxShadow: "0 0 8px rgba(59,130,246,.5)" }} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
