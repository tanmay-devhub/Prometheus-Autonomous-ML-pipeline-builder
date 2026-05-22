"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";

interface Props {
  modelCard: string;
  plainExplanation: string;
  shapFeatures: { feature: string; importance: number }[];
  winningJustification: string;
  rmse: number;
  mae: number;
  mape: number;
  forecastHorizon: number;
  frequency: string;
  trainEndDate: string;
  testEndDate: string;
}

function MapeBar({ value }: { value: number }) {
  const pct = Math.min(value, 100);
  const color = value < 10 ? "#10b981" : value < 20 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 rounded-full bg-ink-800 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono text-[12px] w-14 text-right" style={{ color }}>
        {value.toFixed(1)}%
      </span>
    </div>
  );
}

export default function TimeSeriesModelCard({
  modelCard, plainExplanation, shapFeatures, winningJustification,
  rmse, mae, mape, forecastHorizon, frequency, trainEndDate, testEndDate,
}: Props) {
  const [cardOpen, setCardOpen] = useState(false);

  const maxImportance = Math.max(...shapFeatures.map(f => f.importance), 1);

  return (
    <div className="space-y-5">
      {/* Metrics summary */}
      <div className="rounded-2xl bg-ink-900/60 border border-ink-700 p-5">
        <div className="eyebrow text-[9px] mb-3">model performance</div>
        <div className="grid grid-cols-3 gap-5 mb-5">
          {[
            { label: "MAPE", value: mape ? `${mape.toFixed(1)}%` : "—", color: mape < 10 ? "#10b981" : mape < 20 ? "#f59e0b" : "#f43f5e" },
            { label: "RMSE", value: rmse?.toFixed(4) ?? "—", color: "#60a5fa" },
            { label: "MAE", value: mae?.toFixed(4) ?? "—", color: "#a78bfa" },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl bg-ink-800/60 border border-ink-700/60 px-4 py-3 text-center">
              <div className="eyebrow text-[9px] mb-1">{label}</div>
              <div className="text-[24px] font-semibold font-mono" style={{ color }}>{value}</div>
              {label === "MAPE" && (
                <div className="text-[10px] text-ink-500 mt-1">avg % error</div>
              )}
            </div>
          ))}
        </div>

        {/* MAPE visual */}
        {mape > 0 && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11.5px] text-ink-400">Prediction accuracy (MAPE)</span>
              <span className="text-[10.5px] text-ink-500">
                {mape < 10 ? "Excellent" : mape < 20 ? "Good" : mape < 30 ? "Acceptable" : "Poor"}
              </span>
            </div>
            <MapeBar value={mape} />
          </div>
        )}

        <div className="text-[11.5px] text-ink-400 bg-ink-800/40 rounded-lg px-3 py-2">
          On average, predictions are{" "}
          <span className="text-ink-200 font-medium">{mape ? `${mape.toFixed(1)}%` : "N/A"}</span> away from actual values.
          Forecast horizon: <span className="text-ink-200 font-medium">{forecastHorizon} {frequency} steps</span> ahead.
          Test period ended: <span className="text-ink-200 font-mono text-[10.5px]">{testEndDate || "N/A"}</span>.
        </div>
      </div>

      {/* Plain explanation */}
      {plainExplanation && (
        <div className="rounded-2xl bg-ink-900/60 border border-ink-700 overflow-hidden">
          <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-ink-800"
            style={{ background: "linear-gradient(90deg,rgba(16,185,129,.06),transparent)" }}>
            <div className="w-5 h-5 rounded-md bg-accent-emerald/15 border border-accent-emerald/30 flex items-center justify-center">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" className="text-accent-emerald">
                <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2"/>
                <path d="M12 8v4M12 16h.01" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
            </div>
            <span className="text-[12px] font-semibold text-ink-200">AI explanation</span>
            <span className="ml-auto px-2 py-0.5 rounded-full bg-accent-emerald/10 border border-accent-emerald/20 text-[9px] font-mono text-accent-emerald">
              LLM analysis
            </span>
          </div>
          <div className="px-5 py-4 text-[13px] text-ink-300 leading-relaxed">
            {plainExplanation}
          </div>
        </div>
      )}

      {/* AI justification */}
      {winningJustification && (
        <div className="rounded-xl bg-ink-800/40 border border-ink-700/60 px-4 py-3">
          <div className="eyebrow text-[9px] mb-1.5">model selection reasoning</div>
          <p className="text-[12.5px] text-ink-300 leading-relaxed">{winningJustification}</p>
        </div>
      )}

      {/* SHAP feature importance */}
      {shapFeatures.length > 0 && (
        <div className="rounded-2xl bg-ink-900/60 border border-ink-700 overflow-hidden">
          <div className="px-5 py-3.5 border-b border-ink-800">
            <div className="eyebrow text-[9px] mb-0.5">feature importance (SHAP)</div>
            <div className="text-[13px] font-semibold">What drives the forecast</div>
          </div>
          <div className="px-5 py-4 space-y-3">
            {shapFeatures.filter(f => !f.feature?.startsWith?.("error")).map((f, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-[11px] text-ink-300">{f.feature}</span>
                  <span className="font-mono text-[11px] text-ink-500">{f.importance.toFixed(4)}</span>
                </div>
                <div className="h-1.5 rounded-full bg-ink-800">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-accent-emerald to-accent-emerald/60 transition-all duration-500"
                    style={{ width: `${(f.importance / maxImportance) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Collapsible model card */}
      {modelCard && (
        <div className="rounded-2xl bg-ink-900/60 border border-ink-700 overflow-hidden">
          <button
            onClick={() => setCardOpen(v => !v)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-ink-800/40 transition-colors"
          >
            <div>
              <div className="eyebrow text-[9px] mb-0.5">documentation</div>
              <div className="text-[13px] font-semibold text-left">Model card</div>
            </div>
            <svg
              width="16" height="16" viewBox="0 0 24 24" fill="none"
              className={`text-ink-500 transition-transform duration-200 ${cardOpen ? "rotate-180" : ""}`}
            >
              <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          {cardOpen && (
            <div className="px-5 pb-5 border-t border-ink-800 prose prose-sm prose-invert max-w-none pt-4 text-[13px]">
              <ReactMarkdown>{modelCard}</ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
