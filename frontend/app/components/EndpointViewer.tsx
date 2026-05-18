"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface Props { endpointCode: string; requirements: string; jobId: string; }

function highlight(code: string) {
  return code.split("\n").map((line, i) => {
    const cls = line.trim().startsWith("#") ? "tok-cmt"
      : /^(import|from|def |class |return|if |else|elif|for |with |as |global|async |await )/.test(line.trim()) ? "tok-kw"
      : /['"].*?['"]/.test(line) ? ""
      : "";
    return (
      <div key={i} className="flex">
        <span className="w-8 text-right shrink-0 text-ink-600 select-none mr-3 text-[11px]">{String(i + 1).padStart(2, "0")}</span>
        <span className={`flex-1 text-[11.5px] ${cls}`}>{line || " "}</span>
      </div>
    );
  });
}

export default function EndpointViewer({ endpointCode, requirements, jobId }: Props) {
  const [tab, setTab] = useState<"code" | "req" | "deploy">("code");
  const [copied, setCopied] = useState(false);

  const tabs = [
    { id: "code" as const,   label: "endpoint.py" },
    { id: "req" as const,    label: "requirements.txt" },
    { id: "deploy" as const, label: "deployment.md" },
  ];

  const deployContent = `# Quickstart
$ pip install -r requirements.txt
$ uvicorn endpoint:app --host 0.0.0.0 --port 8001

# Test
$ curl -X POST localhost:8001/predict \\
    -H "Content-Type: application/json" \\
    -d '{"feature1": 1.0, "feature2": "value"}'

# sklearn version note
pip install "scikit-learn>=1.3.0,<2.0.0" --upgrade`;

  const content = tab === "code" ? endpointCode : tab === "req" ? requirements : deployContent;

  const handleCopy = () => {
    navigator.clipboard.writeText(content ?? "");
    setCopied(true); setTimeout(() => setCopied(false), 1600);
  };

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.05 }}
      className="glass-strong rounded-2xl overflow-hidden">
      <div className="px-6 pt-5 pb-4 flex items-center justify-between border-b border-ink-700/60">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent-violet/15 border border-accent-violet/40 flex items-center justify-center text-accent-violet">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"><path d="M8 4L4 12L8 20M16 4L20 12L16 20" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </div>
          <div>
            <div className="text-[15px] font-semibold tracking-tight">Generated endpoint</div>
            <div className="text-[12px] text-ink-400 mt-0.5">FastAPI service / ready to deploy</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ink-800 hover:bg-ink-750 border border-ink-700 text-ink-200 text-[12px] transition-colors">
            {copied ? (
              <><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg> Copied</>
            ) : (
              <><svg width="13" height="13" viewBox="0 0 24 24" fill="none"><rect x="8" y="8" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.6"/><path d="M5 16V6a1 1 0 0 1 1-1h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg> Copy</>
            )}
          </button>
          <a href={`http://localhost:8000/jobs/${jobId}/endpoint-code`} target="_blank"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-blue/15 hover:bg-accent-blue/25 border border-accent-blue/40 text-accent-blueGlow text-[12px] transition-colors">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M12 4v12m0 0l-5-5m5 5l5-5M4 20h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
            endpoint.py
          </a>
          <a href={`http://localhost:8000/jobs/${jobId}/model.pkl`} target="_blank"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-emerald/15 hover:bg-accent-emerald/25 border border-accent-emerald/40 text-accent-emerald text-[12px] transition-colors">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"><path d="M12 4v12m0 0l-5-5m5 5l5-5M4 20h16" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
            model.pkl
          </a>
        </div>
      </div>

      <div className="px-6 pt-4 flex items-center gap-1">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded-md font-mono text-[12px] transition-all ${tab === t.id ? "bg-ink-800 text-ink-100 border border-ink-700" : "text-ink-500 hover:text-ink-300 border border-transparent"}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="px-6 pb-6 pt-3">
        <div className="rounded-lg bg-[#070A12] border border-ink-700/70 overflow-hidden">
          <div className="px-4 py-3 font-mono leading-relaxed overflow-x-auto max-h-72 overflow-y-auto no-scrollbar">
            {highlight(content || "")}
          </div>
        </div>
      </div>
    </motion.div>
  );
}


