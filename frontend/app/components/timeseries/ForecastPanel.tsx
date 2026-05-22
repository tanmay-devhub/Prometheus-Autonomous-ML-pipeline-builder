"use client";

import { useState, useCallback } from "react";

interface Props {
  forecastValues: number[];
  forecastDates: string[];
  targetColumn: string;
  frequency: string;
}

export default function ForecastPanel({ forecastValues, forecastDates, targetColumn, frequency }: Props) {
  const [showAll, setShowAll] = useState(false);

  const displayRows = showAll ? forecastValues : forecastValues.slice(0, 15);

  const downloadCsv = useCallback(() => {
    const rows = ["date,forecast"].concat(
      forecastValues.map((v, i) => `${forecastDates[i] || `step_${i + 1}`},${v}`)
    );
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `forecast_${targetColumn}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [forecastValues, forecastDates, targetColumn]);

  if (!forecastValues?.length) return null;

  return (
    <div className="rounded-2xl bg-ink-900/60 border border-ink-700 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-ink-800">
        <div>
          <div className="eyebrow text-[9px]">forecast output</div>
          <div className="text-[14px] font-semibold mt-0.5">
            Next {forecastValues.length} {frequency} values — {targetColumn}
          </div>
        </div>
        <button
          onClick={downloadCsv}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[11.5px] font-medium border border-ink-700 text-ink-300 hover:border-ink-500 hover:text-ink-100 hover:bg-ink-800/60 transition-all"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Download CSV
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-ink-800">
              <th className="text-left px-5 py-2.5 text-[10px] font-medium text-ink-500 uppercase tracking-wider w-12">#</th>
              <th className="text-left px-5 py-2.5 text-[10px] font-medium text-ink-500 uppercase tracking-wider">Date</th>
              <th className="text-right px-5 py-2.5 text-[10px] font-medium text-ink-500 uppercase tracking-wider">Forecasted Value</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((val, i) => (
              <tr key={i} className="border-b border-ink-800/50 hover:bg-ink-800/30 transition-colors">
                <td className="px-5 py-2 font-mono text-[11px] text-ink-600">{i + 1}</td>
                <td className="px-5 py-2 font-mono text-[12px] text-ink-300">
                  {forecastDates[i] || `Step +${i + 1}`}
                </td>
                <td className="px-5 py-2 font-mono text-[13px] text-accent-emerald text-right font-semibold">
                  {typeof val === "number" ? val.toFixed(4) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {forecastValues.length > 15 && (
        <div className="px-5 py-3 border-t border-ink-800 text-center">
          <button
            onClick={() => setShowAll(v => !v)}
            className="text-[12px] text-ink-400 hover:text-ink-200 transition-colors"
          >
            {showAll
              ? "Show less"
              : `Show all ${forecastValues.length} rows`}
          </button>
        </div>
      )}
    </div>
  );
}
