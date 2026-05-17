"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  jobId: string;
  featureColumns: string[];
  targetColumn: string;
  taskType?: string;
  sampleRow?: Record<string, any>;
}

export default function TestModelPanel({ jobId, featureColumns, targetColumn, taskType, sampleRow }: Props) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const col of featureColumns) {
      const v = sampleRow?.[col];
      init[col] = v !== null && v !== undefined ? String(v) : "";
    }
    return init;
  });

  const [result, setResult] = useState<{ prediction: any; probability: number | null } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const features: Record<string, any> = {};
      for (const col of featureColumns) {
        const raw = values[col];
        if (raw === "" || raw === undefined || raw === null) {
          features[col] = null;
        } else {
          const n = Number(raw);
          features[col] = isNaN(n) ? raw : n;
        }
      }
      const res = await fetch(`${API_BASE}/jobs/${jobId}/test-predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(features),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        setError(err.detail || "Prediction failed");
        return;
      }
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const isClassification = taskType === "binary_classification";

  return (
    <div className="max-w-4xl mx-auto px-8 pb-8">
      <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Test Model</h3>
          <p className="text-gray-400 text-xs mt-0.5">
            Pre-filled with a sample row from your dataset. Edit any values and run a prediction — no local setup needed.
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {featureColumns.map((col) => (
            <div key={col}>
              <label className="block text-xs text-gray-400 mb-1 truncate" title={col}>{col}</label>
              <input
                type="text"
                value={values[col] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [col]: e.target.value }))}
                placeholder="null"
                className="w-full bg-gray-700 text-white text-sm rounded-lg px-3 py-2 border border-gray-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
          ))}
        </div>

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Running...
            </>
          ) : "Run Prediction"}
        </button>

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 text-red-400 text-sm">
            {error}
          </div>
        )}

        {result && (
          <div className="bg-gray-700/60 rounded-xl p-5 text-center space-y-1">
            <p className="text-gray-400 text-xs uppercase tracking-wider">{targetColumn} prediction</p>
            <p className="text-5xl font-bold text-white">{String(result.prediction)}</p>
            {isClassification && result.probability !== null && result.probability !== undefined && (
              <p className="text-gray-300 text-sm pt-1">
                Confidence:{" "}
                <span className={`font-semibold ${result.probability > 0.7 ? "text-green-400" : result.probability > 0.4 ? "text-yellow-400" : "text-red-400"}`}>
                  {(result.probability * 100).toFixed(1)}%
                </span>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
