"use client";

import { useState, useEffect, useCallback } from "react";
import UploadPanel from "./components/UploadPanel";
import ApprovalGate from "./components/ApprovalGate";
import ProfileView from "./components/ProfileView";
import ExperimentPanel from "./components/ExperimentPanel";
import DebugLog from "./components/DebugLog";
import ModelCard from "./components/ModelCard";
import EndpointViewer from "./components/EndpointViewer";
import PipelineProgress from "./components/PipelineProgress";
import TestModelPanel from "./components/TestModelPanel";
import {
  getJobStatus, getFullJob, getProfile, getExperiments,
  getDebugLog, getModelCard, getEndpointCode, getExplanation,
  approveModel,
} from "@/lib/api";

const TERMINAL_PHASES = ["complete", "failed"];
const POLL_INTERVAL = 3000;

type View =
  | "upload"
  | "awaiting_problem_approval"
  | "profiling"
  | "experiments"
  | "awaiting_model_approval"
  | "results"
  | "endpoint"
  | "failed";

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

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [view, setView] = useState<View>("upload");
  const [jobData, setJobData] = useState<any>(null);
  const [profileData, setProfileData] = useState<any>(null);
  const [experiments, setExperiments] = useState<any[]>([]);
  const [debugLog, setDebugLog] = useState<any[]>([]);
  const [modelCardData, setModelCardData] = useState<any>(null);
  const [endpointData, setEndpointData] = useState<any>(null);
  const [explanationData, setExplanationData] = useState<any>(null);

  const pollStatus = useCallback(async () => {
    if (!jobId) return;
    try {
      const status = await getJobStatus(jobId);
      const newView = phaseToView(status.current_phase);
      setView(newView);

      const full = await getFullJob(jobId);
      setJobData(full);

      // Fetch phase-specific data
      if (["profiling", "experiments", "awaiting_model_approval", "results", "endpoint"].includes(newView)) {
        if (!profileData) {
          try {
            const p = await getProfile(jobId);
            setProfileData(p);
          } catch {}
        }
      }

      if (["experiments", "awaiting_model_approval", "results", "endpoint"].includes(newView)) {
        try {
          const e = await getExperiments(jobId);
          setExperiments(e.experiment_results);
        } catch {}
        try {
          const d = await getDebugLog(jobId);
          setDebugLog(d.debug_log);
        } catch {}
      }

      if (["results", "endpoint"].includes(newView)) {
        if (!modelCardData) {
          try {
            const mc = await getModelCard(jobId);
            const exp = await getExplanation(jobId);
            setModelCardData(mc);
            setExplanationData(exp);
          } catch {}
        }
      }

      if (newView === "endpoint" && !endpointData) {
        try {
          const ep = await getEndpointCode(jobId);
          setEndpointData(ep);
        } catch {}
      }
    } catch {}
  }, [jobId, profileData, modelCardData, endpointData]);

  useEffect(() => {
    if (!jobId || TERMINAL_PHASES.includes(view) || view === "upload") return;
    const interval = setInterval(pollStatus, POLL_INTERVAL);
    pollStatus();
    return () => clearInterval(interval);
  }, [jobId, view, pollStatus]);

  const handleJobCreated = (id: string) => {
    setJobId(id);
    setView("experiments");
    setJobData({ current_phase: "initializing" }); // seed phase so progress bar starts at step 1
  };

  const handleProblemApproved = () => {
    setView("profiling");
  };

  const handleModelApprove = async () => {
    if (!jobId) return;
    await approveModel(jobId, true);
    setView("results");
  };

  const phaseLabel: Record<string, string> = {
    initializing: "Initializing...",
    awaiting_problem_approval: "Awaiting approval",
    profiling_complete: "Profiling complete",
    design_complete: "Designing pipelines",
    experiments_complete: "Experiments done",
    awaiting_model_approval: "Select model",
    model_approved: "Generating outputs",
    complete: "Complete",
    failed: "Failed",
  };

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      {jobId && view !== "upload" && view !== "failed" && (
        <>
          <nav className="border-b border-gray-800 px-8 py-3 flex items-center gap-4 text-sm">
            <span className="text-gray-400 font-mono text-xs">Job: {jobId.slice(0, 8)}…</span>
            <span className="text-gray-600">›</span>
            <span className="text-gray-300">{phaseLabel[jobData?.current_phase] || jobData?.current_phase || "Running"}</span>
          </nav>
          <PipelineProgress view={view} phase={jobData?.current_phase} />
        </>
      )}

      {view === "upload" && <UploadPanel onJobCreated={handleJobCreated} />}

      {view === "awaiting_problem_approval" && jobData && (
        <ApprovalGate
          jobId={jobId!}
          taskType={jobData.task_type || ""}
          targetColumn={jobData.target_column || ""}
          metric={jobData.evaluation_metric || ""}
          allColumns={jobData.dataset_columns || []}
          validationWarnings={jobData.validation_warnings || []}
          leakageWarnings={jobData.leakage_warnings || []}
          onApproved={handleProblemApproved}
        />
      )}

      {view === "profiling" && (
        <div className="space-y-4">
          {profileData ? (
            <ProfileView
              profile={profileData.profile_report}
              validationWarnings={profileData.validation_warnings}
              leakageWarnings={profileData.leakage_warnings}
              classImbalanceDetected={profileData.class_imbalance_detected}
              imbalanceRatio={profileData.imbalance_ratio}
            />
          ) : (
            <div className="max-w-2xl mx-auto p-8 text-center text-gray-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
              Profiling dataset...
            </div>
          )}
        </div>
      )}

      {view === "experiments" && (
        <div className="space-y-4">
          {profileData && (
            <ProfileView
              profile={profileData.profile_report}
              validationWarnings={profileData.validation_warnings}
              leakageWarnings={profileData.leakage_warnings}
              classImbalanceDetected={profileData.class_imbalance_detected}
              imbalanceRatio={profileData.imbalance_ratio}
            />
          )}
          <ExperimentPanel experiments={experiments} evaluationMetric={jobData?.evaluation_metric} />
          {experiments.length === 0 && (
            <p className="text-center text-gray-500 text-xs -mt-2 pb-2">
              E2B sandbox is installing packages and running your ML pipeline — typically 2–4 minutes.
            </p>
          )}
          {debugLog.length > 0 && <DebugLog debugLog={debugLog} />}
        </div>
      )}

      {view === "awaiting_model_approval" && (
        <div className="space-y-4">
          <ExperimentPanel experiments={experiments} evaluationMetric={jobData?.evaluation_metric} />
          <div className="max-w-2xl mx-auto px-8 pb-8">
            <div className="bg-gray-800 rounded-xl p-6">
              <h3 className="text-lg font-semibold text-white mb-2">Selected Model</h3>
              <p className="text-gray-300 text-sm mb-4">{jobData?.winning_justification}</p>
              <button
                onClick={handleModelApprove}
                className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-3 rounded-xl transition-colors"
              >
                Approve & Generate Endpoint
              </button>
            </div>
          </div>
          {debugLog.length > 0 && <DebugLog debugLog={debugLog} />}
        </div>
      )}

      {view === "results" && (
        <div className="space-y-4">
          {modelCardData && explanationData ? (
            <ModelCard
              modelCard={modelCardData.model_card}
              plainExplanation={explanationData.plain_english_explanation}
              shapFeatures={explanationData.shap_features || []}
              winningJustification={explanationData.winning_justification}
            />
          ) : (
            <div className="max-w-2xl mx-auto p-8 text-center text-gray-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
              Generating model card and SHAP analysis...
            </div>
          )}
          {debugLog.length > 0 && <DebugLog debugLog={debugLog} />}
        </div>
      )}

      {view === "endpoint" && (
        <div className="space-y-4">
          {endpointData ? (
            <EndpointViewer
              endpointCode={endpointData.endpoint_code}
              requirements={endpointData.requirements}
              jobId={jobId!}
            />
          ) : (
            <div className="max-w-2xl mx-auto p-8 text-center text-gray-400">
              <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
              Generating endpoint...
            </div>
          )}
          {jobData && (
            <TestModelPanel
              jobId={jobId!}
              featureColumns={(jobData.dataset_columns || []).filter((c: string) => c !== jobData.target_column)}
              targetColumn={jobData.target_column || "target"}
              taskType={jobData.task_type}
              sampleRow={jobData.dataset_sample_rows?.[0]}
            />
          )}
          {modelCardData && explanationData && (
            <ModelCard
              modelCard={modelCardData.model_card}
              plainExplanation={explanationData.plain_english_explanation}
              shapFeatures={explanationData.shap_features || []}
              winningJustification={explanationData.winning_justification}
            />
          )}
          {debugLog.length > 0 && <DebugLog debugLog={debugLog} />}
        </div>
      )}

      {view === "failed" && (
        <div className="max-w-2xl mx-auto p-8 text-center">
          <p className="text-red-400 text-xl font-semibold mb-3">Pipeline Failed</p>
          <p className="text-gray-400 text-sm mb-6">{jobData?.error_message || "An unknown error occurred."}</p>
          {debugLog.length > 0 && <DebugLog debugLog={debugLog} />}
          <button
            onClick={() => { setJobId(null); setView("upload"); }}
            className="mt-4 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium"
          >
            Start New Job
          </button>
        </div>
      )}
    </main>
  );
}
