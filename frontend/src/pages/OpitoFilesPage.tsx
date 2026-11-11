import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileSpreadsheet, RefreshCw } from "lucide-react";
import { downloadFile, request } from "../api/client";
import type { OpitoCohort, OpitoFileResult, OpitoMissingVantage } from "../api/types";
import { useAuth } from "../auth/context";
import { CERTIFICATE_ISSUE, CERTIFICATE_READ, can } from "../auth/roles";
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { count, errorMessage, formatDate } from "../lib/format";

interface OpitoCohortList {
  data: OpitoCohort[];
  total: number;
}

interface OpitoValidation {
  valid: boolean;
  missingVantageIds: OpitoMissingVantage[];
}

export function OpitoFilesPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [confirming, setConfirming] = useState<OpitoCohort | null>(null);
  const [missing, setMissing] = useState<OpitoMissingVantage[]>([]);
  const [busyCohort, setBusyCohort] = useState<string | null>(null);

  const cohorts = useQuery({
    queryKey: ["opito-files"],
    queryFn: () => request<OpitoCohortList>("/opito-files/"),
  });

  const generate = useMutation({
    mutationFn: (cohort: OpitoCohort) =>
      request<OpitoFileResult>("/opito-files/generate/", {
        method: "POST",
        body: JSON.stringify({ course: cohort.course, start_date: cohort.start }),
      }),
    onSuccess: (file) => {
      void queryClient.invalidateQueries({ queryKey: ["opito-files"] });
      toast.push(`${file.file_name} generated for ${count(file.record_count)} learners.`);
      setConfirming(null);
    },
    onError: (error) => toast.push(errorMessage(error), "error"),
    onSettled: () => setBusyCohort(null),
  });

  const validate = useMutation({
    mutationFn: (cohort: OpitoCohort) =>
      request<OpitoValidation>("/opito-files/validate-vantage/", {
        params: { course: cohort.course, start_date: cohort.start },
      }),
    onSuccess: (result, cohort) => {
      if (result.valid) {
        generate.mutate(cohort);
        return;
      }
      setBusyCohort(null);
      setMissing(result.missingVantageIds);
      setConfirming(cohort);
    },
    onError: (error) => {
      setBusyCohort(null);
      toast.push(errorMessage(error), "error");
    },
  });

  function getFile(cohort: OpitoCohort) {
    setBusyCohort(cohort.id);
    validate.mutate(cohort);
  }

  function download(cohort: OpitoCohort) {
    if (!cohort.file_id) return;
    void downloadFile(`/opito-files/${cohort.file_id}/download/`, cohort.file_name).catch(
      (error) => toast.push(errorMessage(error), "error"),
    );
  }

  if (!can(user, CERTIFICATE_READ)) {
    return (
      <EmptyState
        title="OPITO files are restricted"
        body="Your role does not include access to certification files."
      />
    );
  }
  if (cohorts.isLoading) return <Loading rows={6} />;
  if (cohorts.isError || !cohorts.data) {
    return (
      <ErrorState
        message={errorMessage(cohorts.error)}
        retry={() => void cohorts.refetch()}
      />
    );
  }

  const data = cohorts.data.data;
  const canGenerate = can(user, CERTIFICATE_ISSUE);
  const generated = data.filter((cohort) => cohort.file_id).length;
  const learners = data.reduce((total, cohort) => total + cohort.learners, 0);

  return (
    <>
      <PageHeader
        eyebrow="Certification"
        title="OPITO files"
        description="Build the learner CSV for each delivered OPITO course, validate Vantage IDs, and download the file for upload to the OPITO HUB."
      />

      <Card
        title="Delivery cohorts"
        aside={
          <span className="card-note">
            {count(data.length)} cohorts - {count(generated)} generated - {count(learners)} learners
          </span>
        }
      >
        <div className="opito-summary">
          <div>
            <strong>{count(data.length)}</strong>
            <span>OPITO cohorts</span>
          </div>
          <div>
            <strong>{count(learners)}</strong>
            <span>Learner rows</span>
          </div>
          <div>
            <strong>{count(generated)}</strong>
            <span>Files ready</span>
          </div>
        </div>

        {data.length ? (
          <div className="opito-grid">
            {data.map((cohort) => {
              const isBusy = busyCohort === cohort.id || (generate.isPending && confirming?.id === cohort.id);
              return (
                <article className="opito-card" key={cohort.id}>
                  <div className="opito-card-head">
                    <div>
                      <span className="opito-code">{cohort.product_code || cohort.course_code}</span>
                      <h3>{cohort.name}</h3>
                    </div>
                    {cohort.file_id ? <Badge tone="ok">Ready</Badge> : <Badge>Not generated</Badge>}
                  </div>

                  <dl className="opito-meta">
                    <div>
                      <dt>Course date</dt>
                      <dd>{formatDate(cohort.start)}</dd>
                    </div>
                    <div>
                      <dt>Learners</dt>
                      <dd>{count(cohort.learners)}</dd>
                    </div>
                    <div>
                      <dt>Course code</dt>
                      <dd className="mono">{cohort.course_code}</dd>
                    </div>
                    <div>
                      <dt>Product code</dt>
                      <dd className="mono">{cohort.product_code || "Not set"}</dd>
                    </div>
                  </dl>

                  {cohort.file_id ? (
                    <p className="opito-file-note">
                      <FileSpreadsheet size={14} aria-hidden="true" />
                      <span className="mono">{cohort.file_name}</span>
                    </p>
                  ) : (
                    <p className="hint">
                      {canGenerate
                        ? "Vantage IDs are checked before the file is generated."
                        : "A certification manager must generate this file."}
                    </p>
                  )}

                  <div className="opito-card-foot">
                    {cohort.file_id ? (
                      <Button size="sm" variant="primary" onClick={() => download(cohort)}>
                        <Download size={14} aria-hidden="true" /> Download CSV
                      </Button>
                    ) : canGenerate ? (
                      <Button
                        size="sm"
                        variant="primary"
                        busy={isBusy}
                        disabled={Boolean(busyCohort)}
                        onClick={() => getFile(cohort)}
                      >
                        <FileSpreadsheet size={14} aria-hidden="true" /> Get file
                      </Button>
                    ) : null}
                    {cohort.file_id && canGenerate ? (
                      <Button
                        size="sm"
                        busy={isBusy}
                        disabled={Boolean(busyCohort)}
                        title="Regenerate from the latest learner records"
                        onClick={() => getFile(cohort)}
                      >
                        <RefreshCw size={14} aria-hidden="true" /> Refresh
                      </Button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No OPITO cohorts yet"
            body="Once OPITO course deliveries are scheduled and learners are recorded, their cohorts will appear here."
          />
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(confirming)}
        title="Generate with missing Vantage IDs?"
        message={`${count(missing.length)} learner${
          missing.length === 1 ? "" : "s"
        } in this cohort have no Vantage ID: ${
          missing
            .slice(0, 5)
            .map((learner) => learner.fullName)
            .join(", ") || "none"
        }${missing.length > 5 ? ` and ${missing.length - 5} more` : ""}. The CSV will leave those cells blank.`}
        confirmLabel="Generate CSV"
        busy={generate.isPending}
        onConfirm={() => confirming && generate.mutate(confirming)}
        onClose={() => {
          if (generate.isPending) return;
          setConfirming(null);
          setMissing([]);
          setBusyCohort(null);
        }}
      />
    </>
  );
}
