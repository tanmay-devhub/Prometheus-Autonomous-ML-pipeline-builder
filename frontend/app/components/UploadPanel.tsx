"use client";

import { useState, useCallback } from "react";
import { createJob } from "@/lib/api";

interface Props {
  onJobCreated: (jobId: string) => void;
}

export default function UploadPanel({ onJobCreated }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [description, setDescription] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".csv")) setFile(dropped);
    else setError("Please upload a CSV file.");
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0];
    if (selected?.name.endsWith(".csv")) {
      setFile(selected);
      setError("");
    } else {
      setError("Please upload a CSV file.");
    }
  };

  const handleSubmit = async () => {
    if (!file || !description.trim()) {
      setError("Please provide both a CSV file and a description.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { job_id } = await createJob(file, description);
      onJobCreated(job_id);
    } catch (e: any) {
      setError(e.message || "Failed to create job.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold text-white mb-2">Prometheus</h1>
      <p className="text-gray-400 mb-8">Autonomous ML Pipeline Builder</p>

      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors mb-6
          ${dragging ? "border-blue-500 bg-blue-500/10" : "border-gray-600 hover:border-gray-400"}
          ${file ? "border-green-500 bg-green-500/10" : ""}`}
        onClick={() => document.getElementById("csv-input")?.click()}
      >
        <input
          id="csv-input"
          type="file"
          accept=".csv"
          className="hidden"
          onChange={handleFileChange}
        />
        {file ? (
          <div>
            <p className="text-green-400 text-lg font-medium">{file.name}</p>
            <p className="text-gray-400 text-sm mt-1">{(file.size / 1024).toFixed(1)} KB</p>
          </div>
        ) : (
          <div>
            <p className="text-gray-300 text-lg">Drop your CSV file here</p>
            <p className="text-gray-500 text-sm mt-2">or click to browse</p>
          </div>
        )}
      </div>

      <textarea
        className="w-full bg-gray-800 border border-gray-600 rounded-xl p-4 text-gray-200 placeholder-gray-500 resize-none h-32 focus:outline-none focus:border-blue-500 mb-6"
        placeholder="Describe what you want to predict. Example: Predict whether a customer will churn in the next 30 days based on their usage history."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={loading || !file || !description.trim()}
        className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <span className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
            Starting pipeline...
          </>
        ) : (
          "Build ML Pipeline"
        )}
      </button>
    </div>
  );
}
