"use client";

import { useState } from "react";

interface Props {
  endpointCode: string;
  requirements: string;
  jobId: string;
}

export default function EndpointViewer({ endpointCode, requirements, jobId }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(endpointCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const blob = new Blob([endpointCode], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "endpoint.py";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadModel = () => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    window.open(`${apiBase}/jobs/${jobId}/model.pkl`, "_blank");
  };

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-white">Generated FastAPI Endpoint</h2>
        <div className="flex gap-3">
          <button
            onClick={handleCopy}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
          <button
            onClick={handleDownload}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
          >
            Download endpoint.py
          </button>
          <button
            onClick={handleDownloadModel}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition-colors"
          >
            Download model.pkl
          </button>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700 bg-gray-800">
          <span className="w-3 h-3 rounded-full bg-red-500" />
          <span className="w-3 h-3 rounded-full bg-yellow-500" />
          <span className="w-3 h-3 rounded-full bg-green-500" />
          <span className="ml-2 text-gray-400 text-sm">endpoint.py</span>
        </div>
        <pre className="p-5 overflow-x-auto text-sm text-gray-300 max-h-[600px] overflow-y-auto leading-relaxed">
          <code>{endpointCode}</code>
        </pre>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-white mb-3">requirements.txt</h3>
        <pre className="bg-gray-800 border border-gray-700 rounded-xl p-4 text-sm text-gray-300 whitespace-pre-wrap">
          {requirements}
        </pre>
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-4">
        <h3 className="text-lg font-semibold text-white">Deployment Instructions</h3>

        <div className="space-y-3 text-sm text-gray-300">
          <div>
            <p className="text-gray-400 font-medium mb-1">Step 1 — Create a folder and download both files</p>
            <pre className="bg-gray-900 rounded p-3 text-xs text-gray-300 overflow-x-auto">{`mkdir my_model
cd my_model
# Click "Download endpoint.py" and "Download model.pkl" above, then move them here`}</pre>
          </div>

          <div>
            <p className="text-gray-400 font-medium mb-1">Step 2 — Install dependencies</p>
            <pre className="bg-gray-900 rounded p-3 text-xs text-gray-300 overflow-x-auto">{`pip install -r requirements.txt`}</pre>
            <div className="mt-2 bg-yellow-900/30 border border-yellow-700/50 rounded p-2 text-xs text-yellow-300">
              <strong>Version mismatch warning:</strong> model.pkl is tied to the scikit-learn version used during training in the E2B sandbox. If you get errors like <code className="bg-yellow-900/50 px-1 rounded">AttributeError</code> on load, run:
              <pre className="mt-1 text-yellow-200">{`pip install "scikit-learn>=1.3.0,<2.0.0" --upgrade`}</pre>
            </div>
          </div>

          <div>
            <p className="text-gray-400 font-medium mb-1">Step 3 — Start the API server</p>
            <pre className="bg-gray-900 rounded p-3 text-xs text-gray-300 overflow-x-auto">{`uvicorn endpoint:app --host 0.0.0.0 --port 8000`}</pre>
            <p className="text-gray-500 text-xs mt-1">The server starts at <span className="text-blue-400">http://localhost:8000</span></p>
          </div>

          <div>
            <p className="text-gray-400 font-medium mb-1">Step 4 — Test a prediction</p>
            <pre className="bg-gray-900 rounded p-3 text-xs text-gray-300 overflow-x-auto">{`curl -X POST http://localhost:8000/predict \\
  -H "Content-Type: application/json" \\
  -d '{"Pclass": 1, "Sex": "female", "Age": 29}'`}</pre>
            <p className="text-gray-500 text-xs mt-1">Or open <span className="text-blue-400">http://localhost:8000/docs</span> for the interactive Swagger UI</p>
          </div>

          <div>
            <p className="text-gray-400 font-medium mb-1">Other endpoints</p>
            <ul className="space-y-1 text-xs text-gray-400">
              <li><code className="text-blue-300">GET /health</code> — model status and metric value</li>
              <li><code className="text-blue-300">GET /features</code> — list of required input columns</li>
              <li><code className="text-blue-300">GET /docs</code> — Swagger interactive API docs</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
