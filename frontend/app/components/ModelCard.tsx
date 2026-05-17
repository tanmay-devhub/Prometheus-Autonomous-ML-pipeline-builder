"use client";

import ReactMarkdown from "react-markdown";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface ShapFeature {
  feature: string;
  importance: number;
}

interface Props {
  modelCard: string;
  plainExplanation: string;
  shapFeatures: ShapFeature[];
  winningJustification?: string;
}

export default function ModelCard({ modelCard, plainExplanation, shapFeatures, winningJustification }: Props) {
  const maxImportance = Math.max(...shapFeatures.map((f) => f.importance), 0.001);
  const chartData = shapFeatures.slice(0, 10).map((f) => ({
    name: f.feature.length > 20 ? f.feature.slice(0, 20) + "…" : f.feature,
    importance: parseFloat(f.importance.toFixed(4)),
  }));

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8">
      <h2 className="text-2xl font-bold text-white">Model Results</h2>

      {winningJustification && (
        <div className="bg-green-900/30 border border-green-700 rounded-xl p-5">
          <p className="text-green-300 font-semibold mb-1">Selection Rationale</p>
          <p className="text-green-200 text-sm">{winningJustification}</p>
        </div>
      )}

      {plainExplanation && (
        <div className="bg-purple-900/30 border border-purple-700 rounded-xl p-5">
          <p className="text-purple-300 font-semibold mb-2">Plain English Explanation</p>
          <p className="text-purple-100 text-sm leading-relaxed">{plainExplanation}</p>
        </div>
      )}

      {chartData.length > 0 && (
        <div>
          <h3 className="text-lg font-semibold text-white mb-4">Feature Importance (SHAP)</h3>
          <ResponsiveContainer width="100%" height={chartData.length * 36 + 40}>
            <BarChart data={chartData} layout="vertical">
              <XAxis type="number" stroke="#9ca3af" domain={[0, maxImportance * 1.1]} />
              <YAxis type="category" dataKey="name" width={140} stroke="#9ca3af" tick={{ fontSize: 12 }} />
              <Tooltip
                contentStyle={{ background: "#1f2937", border: "1px solid #374151" }}
                formatter={(v: number) => [v.toFixed(4), "Importance"]}
              />
              <Bar dataKey="importance" radius={4}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={`hsl(${220 - i * 15}, 70%, 55%)`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-gray-800 rounded-xl p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Model Card</h3>
        <div className="prose prose-invert prose-sm max-w-none">
          <ReactMarkdown>{modelCard}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
