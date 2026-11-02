import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Stethoscope } from "lucide-react";
import { getList, request } from "../api/client";
import type { Medical } from "../api/types";
import { useAuth } from "../auth/context";
import { MEDICAL_ROLES, MEDICAL_WRITE, can } from "../auth/roles";
import { LearnerPicker } from "../components/LearnerPicker";
import {
  Badge,
  Button,
  Card,
  CsvButton,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Loading,
  Modal,
  PageHeader,
  Pagination,
  SearchInput,
  Select,
  StatusBadge,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";

const FITNESS = ["fit", "fit_with_restrictions", "unfit"];

function expiryFlag(medical: Medical) {
  if (!medical.active || !medical.expiry_date) return null;
  const today = new Date();
  const expiry = new Date(`${medical.expiry_date}T23:59:59`);
  const days = Math.ceil((expiry.getTime() - today.getTime()) / 86_400_000);
  if (days < 0) return { label: "Expired", tone: "danger" as const };
  if (days <= 30) return { label: `${days}d left`, tone: "warn" as const };
  return null;
}

function MedicalEditor({
  medical,
  onClose,
}: {
  medical?: Medical;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    learner: medical ? String(medical.learner) : "",
    record_no: medical?.record_no ?? "",
    issued_date: medical?.issued_date ?? "",
    expiry_date: medical?.expiry_date ?? "",
    systolic: medical?.systolic ? String(medical.systolic) : "",
    diastolic: medical?.diastolic ? String(medical.diastolic) : "",
    fitness: medical?.fitness ?? "",
    active: medical?.active ?? true,
  });

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      medical
        ? request<Medical>(`/medicals/${medical.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<Medical>("/medicals/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["medicals"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(medical ? "Medical record updated." : "Medical record added.");
      onClose();
    },
  });

  function set(key: keyof typeof form, value: string | boolean) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      learner: Number(form.learner),
      record_no: form.record_no.trim(),
      issued_date: form.issued_date || null,
      expiry_date: form.expiry_date || null,
      systolic: form.systolic ? Number(form.systolic) : null,
      diastolic: form.diastolic ? Number(form.diastolic) : null,
      fitness: form.fitness,
      active: form.active,
    });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={medical ? "Edit medical record" : "Add medical record"}
      description="Medical validity gates certificate issue. Keep expiry dates current."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="medical-form" variant="primary" busy={save.isPending}>
            {medical ? "Save record" : "Add record"}
          </Button>
        </>
      }
    >
      <form id="medical-form" className="form-grid" onSubmit={submit}>
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        <Field label="Learner" htmlFor="medical-learner" className="form-span">
          <LearnerPicker
            id="medical-learner"
            value={form.learner}
            onChange={(value) => set("learner", value)}
            required
          />
        </Field>
        <Field label="Record number" htmlFor="medical-record">
          <Input
            id="medical-record"
            value={form.record_no}
            onChange={(event) => set("record_no", event.target.value)}
          />
        </Field>
        <Field label="Fitness" htmlFor="medical-fitness">
          <Select
            id="medical-fitness"
            value={form.fitness}
            onChange={(event) => set("fitness", event.target.value)}
          >
            <option value="">Not assessed</option>
            {FITNESS.map((option) => (
              <option value={option} key={option}>
                {titleCase(option)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Issued" htmlFor="medical-issued">
          <Input
            id="medical-issued"
            type="date"
            value={form.issued_date}
            onChange={(event) => set("issued_date", event.target.value)}
          />
        </Field>
        <Field label="Expires" htmlFor="medical-expiry">
          <Input
            id="medical-expiry"
            type="date"
            value={form.expiry_date}
            onChange={(event) => set("expiry_date", event.target.value)}
          />
        </Field>
        <Field label="Systolic" htmlFor="medical-systolic">
          <Input
            id="medical-systolic"
            type="number"
            min="0"
            max="300"
            value={form.systolic}
            onChange={(event) => set("systolic", event.target.value)}
          />
        </Field>
        <Field label="Diastolic" htmlFor="medical-diastolic">
          <Input
            id="medical-diastolic"
            type="number"
            min="0"
            max="200"
            value={form.diastolic}
            onChange={(event) => set("diastolic", event.target.value)}
          />
        </Field>
        <Field label="Status" htmlFor="medical-active">
          <Select
            id="medical-active"
            value={form.active ? "true" : "false"}
            onChange={(event) => set("active", event.target.value === "true")}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
        </Field>
      </form>
    </Modal>
  );
}

export function MedicalsPage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [fitness, setFitness] = useState("");
  const [active, setActive] = useState("true");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ medical?: Medical } | null>(null);
  const search = useDebounced(query);

  const medicals = useQuery({
    queryKey: ["medicals", search, fitness, active, page],
    queryFn: () =>
      getList<Medical>("/medicals/", {
        search,
        fitness,
        active,
        page,
        page_size: 25,
      }),
  });

  if (!can(user, MEDICAL_ROLES)) {
    return (
      <EmptyState
        title="Medicals are restricted"
        body="Your role does not include access to medical fitness records."
      />
    );
  }
  if (medicals.isLoading) return <Loading rows={7} />;
  if (medicals.isError || !medicals.data) {
    return (
      <ErrorState message={errorMessage(medicals.error)} retry={() => void medicals.refetch()} />
    );
  }

  const canWrite = can(user, MEDICAL_WRITE);

  return (
    <>
      <PageHeader
        eyebrow="Fitness to train"
        title="Medicals"
        description="Medical validity records that gate training and certificate issue."
        actions={
          <>
            <CsvButton dataset="medicals" label="Export medicals" />
            {canWrite ? (
              <Button variant="primary" onClick={() => setEditor({})}>
                <Stethoscope size={16} aria-hidden="true" /> Add medical
              </Button>
            ) : null}
          </>
        }
      />

      <Card>
        <Toolbar>
          <SearchInput
            value={query}
            onChange={(value) => {
              setQuery(value);
              setPage(1);
            }}
            placeholder="Search badge, surname or record no"
          />
          <Select
            aria-label="Filter by fitness"
            value={fitness}
            onChange={(event) => {
              setFitness(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All fitness states</option>
            {FITNESS.map((option) => (
              <option value={option} key={option}>
                {titleCase(option)}
              </option>
            ))}
          </Select>
          <Select
            aria-label="Filter by status"
            value={active}
            onChange={(event) => {
              setActive(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All records</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </Select>
          <span className="toolbar-count">{medicals.data.total} records</span>
        </Toolbar>

        {medicals.data.data.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Learner</th>
                    <th>Record</th>
                    <th>Issued</th>
                    <th>Expires</th>
                    <th>Fitness</th>
                    <th>Status</th>
                    {canWrite ? <th aria-label="Actions" /> : null}
                  </tr>
                </thead>
                <tbody>
                  {medicals.data.data.map((medical) => {
                    const flag = expiryFlag(medical);
                    return (
                      <tr key={medical.id}>
                        <td>
                          <strong>{medical.learner_name}</strong>
                          <div className="cell-sub mono">{medical.badge_no}</div>
                        </td>
                        <td className="mono">{medical.record_no || "—"}</td>
                        <td>{formatDate(medical.issued_date)}</td>
                        <td>
                          <span className="date-flag">
                            {formatDate(medical.expiry_date)}
                            {flag ? <Badge tone={flag.tone}>{flag.label}</Badge> : null}
                          </span>
                        </td>
                        <td>
                          {medical.fitness ? (
                            <StatusBadge status={medical.fitness} label={titleCase(medical.fitness)} />
                          ) : (
                            "—"
                          )}
                        </td>
                        <td>
                          <StatusBadge
                            status={medical.active ? "active" : "inactive"}
                            label={medical.active ? "Active" : "Inactive"}
                          />
                        </td>
                        {canWrite ? (
                          <td className="row-actions">
                            <Button size="sm" onClick={() => setEditor({ medical })}>
                              <Pencil size={14} aria-hidden="true" /> Edit
                            </Button>
                          </td>
                        ) : null}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Pagination
              page={medicals.data.page}
              pageSize={medicals.data.page_size}
              total={medicals.data.total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No medicals found"
            body={
              query || fitness
                ? "No record matches the current filters."
                : "Add a medical record before issuing certificates for a learner."
            }
            action={
              canWrite && !query && !fitness ? (
                <Button variant="primary" onClick={() => setEditor({})}>
                  Add medical
                </Button>
              ) : undefined
            }
          />
        )}
      </Card>

      {editor ? <MedicalEditor medical={editor.medical} onClose={() => setEditor(null)} /> : null}
    </>
  );
}
