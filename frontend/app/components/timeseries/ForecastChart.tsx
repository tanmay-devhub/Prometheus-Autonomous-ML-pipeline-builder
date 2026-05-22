"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ReferenceLine, ResponsiveContainer,
} from "recharts";

interface HistoryData {
  train_dates: string[];
  train_actuals: number[];
  test_dates: string[];
  test_actuals: number[];
  test_predictions: number[];
  split_date: string;
  rmse: number;
  mae: number;
  mape: number;
}

interface ForecastData {
  forecast: number[];
  forecast_dates: string[];
  forecast_horizon: number;
  rmse?: number;
  mae?: number;
  mape?: number;
}

interface Props {
  history: HistoryData | null;
  forecast: ForecastData | null;
  targetColumn: string;
  frequency: string;
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  } catch {
    return dateStr;
  }
}

function buildChartData(history: HistoryData | null, forecast: ForecastData | null) {
  const data: any[] = [];

  if (history) {
    const trainCount = history.train_dates.length;
    const keepLast = Math.min(trainCount, 60);

    for (let i = trainCount - keepLast; i < trainCount; i++) {
      data.push({
        date: history.train_dates[i],
        actual: history.train_actuals[i],
        predicted: null,
        forecast: null,
        region: "train",
      });
    }

    for (let i = 0; i < history.test_dates.length; i++) {
      data.push({
        date: history.test_dates[i],
        actual: history.test_actuals[i],
        predicted: history.test_predictions[i],
        forecast: null,
        region: "test",
      });
    }
  }

  if (forecast) {
    for (let i = 0; i < forecast.forecast.length; i++) {
      data.push({
        date: forecast.forecast_dates[i] || `+${i + 1}`,
        actual: null,
        predicted: null,
        forecast: forecast.forecast[i],
        region: "forecast",
      });
    }
  }

  return data;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-ink-900 border border-ink-700 rounded-lg px-3 py-2 text-[11.5px] shadow-xl">
      <div className="text-ink-400 mb-1 font-mono">{label}</div>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-ink-300">{p.name}:</span>
          <span className="text-ink-100 font-mono">{typeof p.value === "number" ? p.value.toFixed(3) : "—"}</span>
        </div>
      ))}
    </div>
  );
};

export default function ForecastChart({ history, forecast, targetColumn, frequency }: Props) {
  const data = buildChartData(history, forecast);

  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-[320px] text-ink-500 text-[13px]">
        Chart data not yet available
      </div>
    );
  }

  const splitDate = history?.split_date || "";

  // Only show every Nth x-axis label to avoid crowding
  const tickInterval = Math.max(1, Math.floor(data.length / 8));

  return (
    <div className="w-full">
      {history && (
        <div className="flex items-center gap-5 mb-4 text-[11.5px] text-ink-400">
          <div className="flex items-center gap-1.5">
            <span className="w-8 h-0.5 bg-blue-400 inline-block" />
            <span>Actual (train)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-8 h-0.5 bg-emerald-400 inline-block" />
            <span>Predicted (test)</span>
          </div>
          {forecast && (
            <div className="flex items-center gap-1.5">
              <span className="w-8 h-0.5 border-t-2 border-dashed border-amber-400 inline-block" />
              <span>Forecast (future)</span>
            </div>
          )}
          {splitDate && (
            <div className="flex items-center gap-1.5">
              <span className="w-0.5 h-3 bg-ink-500 inline-block" />
              <span>Train/test split</span>
            </div>
          )}
        </div>
      )}

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={{ stroke: "rgba(255,255,255,.08)" }}
            interval={tickInterval}
            tickFormatter={formatDate}
          />
          <YAxis
            tick={{ fill: "#64748b", fontSize: 10, fontFamily: "monospace" }}
            tickLine={false}
            axisLine={false}
            width={60}
          />
          <Tooltip content={<CustomTooltip />} />

          {splitDate && (
            <ReferenceLine
              x={splitDate}
              stroke="rgba(148,163,184,.35)"
              strokeDasharray="4 4"
              label={{ value: "split", position: "top", fill: "#64748b", fontSize: 9 }}
            />
          )}

          <Line
            type="monotone"
            dataKey="actual"
            stroke="#60a5fa"
            strokeWidth={1.5}
            dot={false}
            name="Actual"
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#34d399"
            strokeWidth={2}
            dot={false}
            name="Predicted"
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="forecast"
            stroke="#fbbf24"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={false}
            name="Forecast"
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>

      {(history || forecast) && (() => {
        // Prefer forecast metrics (from state/winning experiment) — history PKL may not store them
        const rmse = (history?.rmse && history.rmse > 0) ? history.rmse : (forecast?.rmse ?? 0);
        const mae  = (history?.mae  && history.mae  > 0) ? history.mae  : (forecast?.mae  ?? 0);
        const mape = (history?.mape && history.mape > 0) ? history.mape : (forecast?.mape ?? 0);
        return (
          <div className="flex items-center gap-6 mt-4 pt-3 border-t border-ink-800">
            {[
              { label: "RMSE", value: rmse > 0 ? rmse.toFixed(4) : "—" },
              { label: "MAE",  value: mae  > 0 ? mae.toFixed(4)  : "—" },
              { label: "MAPE", value: mape > 0 ? `${mape.toFixed(1)}%` : "—" },
            ].map(({ label, value }) => (
              <div key={label} className="text-center">
                <div className="eyebrow text-[9px]">{label}</div>
                <div className="font-mono text-[14px] text-accent-emerald font-semibold">{value}</div>
              </div>
            ))}
            <div className="ml-auto text-[11px] text-ink-500">
              On average, predictions are{" "}
              <span className="text-ink-300 font-medium">
                {mape > 0 ? `${mape.toFixed(1)}%` : "N/A"}
              </span>{" "}
              away from actual values
            </div>
          </div>
        );
      })()}
    </div>
  );
}
