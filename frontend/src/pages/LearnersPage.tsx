import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Pencil, Plus, UserPlus } from "lucide-react";
import { getList, request } from "../api/client";
import type { Learner, LearnerContact } from "../api/types";
import { useAuth } from "../auth/context";
import { LEARNER_ROLES, can } from "../auth/roles";
import {
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
import { errorMessage, formatDate } from "../lib/format";
import { useDebounced } from "../lib/hooks";
import { useReference } from "../lib/useReference";
import { useToast } from "../components/toastContext";

interface LearnerForm {
  badge_no: string;
  surname: string;
  first_name: string;
  middle_name: string;
  sex: string;
  birth_date: string;
  nationality: string;
  state: string;
  position: string;
  company: string;
  title: string;
  active: boolean;
  pertype: string;
}

function initialForm(learner?: Learner): LearnerForm {
  return {
    badge_no: learner?.badge_no ?? "",
    surname: learner?.surname ?? "",
    first_name: learner?.first_name ?? "",
    middle_name: learner?.middle_name ?? "",
    sex: learner?.sex ?? "",
    birth_date: learner?.birth_date ?? "",
    nationality: learner?.nationality ? String(learner.nationality) : "",
    state: learner?.state ? String(learner.state) : "",
    position: learner?.position ? String(learner.position) : "",
    company: learner?.company ? String(learner.company) : "",
    title: learner?.title ? String(learner.title) : "",
    active: learner?.active ?? true,
    pertype: learner?.pertype ?? "TRN",
  };
}

function LearnerEditor({
  learner,
  onClose,
}: {
  learner?: Learner;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const references = useReference();
  const [form, setForm] = useState<LearnerForm>(() => initialForm(learner));

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      learner
        ? request<Learner>(`/learners/${learner.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<Learner>("/learners/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["learners"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["reference"] });
      toast.push(learner ? "Learner record updated." : "Learner added to the register.");
      onClose();
    },
  });

  function set<K extends keyof LearnerForm>(key: K, value: LearnerForm[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      badge_no: form.badge_no.trim(),
      surname: form.surname.trim(),
      first_name: form.first_name.trim(),
      middle_name: form.middle_name.trim(),
      sex: form.sex,
      birth_date: form.birth_date || null,
      nationality: form.nationality ? Number(form.nationality) : null,
      state: form.state ? Number(form.state) : null,
      position: form.position ? Number(form.position) : null,
      company: form.company ? Number(form.company) : null,
      title: form.title ? Number(form.title) : null,
      active: form.active,
      pertype: form.pertype.trim() || "TRN",
    });
  }

  const refs = references.data;

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={learner ? `Edit ${learner.full_name}` : "Add a learner"}
      description="Badge numbers are unique. Reference fields can stay blank until the learner profile is complete."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="learner-form"
            variant="primary"
            busy={save.isPending}
          >
            {learner ? "Save changes" : "Add learner"}
          </Button>
        </>
      }
    >
      <form id="learner-form" className="form-grid" onSubmit={submit}>
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        <Field label="Badge number" htmlFor="badge_no">
          <Input
            id="badge_no"
            required
            value={form.badge_no}
            onChange={(event) => set("badge_no", event.target.value)}
            placeholder="TC-0001"
          />
        </Field>
        <Field label="Surname" htmlFor="surname">
          <Input
            id="surname"
            required
            value={form.surname}
            onChange={(event) => set("surname", event.target.value)}
          />
        </Field>
        <Field label="First name" htmlFor="first_name">
          <Input
            id="first_name"
            value={form.first_name}
            onChange={(event) => set("first_name", event.target.value)}
          />
        </Field>
        <Field label="Middle name" htmlFor="middle_name">
          <Input
            id="middle_name"
            value={form.middle_name}
            onChange={(event) => set("middle_name", event.target.value)}
          />
        </Field>
        <Field label="Sex" htmlFor="sex">
          <Select id="sex" value={form.sex} onChange={(event) => set("sex", event.target.value)}>
            <option value="">Not specified</option>
            <option value="M">Male</option>
            <option value="F">Female</option>
          </Select>
        </Field>
        <Field label="Date of birth" htmlFor="birth_date">
          <Input
            id="birth_date"
            type="date"
            value={form.birth_date}
            onChange={(event) => set("birth_date", event.target.value)}
          />
        </Field>
        <Field label="Company" htmlFor="company">
          <Select
            id="company"
            value={form.company}
            onChange={(event) => set("company", event.target.value)}
          >
            <option value="">Individual / not set</option>
            {(refs?.companies ?? []).map((company) => (
              <option value={company.id} key={company.id}>
                {company.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Position" htmlFor="position">
          <Select
            id="position"
            value={form.position}
            onChange={(event) => set("position", event.target.value)}
          >
            <option value="">Not set</option>
            {(refs?.positions ?? []).map((position) => (
              <option value={position.id} key={position.id}>
                {position.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Nationality" htmlFor="nationality">
          <Select
            id="nationality"
            value={form.nationality}
            onChange={(event) => set("nationality", event.target.value)}
          >
            <option value="">Not set</option>
            {(refs?.nationalities ?? []).map((nationality) => (
              <option value={nationality.id} key={nationality.id}>
                {nationality.nationality}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="State" htmlFor="state">
          <Select
            id="state"
            value={form.state}
            onChange={(event) => set("state", event.target.value)}
          >
            <option value="">Not set</option>
            {(refs?.states ?? []).map((state) => (
              <option value={state.id} key={state.id}>
                {state.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Title" htmlFor="title">
          <Select
            id="title"
            value={form.title}
            onChange={(event) => set("title", event.target.value)}
          >
            <option value="">Not set</option>
            {(refs?.titles ?? []).map((title) => (
              <option value={title.id} key={title.id}>
                {title.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Legacy type" htmlFor="pertype" hint="Legacy personnel code. Defaults to TRN.">
          <Input
            id="pertype"
            value={form.pertype}
            onChange={(event) => set("pertype", event.target.value)}
          />
        </Field>
        <Field label="Status" htmlFor="active">
          <Select
            id="active"
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

function LearnerDetail({ learner, onClose }: { learner: Learner; onClose: () => void }) {
  const references = useReference();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [contacts, setContacts] = useState<LearnerContact[]>(learner.contacts);
  const [contactType, setContactType] = useState("");
  const [value, setValue] = useState("");

  const addContact = useMutation({
    mutationFn: (payload: { learner: number; contact_type: number | null; value: string }) =>
      request<LearnerContact>("/learner-contacts/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (contact) => {
      setContacts((current) => [...current, contact]);
      setValue("");
      void queryClient.invalidateQueries({ queryKey: ["learners"] });
      toast.push("Contact added.");
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!value.trim()) return;
    addContact.mutate({
      learner: learner.id,
      contact_type: contactType ? Number(contactType) : null,
      value: value.trim(),
    });
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={learner.full_name}
      description={`${learner.badge_no} · ${learner.active ? "Active" : "Inactive"}`}
      footer={
        <Button onClick={onClose}>Close</Button>
      }
    >
      <div className="detail-grid">
        <div>
          <p className="detail-label">Date of birth</p>
          <p>{formatDate(learner.birth_date)}</p>
        </div>
        <div>
          <p className="detail-label">Sex</p>
          <p>{learner.sex === "M" ? "Male" : learner.sex === "F" ? "Female" : "Not set"}</p>
        </div>
        <div>
          <p className="detail-label">Company</p>
          <p>
            {references.data?.companies.find((row) => row.id === learner.company)?.name ?? "—"}
          </p>
        </div>
        <div>
          <p className="detail-label">Position</p>
          <p>
            {references.data?.positions.find((row) => row.id === learner.position)?.name ?? "—"}
          </p>
        </div>
      </div>

      <div className="detail-section">
        <h3>Contacts</h3>
        {contacts.length ? (
          <ul className="plain-list">
            {contacts.map((contact) => (
              <li key={contact.id}>
                <span>
                  {references.data?.contactTypes.find((row) => row.id === contact.contact_type)
                    ?.name ?? "Contact"}
                </span>
                <strong>{contact.value}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted body-copy">No contact details captured yet.</p>
        )}
        <form className="inline-form" onSubmit={submit}>
          <Select
            aria-label="Contact type"
            value={contactType}
            onChange={(event) => setContactType(event.target.value)}
          >
            <option value="">Contact type</option>
            {(references.data?.contactTypes ?? []).map((type) => (
              <option value={type.id} key={type.id}>
                {type.name}
              </option>
            ))}
          </Select>
          <Input
            aria-label="Contact value"
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Phone, email or address"
          />
          <Button type="submit" busy={addContact.isPending}>
            Add
          </Button>
        </form>
        {addContact.isError ? (
          <p className="field-error">{errorMessage(addContact.error)}</p>
        ) : null}
      </div>

      <div className="detail-section">
        <h3>Documents</h3>
        {learner.documents.length ? (
          <ul className="plain-list">
            {learner.documents.map((document) => (
              <li key={document.id}>
                <span>{document.kind.replace(/_/g, " ")}</span>
                <strong className="mono">{document.object_key}</strong>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted body-copy">No documents uploaded for this learner.</p>
        )}
      </div>
    </Modal>
  );
}

export function LearnersPage() {
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<{ learner?: Learner } | null>(null);
  const [detail, setDetail] = useState<Learner | null>(null);
  const search = useDebounced(query);

  const learners = useQuery({
    queryKey: ["learners", search, status, page],
    queryFn: () =>
      getList<Learner>("/learners/", {
        search,
        active: status,
        page,
        page_size: 25,
      }),
  });

  if (learners.isLoading) return <Loading rows={7} />;
  if (learners.isError || !learners.data) {
    return (
      <ErrorState message={errorMessage(learners.error)} retry={() => void learners.refetch()} />
    );
  }

  const canManage = can(user, LEARNER_ROLES);
  const rows = learners.data.data;
  const total = learners.data.total;

  return (
    <>
      <PageHeader
        eyebrow="Learner register"
        title="Learners"
        description="The personnel and delegate register behind every booking, medical and certificate."
        actions={
          <>
            <CsvButton dataset="learners" params={{ q: search, active: status }} label="Export register" />
            {canManage ? (
              <Button variant="primary" onClick={() => setEditor({})}>
                <UserPlus size={16} aria-hidden="true" /> New learner
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
            placeholder="Search badge, surname or first name"
          />
          <Select
            aria-label="Filter by status"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </Select>
          <span className="toolbar-count">{total} learners</span>
        </Toolbar>

        {rows.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Badge</th>
                    <th>Learner</th>
                    <th>Company</th>
                    <th>Contact</th>
                    <th>Status</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((learner) => (
                    <tr key={learner.id}>
                      <td className="mono">{learner.badge_no}</td>
                      <td>
                        <strong>{learner.full_name}</strong>
                        <div className="cell-sub">
                          {learner.sex === "M" ? "Male" : learner.sex === "F" ? "Female" : "—"} ·{" "}
                          {formatDate(learner.birth_date)}
                        </div>
                      </td>
                      <td>{learner.company ? `Company #${learner.company}` : "Individual"}</td>
                      <td>
                        {learner.contacts[0]?.value ?? "—"}
                        {learner.contacts.length > 1 ? (
                          <div className="cell-sub">+{learner.contacts.length - 1} more</div>
                        ) : null}
                      </td>
                      <td>
                        <StatusBadge
                          status={learner.active ? "active" : "inactive"}
                          label={learner.active ? "Active" : "Inactive"}
                        />
                      </td>
                      <td className="row-actions">
                        <Button size="sm" onClick={() => setDetail(learner)}>
                          <ExternalLink size={14} aria-hidden="true" /> View
                        </Button>
                        {canManage ? (
                          <Button size="sm" onClick={() => setEditor({ learner })}>
                            <Pencil size={14} aria-hidden="true" /> Edit
                          </Button>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={learners.data.page}
              pageSize={learners.data.page_size}
              total={total}
              onPage={setPage}
            />
          </>
        ) : (
          <EmptyState
            title="No learners found"
            body={
              query || status
                ? "Adjust the search or status filter to widen the register."
                : "Add the first learner to begin booking training."
            }
            action={
              canManage && !query && !status ? (
                <Button variant="primary" onClick={() => setEditor({})}>
                  <Plus size={16} aria-hidden="true" /> Add learner
                </Button>
              ) : undefined
            }
          />
        )}
      </Card>

      {editor ? <LearnerEditor learner={editor.learner} onClose={() => setEditor(null)} /> : null}
      {detail ? <LearnerDetail learner={detail} onClose={() => setDetail(null)} /> : null}
    </>
  );
}
