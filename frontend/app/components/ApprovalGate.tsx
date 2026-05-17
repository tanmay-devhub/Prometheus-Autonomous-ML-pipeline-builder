"use client";

import { useState } from "react";
import { approveProblem } from "@/lib/api";

interface Warning {
  severity: string;
  message: string;
  column: string;
}

interface Props {
  jobId: string;
  taskType: string;
  targetColumn: string;
  metric: string;
  confidence?: number;
  allColumns: string[];
  validationWarnings: Warning[];
  leakageWarnings: string[];
  onApproved: () => void;
}

const SEVERITY_COLORS: Record<string, string> = {
  block: "bg-red-900 text-red-300 border border-red-700",
  warn: "bg-yellow-900 text-yellow-300 border border-yellow-700",
  info: "bg-blue-900 text-blue-300 border border-blue-700",
};

export default function ApprovalGate({
  jobId, taskType, targetColumn, metric, confidence,
  allColumns, validationWarnings, leakageWarnings, onApproved,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [editedTarget, setEditedTarget] = useState(targetColumn);
  const [editedTaskType, setEditedTaskType] = useState(taskType);
  const [loading, setLoading] = useState(false);

  const handleApprove = async () => {
    setLoading(true);
    try {
      const corrections = editing ? { target_column: editedTarget, task_type: editedTaskType } : undefined;
      await approveProblem(jobId, true, corrections);
      onApproved();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h2 className="text-2xl font-bold text-white mb-6">Problem Analysis — Review & Approve</h2>

      <div className="bg-gray-800 rounded-xl p-6 mb-6 space-y-4">
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Task Type</span>
          {editing ? (
            <select
              className="bg-gray-700 text-white rounded px-3 py-1"
              value={editedTaskType}
              onChange={(e) => setEditedTaskType(e.target.value)}
            >
              <option value="binary_classification">Binary Classification</option>
              <option value="regression">Regression</option>
            </select>
          ) : (
            <span className="text-white font-medium">{taskType}</span>
          )}
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Target Column</span>
          {editing ? (
            <select
              className="bg-gray-700 text-white rounded px-3 py-1"
              value={editedTarget}
              onChange={(e) => setEditedTarget(e.target.value)}
            >
              {allColumns.map((col) => (
                <option key={col} value={col}>{col}</option>
              ))}
            </select>
          ) : (
            <span className="text-white font-medium font-mono">{targetColumn}</span>
          )}
        </div>
        <div className="flex justify-between items-center">
          <span className="text-gray-400">Evaluation Metric</span>
          <span className="text-white font-medium">{metric}</span>
        </div>
        {confidence !== undefined && (
          <div className="flex justify-between items-center">
            <span className="text-gray-400">Confidence</span>
            <span className={`font-medium ${confidence >= 0.7 ? "text-green-400" : "text-yellow-400"}`}>
              {(confidence * 100).toFixed(0)}%
            </span>
          </div>
        )}
      </div>

      {leakageWarnings.length > 0 && (
        <div className="mb-4 p-4 bg-red-900/50 border border-red-700 rounded-xl">
          <p className="text-red-300 font-semibold mb-2">Data Leakage Detected</p>
          {leakageWarnings.map((w, i) => (
            <p key={i} className="text-red-400 text-sm">{w}</p>
          ))}
        </div>
      )}

      {validationWarnings.length > 0 && (
        <div className="mb-6 space-y-2">
          <p className="text-gray-400 text-sm font-medium">Validation Warnings</p>
          {validationWarnings.map((w, i) => (
            <div key={i} className={`px-3 py-2 rounded-lg text-sm ${SEVERITY_COLORS[w.severity] || SEVERITY_COLORS.info}`}>
              [{w.severity.toUpperCase()}] {w.message}
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleApprove}
          disabled={loading}
          className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 text-white font-semibold py-3 rounded-xl transition-colors"
        >
          {loading ? "Approving..." : "Looks Correct — Continue"}
        </button>
        <button
          onClick={() => setEditing(!editing)}
          className="px-6 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 rounded-xl transition-colors"
        >
          {editing ? "Done Editing" : "Edit"}
        </button>
      </div>
    </div>
  );
}
