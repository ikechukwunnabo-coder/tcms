import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { getList, request } from "../api/client";
import { useAuth } from "../auth/context";
import { USER_ADMIN_ROLES, can } from "../auth/roles";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Field,
  Input,
  Loading,
  Modal,
  PageHeader,
  SearchInput,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { count, errorMessage, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";

type ReferenceRow = Record<string, string | number | boolean | null>;

interface ReferenceField {
  key: string;
  label: string;
  type?: "text" | "email" | "checkbox";
  required?: boolean;
}

interface ReferenceSet {
  key: string;
  label: string;
  endpoint: string;
  columns: { key: string; label: string; render?: (row: ReferenceRow) => string }[];
  fields: ReferenceField[];
  searchable: boolean;
}

const SETS: ReferenceSet[] = [
  {
    key: "companies",
    label: "Companies",
    endpoint: "/companies/",
    columns: [
      { key: "agencode", label: "Code" },
      { key: "name", label: "Name" },
      { key: "email", label: "Email" },
      { key: "active", label: "Status", render: (row) => (row.active ? "Active" : "Inactive") },
    ],
    fields: [
      { key: "agencode", label: "Company code", required: true },
      { key: "name", label: "Name", required: true },
      { key: "email", label: "Email", type: "email" },
      { key: "active", label: "Active", type: "checkbox" },
      { key: "is_individual", label: "Individual account", type: "checkbox" },
    ],
    searchable: true,
  },
  {
    key: "nationalities",
    label: "Nationalities",
    endpoint: "/nationalities/",
    columns: [
      { key: "natcode", label: "Code" },
      { key: "nationality", label: "Nationality" },
      { key: "country", label: "Country" },
    ],
    fields: [
      { key: "natcode", label: "Code", required: true },
      { key: "nationality", label: "Nationality", required: true },
      { key: "country", label: "Country", required: true },
    ],
    searchable: true,
  },
  {
    key: "states",
    label: "States",
    endpoint: "/states/",
    columns: [
      { key: "code", label: "Code" },
      { key: "name", label: "Name" },
    ],
    fields: [
      { key: "code", label: "Code", required: true },
      { key: "name", label: "Name", required: true },
    ],
    searchable: true,
  },
  {
    key: "positions",
    label: "Positions",
    endpoint: "/positions/",
    columns: [
      { key: "posicode", label: "Code" },
      { key: "name", label: "Name" },
    ],
    fields: [
      { key: "posicode", label: "Code", required: true },
      { key: "name", label: "Name", required: true },
    ],
    searchable: true,
  },
  {
    key: "titles",
    label: "Titles",
    endpoint: "/titles/",
    columns: [{ key: "name", label: "Name" }],
    fields: [{ key: "name", label: "Name", required: true }],
    searchable: false,
  },
  {
    key: "contact-types",
    label: "Contact types",
    endpoint: "/contact-types/",
    columns: [{ key: "name", label: "Name" }],
    fields: [{ key: "name", label: "Name", required: true }],
    searchable: false,
  },
];

const STANDALONE_DESCRIPTIONS: Record<string, string> = {
  companies: "Manage companies.",
  states: "Manage states master table.",
  nationalities: "Manage nationalities.",
};

function ReferenceEditor({
  set,
  row,
  onClose,
}: {
  set: ReferenceSet;
  row?: ReferenceRow;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<Record<string, string | boolean>>(() => {
    const initial: Record<string, string | boolean> = {};
    for (const field of set.fields) {
      const value = row?.[field.key];
      initial[field.key] =
        field.type === "checkbox" ? Boolean(value) : String(value ?? "");
    }
    return initial;
  });

  const save = useMutation({
    mutationFn: () => {
      const payload: ReferenceRow = {};
      for (const field of set.fields) {
        const value = form[field.key];
        if (field.type === "checkbox") payload[field.key] = Boolean(value);
        else if (value !== "") payload[field.key] = String(value).trim();
      }
      return request<ReferenceRow>(
        row ? `${set.endpoint}${row.id}/` : set.endpoint,
        { method: row ? "PATCH" : "POST", body: JSON.stringify(payload) },
      );
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reference", set.key] });
      void queryClient.invalidateQueries({ queryKey: ["reference"] });
      toast.push(`${titleCase(set.label)} saved.`);
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`${row ? "Edit" : "Add"} ${titleCase(set.label)}`}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="reference-form" variant="primary" busy={save.isPending}>
            Save record
          </Button>
        </>
      }
    >
      <form id="reference-form" className="form-stack" onSubmit={submit}>
        {save.isError ? <div className="form-error">{errorMessage(save.error)}</div> : null}
        {set.fields.map((field) => (
          field.type === "checkbox" ? (
            <label className="check-row" key={field.key}>
              <input
                type="checkbox"
                checked={Boolean(form[field.key])}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [field.key]: event.target.checked }))
                }
              />
              {field.label}
            </label>
          ) : (
            <Field label={field.label} htmlFor={`ref-${field.key}`} key={field.key}>
              <Input
                id={`ref-${field.key}`}
                type={field.type ?? "text"}
                required={field.required}
                value={String(form[field.key] ?? "")}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [field.key]: event.target.value }))
                }
              />
            </Field>
          )
        ))}
      </form>
    </Modal>
  );
}

export function ReferenceDataPage({ initialSet }: { initialSet?: string }) {
  const { user } = useAuth();
  const editable = can(user, USER_ADMIN_ROLES);
  const standalone = Boolean(initialSet);
  const [active, setActive] = useState(
    () => SETS.find((set) => set.key === initialSet) ?? SETS[0],
  );
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<ReferenceRow | null | undefined>(undefined);
  const search = useDebounced(query);

  useEffect(() => {
    const next = SETS.find((set) => set.key === initialSet);
    if (!next) return;
    setActive(next);
    setQuery("");
    setEditing(undefined);
  }, [initialSet]);

  const rows = useQuery({
    queryKey: ["reference", active.key, search],
    queryFn: () =>
      getList<ReferenceRow>(active.endpoint, {
        ...(active.searchable && search ? { search } : {}),
        page_size: 200,
      }),
  });

  function selectSet(next: ReferenceSet) {
    setActive(next);
    setQuery("");
    setEditing(undefined);
  }

  return (
    <>
      <PageHeader
        eyebrow={standalone ? "Reference data" : "Shared definitions"}
        title={standalone ? active.label : "Shared definitions"}
        description={
          standalone
            ? STANDALONE_DESCRIPTIONS[active.key]
            : "The controlled lists behind learner profiles, bookings and certificates. Changes are audited and immediately available across the console."
        }
        actions={
          editable ? (
            <Button variant="primary" onClick={() => setEditing(null)}>
              <Plus size={16} aria-hidden="true" /> Add record
            </Button>
          ) : null
        }
      />
      <Card>
        {standalone ? null : (
          <div className="tabs reference-tabs" role="tablist" aria-label="Reference data sets">
            {SETS.map((set) => (
              <button
                type="button"
                key={set.key}
                role="tab"
                aria-selected={active.key === set.key}
                className={`tab ${active.key === set.key ? "active" : ""}`}
                onClick={() => selectSet(set)}
              >
                {set.label}
              </button>
            ))}
          </div>
        )}
        <Toolbar>
          {active.searchable ? (
            <SearchInput value={query} onChange={setQuery} placeholder={`Search ${active.label.toLowerCase()}`} />
          ) : (
            <span />
          )}
          <span className="toolbar-count">{count(rows.data?.total ?? 0)} records</span>
        </Toolbar>
        {rows.isLoading ? (
          <Loading rows={5} />
        ) : rows.isError || !rows.data ? (
          <ErrorState message={errorMessage(rows.error)} retry={() => void rows.refetch()} />
        ) : rows.data.data.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  {active.columns.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {rows.data.data.map((row) => (
                  <tr key={String(row.id)}>
                    {active.columns.map((column) => (
                      <td key={column.key}>
                        {column.key === "active" ? (
                          <Badge tone={row.active ? "ok" : "neutral"}>
                            {row.active ? "Active" : "Inactive"}
                          </Badge>
                        ) : column.render ? (
                          column.render(row)
                        ) : (
                          String(row[column.key] ?? "—")
                        )}
                      </td>
                    ))}
                    <td>
                      {editable ? (
                        <div className="row-actions">
                          <Button size="sm" onClick={() => setEditing(row)}>
                            <Pencil size={14} aria-hidden="true" /> Edit
                          </Button>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted body-copy">No records match this view.</p>
        )}
      </Card>
      {editing !== undefined ? (
        <ReferenceEditor
          set={active}
          row={editing ?? undefined}
          onClose={() => setEditing(undefined)}
        />
      ) : null}
    </>
  );
}
