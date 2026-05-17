"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { ProfileReport } from "@/lib/api";

interface Warning {
  severity: string;
  message: string;
  column: string;
}

interface Props {
  profile: ProfileReport;
  validationWarnings: Warning[];
  leakageWarnings: string[];
  classImbalanceDetected: boolean;
  imbalanceRatio?: number;
}

const SEVERITY_ICON: Record<string, string> = {
  block: "🔴",
  warn: "🟡",
  info: "🔵",
};

const SEVERITY_BG: Record<string, string> = {
  block: "bg-red-900/40 border-red-700",
  warn: "bg-yellow-900/40 border-yellow-700",
  info: "bg-blue-900/40 border-blue-700",
};

export default function ProfileView({
  profile, validationWarnings, leakageWarnings, classImbalanceDetected, imbalanceRatio,
}: Props) {
  const targetChartData = Object.entries(profile.target_distribution || {}).map(([k, v]) => ({
    name: String(k),
    count: typeof v === "number" ? v : 0,
  }));

  const llmBullets = (profile.llm_interpretation || "")
    .split("\n")
    .filter((l) => l.trim().startsWith("-") || l.trim().startsWith("•") || l.trim().startsWith("*"))
    .map((l) => l.replace(/^[-•*]\s*/, "").trim())
    .filter(Boolean);

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-white mb-1">Data Profile</h2>
        <p className="text-gray-400">
          {profile.row_count.toLocaleString()} rows · {profile.column_count} columns ·{" "}
          {profile.duplicate_count} duplicates ({profile.duplicate_pct}%)
        </p>
      </div>

      {llmBullets.length > 0 && (
        <div className="bg-blue-900/30 border border-blue-700 rounded-xl p-5">
          <p className="text-blue-300 font-semibold mb-3">Key Insights</p>
          <ul className="space-y-1">
            {llmBullets.map((b, i) => (
              <li key={i} className="text-blue-200 text-sm flex gap-2">
                <span className="text-blue-400 mt-0.5">›</span> {b}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700 text-gray-400">
              <th className="text-left py-3 pr-4">Column</th>
              <th className="text-left py-3 pr-4">Type</th>
              <th className="text-right py-3 pr-4">Null %</th>
              <th className="text-right py-3 pr-4">Unique</th>
              <th className="text-left py-3">Range / Top Values</th>
            </tr>
          </thead>
          <tbody>
            {profile.columns.map((col) => (
              <tr key={col.column} className="border-b border-gray-800 hover:bg-gray-800/40">
                <td className="py-3 pr-4 text-white font-mono text-xs">{col.column}</td>
                <td className="py-3 pr-4 text-gray-400">{col.dtype}</td>
                <td className={`py-3 pr-4 text-right font-medium ${col.null_pct > 50 ? "text-red-400" : col.null_pct > 10 ? "text-yellow-400" : "text-green-400"}`}>
                  {col.null_pct}%
                </td>
                <td className="py-3 pr-4 text-right text-gray-300">{col.unique_count}</td>
                <td className="py-3 text-gray-400 text-xs">
                  {col.min !== undefined
                    ? `${col.min?.toFixed(2)} – ${col.max?.toFixed(2)}`
                    : Object.entries(col.top_values || {}).slice(0, 3).map(([k, v]) => `${k}(${v})`).join(", ")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {targetChartData.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-3">Target Distribution</h3>
          {classImbalanceDetected && (
            <p className="text-yellow-400 text-sm mb-3">
              Class imbalance detected (ratio: {imbalanceRatio?.toFixed(3)})
            </p>
          )}
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={targetChartData}>
              <XAxis dataKey="name" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip contentStyle={{ background: "#1f2937", border: "1px solid #374151" }} />
              <Bar dataKey="count" fill="#3b82f6" radius={4} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {(validationWarnings.length > 0 || leakageWarnings.length > 0) && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-3">Warnings</h3>
          <div className="space-y-2">
            {leakageWarnings.map((w, i) => (
              <div key={`leak-${i}`} className="flex gap-2 items-start p-3 rounded-lg bg-red-900/40 border border-red-700 text-sm">
                <span>⚠️</span>
                <span className="text-red-300">[LEAKAGE] {w}</span>
              </div>
            ))}
            {validationWarnings.map((w, i) => (
              <div key={i} className={`flex gap-2 items-start p-3 rounded-lg border text-sm ${SEVERITY_BG[w.severity] || SEVERITY_BG.info}`}>
                <span>{SEVERITY_ICON[w.severity] || "ℹ️"}</span>
                <span className="text-gray-200">{w.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
