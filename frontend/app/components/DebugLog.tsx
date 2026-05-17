"use client";

import { useState } from "react";

interface Props {
  debugLog: any[];
}

export default function DebugLog({ debugLog }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="max-w-4xl mx-auto px-8 pb-4">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-gray-400 hover:text-gray-200 transition-colors text-sm font-medium py-2"
      >
        <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>›</span>
        Debug Log ({debugLog.length} entries)
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 max-h-96 overflow-y-auto">
          {debugLog.map((entry, i) => (
            <div key={i} className="bg-gray-800 border border-gray-700 rounded-lg p-4 text-xs">
              <div className="flex gap-4 mb-2">
                <span className="text-blue-400 font-medium">{entry.phase}</span>
                {entry.timestamp && (
                  <span className="text-gray-500">{new Date(entry.timestamp).toLocaleTimeString()}</span>
                )}
                {entry.retries_used !== undefined && (
                  <span className="text-yellow-400">{entry.retries_used} retries</span>
                )}
              </div>
              <pre className="text-gray-300 whitespace-pre-wrap break-all">
                {JSON.stringify(
                  Object.fromEntries(
                    Object.entries(entry).filter(([k]) => !["phase", "timestamp"].includes(k))
                  ),
                  null,
                  2
                )}
              </pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
