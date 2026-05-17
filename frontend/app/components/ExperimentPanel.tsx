"use client";

import { ExperimentResult } from "@/lib/api";

interface Props {
  experiments: ExperimentResult[];
  evaluationMetric?: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; pulse: boolean }> = {
  success: { label: "Success", color: "text-green-400", pulse: false },
  failed: { label: "Failed", color: "text-red-400", pulse: false },
  running: { label: "Running", color: "text-blue-400", pulse: true },
  retrying: { label: "Retrying", color: "text-yellow-400", pulse: true },
  queued: { label: "Queued", color: "text-gray-400", pulse: false },
};

function getStatus(exp: ExperimentResult): string {
  if (exp.success) return "success";
  if (exp.retry_count > 0 && !exp.success) return "retrying";
  if (exp.exit_code === -1 && !exp.stdout && !exp.stderr) return "queued";
  return "failed";
}

function ExperimentCard({
  experiment,
  evaluationMetric,
  label,
}: {
  experiment: ExperimentResult;
  evaluationMetric?: string;
  label: string;
}) {
  const status = getStatus(experiment);
  const cfg = STATUS_CONFIG[status];
  const metricKey = evaluationMetric || Object.keys(experiment.parsed_metrics)[0];
  const metricValue = experiment.parsed_metrics[metricKey];

  return (
    <div className="bg-gray-800 rounded-xl p-6 flex flex-col gap-4">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">{label}</p>
          <h3 className="text-white font-semibold text-lg">{experiment.architecture_name}</h3>
        </div>
        <div className={`flex items-center gap-2 ${cfg.color}`}>
          {cfg.pulse && (
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-current" />
            </span>
          )}
          <span className="text-sm font-medium">{cfg.label}</span>
        </div>
      </div>

      {metricValue !== undefined && (
        <div className="bg-gray-700/50 rounded-lg p-4 text-center">
          <p className="text-gray-400 text-xs mb-1">{metricKey?.toUpperCase()}</p>
          <p className="text-white text-3xl font-bold">{metricValue.toFixed(4)}</p>
        </div>
      )}

      <div className="flex justify-between text-sm">
        <span className="text-gray-400">Retries</span>
        <span className={`font-medium ${experiment.retry_count > 0 ? "text-yellow-400" : "text-gray-300"}`}>
          {experiment.retry_count} / 3
        </span>
      </div>

      {experiment.failure_type && !experiment.success && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3">
          <p className="text-red-400 text-xs">Last failure: {experiment.failure_type}</p>
        </div>
      )}

      {experiment.fix_history.length > 0 && (
        <div className="space-y-1">
          <p className="text-gray-500 text-xs">Fix history</p>
          {experiment.fix_history.map((fix, i) => (
            <div key={i} className="text-xs text-gray-400 bg-gray-700/50 rounded px-2 py-1">
              Retry {fix.retry}: {fix.failure_type}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ExperimentPanel({ experiments, evaluationMetric }: Props) {
  if (experiments.length === 0) {
    return (
      <div className="max-w-4xl mx-auto p-8">
        <h2 className="text-2xl font-bold text-white mb-6">Experiments</h2>
        <div className="grid grid-cols-2 gap-6">
          {[0, 1].map((i) => (
            <div key={i} className="bg-gray-800 rounded-xl p-6 animate-pulse">
              <div className="h-4 bg-gray-700 rounded w-1/2 mb-4" />
              <div className="h-20 bg-gray-700 rounded mb-4" />
              <div className="h-4 bg-gray-700 rounded w-1/3" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h2 className="text-2xl font-bold text-white mb-6">Experiments</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {experiments.map((exp, i) => (
          <ExperimentCard
            key={exp.experiment_id}
            experiment={exp}
            evaluationMetric={evaluationMetric}
            label={`Experiment ${String.fromCharCode(65 + i)}`}
          />
        ))}
      </div>
    </div>
  );
}
