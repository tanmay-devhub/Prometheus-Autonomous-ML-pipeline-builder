"use client";

const STEPS = [
  { key: "analyze",    label: "Analyze" },
  { key: "profile",    label: "Profile" },
  { key: "experiment", label: "Experiment" },
  { key: "select",     label: "Select Model" },
  { key: "output",     label: "Generate Output" },
  { key: "complete",   label: "Complete" },
];

const VIEW_TO_STEP: Record<string, number> = {
  awaiting_problem_approval: 0,
  profiling:                 1,
  experiments:               2,
  awaiting_model_approval:   3,
  results:                   4,
  endpoint:                  5,
};

const PHASE_MESSAGES: Record<string, string> = {
  initializing:              "Starting pipeline...",
  awaiting_problem_approval: "Review the problem analysis below.",
  profiling:                 "Profiling dataset columns and distributions...",
  profiling_complete:        "Profile complete. Designing pipelines...",
  design_complete:           "Pipeline designed. Launching sandbox experiments...",
  resuming:                  "Resuming pipeline...",
  running:                   "Running experiments in E2B sandbox — this takes 2–4 min...",
  experiments_complete:      "Experiments finished. Selecting best model...",
  awaiting_model_approval:   "Experiments complete. Review and approve a model.",
  model_approved:            "Generating documentation and endpoint...",
  documentation_complete:    "Almost done — building deployment endpoint...",
  generating_outputs:        "Generating outputs...",
  complete:                  "Pipeline complete.",
};

interface Props {
  view: string;
  phase?: string;
}

export default function PipelineProgress({ view, phase }: Props) {
  // When pipeline is just starting, force step 0 regardless of the view that was set
  const PHASE_STEP_OVERRIDE: Record<string, number> = { initializing: 0, resuming: 0 };
  const activeStep =
    phase && PHASE_STEP_OVERRIDE[phase] !== undefined
      ? PHASE_STEP_OVERRIDE[phase]
      : VIEW_TO_STEP[view] ?? -1;
  const statusMessage = phase ? (PHASE_MESSAGES[phase] ?? phase) : null;
  const isRunning = view !== "endpoint" && view !== "failed" && view !== "upload";

  return (
    <div className="border-b border-gray-800 bg-gray-900/60 px-8 py-4">
      {/* Step tracker */}
      <div className="flex items-center gap-0 max-w-3xl mx-auto">
        {STEPS.map((step, i) => {
          const done    = i < activeStep;
          const active  = i === activeStep;
          const pending = i > activeStep;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`
                    w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                    transition-all duration-300
                    ${done    ? "bg-green-500 text-white"                           : ""}
                    ${active  ? "bg-blue-500 text-white ring-4 ring-blue-500/30"   : ""}
                    ${pending ? "bg-gray-700 text-gray-500"                        : ""}
                  `}
                >
                  {done ? (
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <span
                  className={`text-[10px] font-medium whitespace-nowrap
                    ${done    ? "text-green-400" : ""}
                    ${active  ? "text-blue-400"  : ""}
                    ${pending ? "text-gray-600"  : ""}
                  `}
                >
                  {step.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-px mx-2 mb-5 transition-colors duration-300
                    ${i < activeStep ? "bg-green-500" : "bg-gray-700"}
                  `}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Status message + spinner */}
      {statusMessage && (
        <div className="flex items-center justify-center gap-2 mt-3">
          {isRunning && (
            <div className="w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          )}
          <span className="text-gray-400 text-xs">{statusMessage}</span>
        </div>
      )}
    </div>
  );
}
