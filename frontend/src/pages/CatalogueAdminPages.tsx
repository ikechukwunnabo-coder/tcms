import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus } from "lucide-react";
import { getList, request } from "../api/client";
import type { CourseItem, CourseModule } from "../api/types";
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
import { count, errorMessage } from "../lib/format";
import { useDebounced } from "../lib/hooks";

type CatalogueEntity = CourseModule | CourseItem;

function EntityEditor({
  kind,
  entity,
  onClose,
}: {
  kind: "module" | "item";
  entity?: CatalogueEntity;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(entity?.name ?? "");
  const [active, setActive] = useState(entity?.active ?? true);
  const endpoint = kind === "module" ? "/course-modules/" : "/course-items/";

  const save = useMutation({
    mutationFn: () =>
      request<CatalogueEntity>(entity ? `${endpoint}${entity.id}/` : endpoint, {
        method: entity ? "PATCH" : "POST",
        body: JSON.stringify({ name: name.trim(), active }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [kind === "module" ? "course-modules" : "course-items"] });
      void queryClient.invalidateQueries({ queryKey: ["reference"] });
      toast.push(`${kind === "module" ? "Module" : "Item"} saved.`);
      onClose();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    save.mutate();
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`${entity ? "Edit" : "Add"} ${kind}`}
      description="These shared definitions are used when assembling course content and delivery records."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="catalogue-entity-form" variant="primary" busy={save.isPending}>
            Save {kind}
          </Button>
        </>
      }
    >
      <form id="catalogue-entity-form" className="form-stack" onSubmit={submit}>
        {save.isError ? <div className="form-error">{errorMessage(save.error)}</div> : null}
        <Field label="Name" htmlFor="entity-name">
          <Input
            id="entity-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </Field>
        <label className="check-row">
          <input
            type="checkbox"
            checked={active}
            onChange={(event) => setActive(event.target.checked)}
          />
          Active and available for selection
        </label>
      </form>
    </Modal>
  );
}

function CatalogueEntityPage({ kind }: { kind: "module" | "item" }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<CatalogueEntity | null | undefined>(undefined);
  const search = useDebounced(query);
  const endpoint = kind === "module" ? "/course-modules/" : "/course-items/";
  const key = kind === "module" ? "course-modules" : "course-items";

  const rows = useQuery({
    queryKey: [key, search],
    queryFn: () => getList<CatalogueEntity>(endpoint, { search, page_size: 200 }),
  });

  if (rows.isLoading) return <Loading rows={6} />;
  if (rows.isError || !rows.data) {
    return <ErrorState message={errorMessage(rows.error)} retry={() => void rows.refetch()} />;
  }

  return (
    <>
      <PageHeader
        eyebrow="Catalogue"
        title={kind === "module" ? "Modules" : "Items"}
        description={
          kind === "module"
            ? "Reusable delivery modules assigned to instructors and training days."
            : "Checklist items recorded against a learner's training."
        }
        actions={
          can(user, USER_ADMIN_ROLES) ? (
            <Button variant="primary" onClick={() => setEditing(null)}>
              <Plus size={16} aria-hidden="true" /> Add {kind}
            </Button>
          ) : null
        }
      />
      <Card>
        <Toolbar>
          <SearchInput value={query} onChange={setQuery} placeholder={`Search ${kind}s`} />
          <span className="toolbar-count">{count(rows.data.total)} {kind}s</span>
        </Toolbar>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rows.data.data.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.name}</strong></td>
                  <td>
                    <Badge tone={row.active ? "ok" : "neutral"}>
                      {row.active ? "Active" : "Inactive"}
                    </Badge>
                  </td>
                  <td>
                    {can(user, USER_ADMIN_ROLES) ? (
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
        {!rows.data.data.length ? <p className="muted body-copy">No {kind}s match this search.</p> : null}
      </Card>
      {editing !== undefined ? (
        <EntityEditor
          kind={kind}
          entity={editing ?? undefined}
          onClose={() => {
            setEditing(undefined);
            void queryClient.invalidateQueries({ queryKey: [key] });
          }}
        />
      ) : null}
    </>
  );
}

export function ModulesPage() {
  return <CatalogueEntityPage kind="module" />;
}

export function ItemsPage() {
  return <CatalogueEntityPage kind="item" />;
}
