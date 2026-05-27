"use client";

import { useState, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import UploadPanel from "../components/UploadPanel";
import ApprovalGate from "../components/ApprovalGate";
import ProfileView from "../components/ProfileView";
import ExperimentPanel from "../components/ExperimentPanel";
import ModelSelectionView from "../components/ModelSelectionView";
import DebugLog from "../components/DebugLog";
import ModelCard from "../components/ModelCard";
import EndpointViewer from "../components/EndpointViewer";
import PipelineProgress from "../components/PipelineProgress";
import TestModelPanel from "../components/TestModelPanel";
import {
  getJobStatus, getFullJob, getProfile, getExperiments,
  getDebugLog, getModelCard, getEndpointCode, getExplanation, approveModel,
  createJob, approveProblem,
} from "@/lib/classification-api";

type View = "upload" | "awaiting_problem_approval" | "profiling" | "experiments" | "awaiting_model_approval" | "results" | "endpoint" | "failed";

function phaseToView(phase: string): View {
  if (phase === "awaiting_problem_approval") return "awaiting_problem_approval";
  if (["profiling_complete", "design_complete", "resuming", "problem_approved"].includes(phase)) return "profiling";
  if (["experiments_complete", "running", "initializing"].includes(phase)) return "experiments";
  if (phase === "awaiting_model_approval") return "awaiting_model_approval";
  if (["model_approved", "documentation_complete"].includes(phase)) return "results";
  if (phase === "complete") return "endpoint";
  if (phase === "failed") return "failed";
  return "experiments";
}

function TopBar({ jobId, polling, onReset }: { jobId: string | null; polling: boolean; onReset: () => void }) {
  const router = useRouter();
  return (
    <div className="sticky top-0 z-50 flex items-center justify-between px-8 py-3 shrink-0 bg-ink-950/80 backdrop-blur-md border-b border-ink-800/40">
      <div className="flex items-center gap-3">
        <button onClick={() => router.push("/")} className="flex items-center gap-3 hover:opacity-80 transition-opacity">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-blue to-accent-violet flex items-center justify-center shadow-glow-blue">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 7L4 17L12 22L20 17L20 7Z" stroke="white" strokeWidth="1.5" fill="none"/>
              <path d="M12 2L12 22M4 7L20 17M20 7L4 17" stroke="white" strokeWidth="1" opacity=".6"/>
            </svg>
          </div>
          <div>
            <div className="text-[13px] font-semibold tracking-tight">Prometheus</div>
            <div className="eyebrow text-[9.5px] -mt-px text-accent-blueGlow">classification</div>
          </div>
        </button>
        {jobId && (
          <div className="ml-5 pl-5 border-l border-ink-700/60">
            <div className="eyebrow text-[9px]">job</div>
            <div className="font-mono text-[11.5px] text-ink-200">{jobId.slice(0, 8)}...</div>
          </div>
        )}
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={onReset}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11.5px] font-medium border border-ink-700 text-ink-300 hover:border-ink-500 hover:text-ink-100 hover:bg-ink-800/60 transition-all active:scale-95"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M3 3v5h5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          New Job
        </button>
        <div className="flex items-center gap-2 text-ink-400">
          <svg width="13" height="13" viewBox="0 0 24 24" className={polling ? "spin-slow" : ""}>
            <circle cx="12" cy="12" r="9" stroke="rgba(148,163,184,.2)" strokeWidth="2" fill="none"/>
            <path d="M12 3a9 9 0 0 1 9 9" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" fill="none"/>
          </svg>
          <span className="eyebrow text-[9.5px]">{polling ? "polling / 3s" : "idle"}</span>
        </div>
      </div>
    </div>
  );
}

export default function ClassificationPage() {
  const router = useRouter();
  const [jobId, setJobId] = useState<string | null>(null);
  const [view, setView] = useState<View>("upload");
  const [jobData, setJobData] = useState<any>(null);
  const [profileData, setProfileData] = useState<any>(null);
  const [experiments, setExperiments] = useState<any[]>([]);
  const [debugLog, setDebugLog] = useState<any[]>([]);
  const [modelCardData, setModelCardData] = useState<any>(null);
  const [endpointData, setEndpointData] = useState<any>(null);
  const [explanationData, setExplanationData] = useState<any>(null);
  const [approveLoading, setApproveLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const pollStatus = useCallback(async () => {
    if (!jobId) return;
    setPolling(true);
    try {
      const status = await getJobStatus(jobId);
      const newView = phaseToView(status.current_phase);
      setView(newView);
      const full = await getFullJob(jobId);
      setJobData(full);

      if (["profiling", "experiments", "awaiting_model_approval", "results", "endpoint"].includes(newView)) {
        if (!profileData) { try { setProfileData(await getProfile(jobId)); } catch (err) { console.error("profile fetch:", err); } }
      }
      if (["experiments", "awaiting_model_approval", "results", "endpoint"].includes(newView)) {
        try { const e = await getExperiments(jobId); setExperiments(e.experiment_results); } catch (err) { console.error("experiments fetch:", err); }
        try { const d = await getDebugLog(jobId); setDebugLog(d.debug_log); } catch (err) { console.error("debug log fetch:", err); }
      }
      if (["results", "endpoint"].includes(newView) && !modelCardData) {
        try { setModelCardData(await getModelCard(jobId)); setExplanationData(await getExplanation(jobId)); } catch (err) { console.error("model card fetch:", err); }
      }
      if (newView === "endpoint" && !endpointData) {
        try { setEndpointData(await getEndpointCode(jobId)); } catch (err) { console.error("endpoint fetch:", err); }
      }
    } catch (err) { console.error("poll status:", err); }
    finally { setPolling(false); }
  }, [jobId, profileData, modelCardData, endpointData]);

  // Support ?job=<id> URL param (from auto-detect landing page)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const jobFromUrl = params.get("job");
    if (jobFromUrl) {
      setJobId(jobFromUrl);
      setView("experiments");
      setJobData({ current_phase: "initializing" });
    }
  }, []);

  const isTerminal = view === "endpoint" || view === "failed";
  useEffect(() => {
    if (!jobId || isTerminal || view === "upload") return;
    const id = setInterval(pollStatus, 3000);
    pollStatus();
    return () => clearInterval(id);
  }, [jobId, view, pollStatus, isTerminal]);

  const handleReset = useCallback(() => {
    router.push("/");
  }, [router]);

  const handleJobCreated = (id: string) => {
    setJobId(id); setView("experiments"); setJobData({ current_phase: "initializing" });
  };
  const handleProblemApproved = () => setView("profiling");
  const handleModelApprove = async (selectedId?: string) => {
    if (!jobId) return;
    setApproveLoading(true);
    try { await approveModel(jobId, true, selectedId); setView("results"); }
    finally { setApproveLoading(false); }
  };

  const showChrome = view !== "upload" && view !== "failed";

  return (
    <div className="h-screen w-full flex flex-col overflow-hidden relative">
      <div className="absolute inset-0 bg-grid opacity-40 pointer-events-none" />
      <TopBar jobId={jobId} polling={polling} onReset={handleReset} />
      {showChrome && <PipelineProgress view={view} phase={jobData?.current_phase} />}

      <div className="flex-1 overflow-y-auto overflow-x-hidden relative">
        <AnimatePresence mode="wait">
          <motion.div key={view}
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
            className="w-full min-h-full pb-16">

            {view === "upload" && (
              <UploadPanel
                onJobCreated={handleJobCreated}
                createJobFn={createJob}
                taskLabel="binary classification"
                taskDescription="Predict categories: Yes/No, survived/died, disease/healthy"
              />
            )}

            {view === "awaiting_problem_approval" && jobData && (
              <ApprovalGate
                jobId={jobId!}
                taskType={jobData.task_type}
                targetColumn={jobData.target_column}
                metric={jobData.evaluation_metric}
                allColumns={jobData.dataset_columns ?? []}
                validationWarnings={jobData.validation_warnings ?? []}
                leakageWarnings={jobData.leakage_warnings ?? []}
                onApproved={handleProblemApproved}
                onReset={handleReset}
                approveProblemFn={approveProblem}
              />
            )}

            {view === "profiling" && (
              <ProfileView
                profile={profileData?.profile_report}
                validationWarnings={profileData?.validation_warnings}
                leakageWarnings={profileData?.leakage_warnings}
                classImbalanceDetected={profileData?.class_imbalance_detected}
                imbalanceRatio={profileData?.imbalance_ratio}
              />
            )}

            {view === "experiments" && (
              <>
                <ExperimentPanel experiments={experiments} evaluationMetric={jobData?.evaluation_metric} />
                <DebugLog debugLog={debugLog} />
              </>
            )}

            {view === "awaiting_model_approval" && (
              <ModelSelectionView
                experiments={experiments}
                jobData={jobData}
                onApprove={handleModelApprove}
                loading={approveLoading}
              />
            )}

            {view === "results" && (
              <motion.div className="max-w-[1280px] mx-auto px-8 py-6 space-y-5">
                <div className="flex items-end justify-between mb-2">
                  <div>
                    <div className="eyebrow">06 . phase</div>
                    <div className="text-[26px] font-semibold tracking-tight mt-1">Generating outputs</div>
                    <div className="text-ink-400 text-[13.5px] mt-1.5">Building model card, SHAP analysis, and endpoint...</div>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-blue/10 border border-accent-blue/30 text-accent-blueGlow">
                    <span className="dot bg-accent-blueGlow pulse-dot" /><span className="text-[11px] font-mono">processing</span>
                  </div>
                </div>
                {modelCardData && explanationData && (
                  <ModelCard modelCard={modelCardData.model_card} plainExplanation={explanationData.plain_english_explanation} shapFeatures={explanationData.shap_features} winningJustification={explanationData.winning_justification} />
                )}
                <DebugLog debugLog={debugLog} />
              </motion.div>
            )}

            {view === "endpoint" && (
              <motion.div className="max-w-[1280px] mx-auto px-8 py-6 space-y-5">
                <div className="flex items-end justify-between mb-2">
                  <div>
                    <div className="eyebrow">07 . complete</div>
                    <div className="text-[26px] font-semibold tracking-tight mt-1">Pipeline complete</div>
                    <div className="text-ink-400 text-[13.5px] mt-1.5">Your classifier is trained, packaged, and ready to call.</div>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-emerald/10 border border-accent-emerald/40 text-accent-emerald">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M5 12.5L10 17L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                    <span className="text-[11px] font-mono uppercase tracking-widest">deployed</span>
                  </div>
                </div>
                {jobData && (
                  <TestModelPanel jobId={jobId!} featureColumns={(jobData.dataset_columns ?? []).filter((c: string) => c !== jobData.target_column)} targetColumn={jobData.target_column ?? "target"} taskType={jobData.task_type} sampleRow={jobData.dataset_sample_rows?.[0]} sampleRows={jobData.dataset_sample_rows ?? []} heldOutRows={jobData.dataset_held_out_rows ?? []} />
                )}
                {endpointData && <EndpointViewer endpointCode={endpointData.endpoint_code} requirements={endpointData.requirements} jobId={jobId!} />}
                {modelCardData && explanationData && (
                  <ModelCard modelCard={modelCardData.model_card} plainExplanation={explanationData.plain_english_explanation} shapFeatures={explanationData.shap_features} winningJustification={explanationData.winning_justification} />
                )}
                <DebugLog debugLog={debugLog} />
              </motion.div>
            )}

            {view === "failed" && (
              <motion.div className="max-w-[1080px] mx-auto px-8 py-8 relative">
                <div className="absolute inset-x-0 top-0 h-48 -z-10" style={{ background: "radial-gradient(600px 300px at 50% 0%,rgba(244,63,94,.15),transparent 70%)" }} />
                <div className="flex items-end justify-between mb-6">
                  <div>
                    <div className="eyebrow">!! . failed</div>
                    <div className="text-[26px] font-semibold tracking-tight mt-1">Pipeline failed</div>
                    <div className="text-ink-400 text-[13.5px] mt-1.5">Both experiments exhausted retries. Inspect the debug log and re-run.</div>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-rose/10 border border-accent-rose/40 text-accent-rose">
                    <span className="dot bg-accent-rose pulse-dot" /><span className="text-[11px] font-mono uppercase tracking-widest">failed</span>
                  </div>
                </div>
                <div className="flex items-start gap-4 rounded-xl bg-accent-rose/8 border border-accent-rose/30 px-5 py-4 mb-6">
                  <div className="w-10 h-10 rounded-lg bg-accent-rose/15 border border-accent-rose/40 flex items-center justify-center text-accent-rose shrink-0">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 3L22 20H2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><path d="M12 10v4M12 17v.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>
                  </div>
                  <div className="flex-1">
                    <div className="text-[14px] font-semibold text-accent-rose">All experiments failed</div>
                    <div className="text-[12.5px] text-ink-300 mt-1">{jobData?.error_message || "Check the debug log for details."}</div>
                    <button onClick={handleReset} className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-[12px] font-medium border bg-accent-blue hover:bg-accent-blueDim border-accent-blue/40 text-white transition-all">
                      Start New Job
                    </button>
                  </div>
                </div>
                <DebugLog debugLog={debugLog} />
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
