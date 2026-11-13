import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileUp,
  GitBranch,
  Plus,
  RefreshCw,
  Upload,
} from "lucide-react";
import { downloadFile, getList, request } from "../api/client";
import type {
  Approval,
  AuditEvent,
  DocumentRecord,
  ExternalRef,
  NotificationRecord,
  NotificationTemplate,
  OutboxEvent,
  ReportDef,
  Role,
  SeedMarker,
  WebhookDelivery,
  WorkflowStatus,
} from "../api/types";
import { useAuth } from "../auth/context";
import { can } from "../auth/roles";
import {
  Badge,
  Button,
  Card,
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
  Stat,
  StatusBadge,
  Textarea,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import {
  errorMessage,
  formatDateTime,
  titleCase,
} from "../lib/format";
import { useDebounced } from "../lib/hooks";

function firstError(error: unknown) {
  return errorMessage(error);
}

function NotificationTemplateEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [code, setCode] = useState("");
  const [channel, setChannel] = useState("email");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const create = useMutation({
    mutationFn: () =>
      request<NotificationTemplate>("/notification-templates/", {
        method: "POST",
        body: JSON.stringify({ code, channel, subject, body }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notification-templates"] });
      toast.push("Template created.");
      onClose();
    },
  });

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title="New notification template"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="template-form"
            variant="primary"
            busy={create.isPending}
          >
            Create template
          </Button>
        </>
      }
    >
      <form
        id="template-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        {create.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(create.error)}
          </div>
        ) : null}
        <Field label="Code" htmlFor="template-code">
          <Input
            id="template-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            required
          />
        </Field>
        <Field label="Channel" htmlFor="template-channel">
          <Select
            id="template-channel"
            value={channel}
            onChange={(event) => setChannel(event.target.value)}
          >
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="in_app">In app</option>
          </Select>
        </Field>
        <Field label="Subject" htmlFor="template-subject" className="form-span">
          <Input
            id="template-subject"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
          />
        </Field>
        <Field label="Body" htmlFor="template-body" className="form-span">
          <Textarea
            id="template-body"
            rows={6}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

export function NotificationsPage() {
  const [tab, setTab] = useState<"history" | "templates">("history");
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const notifications = useQuery({
    queryKey: ["notifications", page],
    queryFn: () => getList<NotificationRecord>("/notifications/", { page, page_size: 25 }),
    enabled: tab === "history",
  });
  const templates = useQuery({
    queryKey: ["notification-templates"],
    queryFn: () => getList<NotificationTemplate>("/notification-templates/", { page_size: 100 }),
    enabled: tab === "templates",
  });

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Notifications"
        description="Review message delivery and maintain the templates used across the centre."
        actions={
          tab === "templates" ? (
            <Button variant="primary" onClick={() => setEditor(true)}>
              <Plus size={16} aria-hidden="true" /> New template
            </Button>
          ) : null
        }
      />
      <div className="tabs" role="tablist" aria-label="Notification sections">
        {(["history", "templates"] as const).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={tab === item ? "tab active" : "tab"}
            onClick={() => setTab(item)}
          >
            {item === "history" ? "Delivery history" : "Templates"}
          </button>
        ))}
      </div>

      {tab === "history" ? (
        <Card title="Delivery history">
          {notifications.isLoading ? <Loading rows={5} /> : null}
          {notifications.isError ? (
            <ErrorState
              message={firstError(notifications.error)}
              retry={() => void notifications.refetch()}
            />
          ) : null}
          {notifications.data ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Template</th>
                      <th>Recipient</th>
                      <th>Channel</th>
                      <th>Status</th>
                      <th>Sent</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {notifications.data.data.map((row) => (
                      <tr key={row.id}>
                        <td className="mono">{row.template_code}</td>
                        <td>{row.recipient}</td>
                        <td>{titleCase(row.channel)}</td>
                        <td>
                          <StatusBadge status={row.status} />
                        </td>
                        <td>{formatDateTime(row.sent_at)}</td>
                        <td>{row.error || <span className="muted">None</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={25}
                total={notifications.data.total}
                onPage={setPage}
              />
            </>
          ) : null}
        </Card>
      ) : null}

      {tab === "templates" ? (
        <Card title="Message templates">
          {templates.isLoading ? <Loading rows={5} /> : null}
          {templates.isError ? (
            <ErrorState
              message={firstError(templates.error)}
              retry={() => void templates.refetch()}
            />
          ) : null}
          {templates.data ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Channel</th>
                    <th>Subject</th>
                    <th>Body</th>
                  </tr>
                </thead>
                <tbody>
                  {templates.data.data.map((row) => (
                    <tr key={row.id}>
                      <td className="mono">{row.code}</td>
                      <td>{titleCase(row.channel)}</td>
                      <td>{row.subject || <span className="muted">No subject</span>}</td>
                      <td>{row.body}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Card>
      ) : null}

      {editor ? <NotificationTemplateEditor onClose={() => setEditor(false)} /> : null}
    </>
  );
}

function DocumentUpload({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [kind, setKind] = useState("supporting");
  const [ownerType, setOwnerType] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const upload = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Choose a file to upload.");
      const data = new FormData();
      data.append("file", file);
      data.append("kind", kind);
      if (ownerType) data.append("owner_type", ownerType);
      if (ownerId) data.append("owner_id", ownerId);
      return request<DocumentRecord>("/documents/upload/", {
        method: "POST",
        body: data,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.push("Document uploaded.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="Upload a document"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="document-form"
            variant="primary"
            busy={upload.isPending}
            disabled={!file}
          >
            <Upload size={15} aria-hidden="true" /> Upload
          </Button>
        </>
      }
    >
      <form
        id="document-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          upload.mutate();
        }}
      >
        {upload.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(upload.error)}
          </div>
        ) : null}
        <Field label="Kind" htmlFor="document-kind">
          <Input
            id="document-kind"
            value={kind}
            onChange={(event) => setKind(event.target.value)}
            required
          />
        </Field>
        <Field label="Owner type" htmlFor="document-owner-type" hint="Optional.">
          <Input
            id="document-owner-type"
            value={ownerType}
            onChange={(event) => setOwnerType(event.target.value)}
          />
        </Field>
        <Field label="Owner ID" htmlFor="document-owner-id" hint="Optional.">
          <Input
            id="document-owner-id"
            type="number"
            min="1"
            value={ownerId}
            onChange={(event) => setOwnerId(event.target.value)}
          />
        </Field>
        <Field label="File" htmlFor="document-file" className="form-span">
          <Input
            id="document-file"
            type="file"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

export function DocumentsPage() {
  const toast = useToast();
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const search = useDebounced(query);
  const documents = useQuery({
    queryKey: ["documents", page, search],
    queryFn: () =>
      getList<DocumentRecord>("/documents/", {
        page,
        page_size: 25,
        ...(search ? { search } : {}),
      }),
  });

  async function download(row: DocumentRecord) {
    try {
      const name = row.object_key.split("/").pop() ?? `document-${row.id}`;
      await downloadFile(`/documents/${row.id}/download/`, name);
    } catch (error) {
      toast.push(firstError(error));
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Documents"
        description="Search stored artefacts and add supporting files to the controlled document store."
        actions={
          <Button variant="primary" onClick={() => setEditor(true)}>
            <FileUp size={16} aria-hidden="true" /> Upload document
          </Button>
        }
      />
      <Card title="Stored documents">
        <Toolbar>
          <SearchInput value={query} onChange={setQuery} placeholder="Search object key or SHA-256" />
          <span className="toolbar-count">{documents.data?.total ?? 0} documents</span>
        </Toolbar>
        {documents.isLoading ? <Loading rows={5} /> : null}
        {documents.isError ? (
          <ErrorState
            message={firstError(documents.error)}
            retry={() => void documents.refetch()}
          />
        ) : null}
        {documents.data ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Owner</th>
                    <th>File</th>
                    <th>MIME</th>
                    <th className="num">Size</th>
                    <th>Generated</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {documents.data.data.map((row) => (
                    <tr key={row.id}>
                      <td>{titleCase(row.kind)}</td>
                      <td>
                        {row.owner_type ? `${row.owner_type} #${row.owner_id ?? "?"}` : "Unattached"}
                      </td>
                      <td className="mono">{row.object_key}</td>
                      <td>{row.mime || "-"}</td>
                      <td className="num">{row.size_bytes.toLocaleString()} B</td>
                      <td>{formatDateTime(row.generated_at)}</td>
                      <td>
                        <Button size="sm" onClick={() => void download(row)}>
                          Download
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!documents.data.data.length ? (
              <EmptyState title="No documents" body="Upload the first supporting document." />
            ) : null}
            <Pagination
              page={page}
              pageSize={25}
              total={documents.data.total}
              onPage={setPage}
            />
          </>
        ) : null}
      </Card>
      {editor ? <DocumentUpload onClose={() => setEditor(false)} /> : null}
    </>
  );
}

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("");
  const search = useDebounced(query);
  const events = useQuery({
    queryKey: ["audit-events", page, search, action],
    queryFn: () =>
      getList<AuditEvent>("/audit-events/", {
        page,
        page_size: 25,
        ...(search ? { search } : {}),
        ...(action ? { action } : {}),
      }),
  });

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Audit trail"
        description="An append-only record of changes and sensitive actions across the console."
      />
      <Card title="Audit events" aside={<Badge tone="brand">Append only</Badge>}>
        <Toolbar>
          <SearchInput value={query} onChange={setQuery} placeholder="Search action or entity" />
          <Input
            aria-label="Filter by action"
            placeholder="Action contains…"
            value={action}
            onChange={(event) => {
              setPage(1);
              setAction(event.target.value);
            }}
          />
          <span className="toolbar-count">{events.data?.total ?? 0} events</span>
        </Toolbar>
        {events.isLoading ? <Loading rows={5} /> : null}
        {events.isError ? (
          <ErrorState message={firstError(events.error)} retry={() => void events.refetch()} />
        ) : null}
        {events.data ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Before</th>
                    <th>After</th>
                    <th>IP</th>
                  </tr>
                </thead>
                <tbody>
                  {events.data.data.map((event) => (
                    <tr key={event.id}>
                      <td>{formatDateTime(event.at)}</td>
                      <td>{event.actor ?? "System"}</td>
                      <td>
                        <Badge tone="brand">{event.action}</Badge>
                      </td>
                      <td>
                        {event.entity}
                        {event.entity_id ? ` #${event.entity_id}` : ""}
                      </td>
                      <td className="audit-json">
                        {event.before ? JSON.stringify(event.before) : "—"}
                      </td>
                      <td className="audit-json">
                        {event.after ? JSON.stringify(event.after) : "—"}
                      </td>
                      <td className="mono">{event.ip ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!events.data.data.length ? (
              <EmptyState title="No audit events" body="No matching activity was recorded." />
            ) : null}
            <Pagination
              page={page}
              pageSize={25}
              total={events.data.total}
              onPage={setPage}
            />
          </>
        ) : null}
      </Card>
    </>
  );
}

function StatusEditor({
  status,
  roles,
  onClose,
}: {
  status?: WorkflowStatus;
  roles: Role[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [code, setCode] = useState(status?.code ?? "");
  const [name, setName] = useState(status?.name ?? "");
  const [nextRole, setNextRole] = useState(
    status?.next_role ? String(status.next_role) : "",
  );
  const [terminal, setTerminal] = useState(status?.terminal ?? false);
  const save = useMutation({
    mutationFn: () => {
      const payload = {
        code,
        name,
        next_role: nextRole ? Number(nextRole) : null,
        terminal,
      };
      return status
        ? request<WorkflowStatus>(`/workflow-statuses/${status.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<WorkflowStatus>("/workflow-statuses/", {
            method: "POST",
            body: JSON.stringify(payload),
          });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["workflow-statuses"] });
      toast.push("Workflow status saved.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title={status ? "Edit workflow status" : "New workflow status"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="status-form"
            variant="primary"
            busy={save.isPending}
          >
            Save status
          </Button>
        </>
      }
    >
      <form
        id="status-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(save.error)}
          </div>
        ) : null}
        <Field label="Code" htmlFor="status-code">
          <Input
            id="status-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            required
          />
        </Field>
        <Field label="Name" htmlFor="status-name">
          <Input
            id="status-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </Field>
        <Field label="Next role" htmlFor="status-role">
          <Select
            id="status-role"
            value={nextRole}
            onChange={(event) => setNextRole(event.target.value)}
          >
            <option value="">No next role</option>
            {roles.map((role) => (
              <option value={role.id} key={role.id}>
                {role.name}
              </option>
            ))}
          </Select>
        </Field>
        <label className="check">
          <input
            type="checkbox"
            checked={terminal}
            onChange={(event) => setTerminal(event.target.checked)}
          />
          Terminal status
        </label>
      </form>
    </Modal>
  );
}

export function WorkflowAdminPage() {
  const [tab, setTab] = useState<"statuses" | "approvals">("statuses");
  const [editing, setEditing] = useState<WorkflowStatus | null | undefined>(undefined);
  const [page, setPage] = useState(1);
  const statuses = useQuery({
    queryKey: ["workflow-statuses"],
    queryFn: () => getList<WorkflowStatus>("/workflow-statuses/", { page_size: 100 }),
    enabled: tab === "statuses",
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => getList<Role>("/roles/", { page_size: 100 }),
    enabled: editing !== undefined,
  });
  const approvals = useQuery({
    queryKey: ["approvals", page],
    queryFn: () => getList<Approval>("/approvals/", { page, page_size: 25 }),
    enabled: tab === "approvals",
  });

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Workflow administration"
        description="Maintain the approval stages that route training records through the centre."
        actions={
          tab === "statuses" ? (
            <Button variant="primary" onClick={() => setEditing(null)}>
              <Plus size={16} aria-hidden="true" /> New status
            </Button>
          ) : null
        }
      />
      <div className="tabs" role="tablist" aria-label="Workflow administration sections">
        {(["statuses", "approvals"] as const).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={tab === item ? "tab active" : "tab"}
            onClick={() => setTab(item)}
          >
            {item === "statuses" ? "Workflow statuses" : "Approval rows"}
          </button>
        ))}
      </div>

      {tab === "statuses" ? (
        <Card title="Workflow statuses">
          {statuses.isLoading ? <Loading rows={5} /> : null}
          {statuses.isError ? (
            <ErrorState
              message={firstError(statuses.error)}
              retry={() => void statuses.refetch()}
            />
          ) : null}
          {statuses.data ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Status</th>
                    <th>Next role</th>
                    <th>Terminal</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {statuses.data.data.map((status) => (
                    <tr key={status.id}>
                      <td className="mono">{status.code}</td>
                      <td>{status.name}</td>
                      <td>{status.next_role ?? "—"}</td>
                      <td>{status.terminal ? <Badge tone="ok">Terminal</Badge> : "No"}</td>
                      <td>
                        <Button size="sm" onClick={() => setEditing(status)}>
                          Edit
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Card>
      ) : null}

      {tab === "approvals" ? (
        <Card title="Approval rows">
          {approvals.isLoading ? <Loading rows={5} /> : null}
          {approvals.isError ? (
            <ErrorState
              message={firstError(approvals.error)}
              retry={() => void approvals.refetch()}
            />
          ) : null}
          {approvals.data ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Record</th>
                      <th>Status</th>
                      <th>Step</th>
                      <th>Assigned role</th>
                      <th>Action</th>
                      <th>Acted by</th>
                      <th>When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {approvals.data.data.map((row) => (
                      <tr key={row.id}>
                        <td className="mono">#{row.training_record}</td>
                        <td>{row.current_status}</td>
                        <td>{row.step_no}</td>
                        <td>{row.assigned_role ?? "—"}</td>
                        <td>{titleCase(row.action)}</td>
                        <td>{row.acted_by ?? "—"}</td>
                        <td>{formatDateTime(row.acted_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={25}
                total={approvals.data.total}
                onPage={setPage}
              />
            </>
          ) : null}
        </Card>
      ) : null}

      {editing !== undefined ? (
        <StatusEditor
          status={editing ?? undefined}
          roles={roles.data?.data ?? []}
          onClose={() => setEditing(undefined)}
        />
      ) : null}
    </>
  );
}

function ExternalRefEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [system, setSystem] = useState("");
  const [entity, setEntity] = useState("");
  const [entityId, setEntityId] = useState("");
  const [externalId, setExternalId] = useState("");
  const create = useMutation({
    mutationFn: () =>
      request<ExternalRef>("/external-refs/", {
        method: "POST",
        body: JSON.stringify({
          system,
          entity,
          entity_id: Number(entityId),
          external_id: externalId,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["external-refs"] });
      toast.push("External reference saved.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="New external reference"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="external-form"
            variant="primary"
            busy={create.isPending}
          >
            Save reference
          </Button>
        </>
      }
    >
      <form
        id="external-form"
        className="form-grid"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          create.mutate();
        }}
      >
        {create.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(create.error)}
          </div>
        ) : null}
        <Field label="System" htmlFor="external-system">
          <Input
            id="external-system"
            value={system}
            onChange={(event) => setSystem(event.target.value)}
            required
          />
        </Field>
        <Field label="Entity" htmlFor="external-entity">
          <Input
            id="external-entity"
            value={entity}
            onChange={(event) => setEntity(event.target.value)}
            required
          />
        </Field>
        <Field label="Entity ID" htmlFor="external-entity-id">
          <Input
            id="external-entity-id"
            type="number"
            min="1"
            value={entityId}
            onChange={(event) => setEntityId(event.target.value)}
            required
          />
        </Field>
        <Field label="External ID" htmlFor="external-id">
          <Input
            id="external-id"
            value={externalId}
            onChange={(event) => setExternalId(event.target.value)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

export function IntegrationPage() {
  const [tab, setTab] = useState<"outbox" | "webhooks" | "refs" | "seeds">("outbox");
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const health = useQuery({
    queryKey: ["integration-health"],
    queryFn: () =>
      request<{
        status: string;
        service: string;
        outbox_pending: number;
        outbox_failed: number;
      }>("/outbox-events/health/"),
    refetchInterval: 60_000,
  });
  const outbox = useQuery({
    queryKey: ["outbox-events", page],
    queryFn: () => getList<OutboxEvent>("/outbox-events/", { page, page_size: 25 }),
    enabled: tab === "outbox",
  });
  const webhooks = useQuery({
    queryKey: ["webhook-deliveries", page],
    queryFn: () => getList<WebhookDelivery>("/webhook-deliveries/", { page, page_size: 25 }),
    enabled: tab === "webhooks",
  });
  const refs = useQuery({
    queryKey: ["external-refs", page],
    queryFn: () => getList<ExternalRef>("/external-refs/", { page, page_size: 25 }),
    enabled: tab === "refs",
  });
  const seeds = useQuery({
    queryKey: ["seed-markers"],
    queryFn: () => getList<SeedMarker>("/seed-markers/", { page_size: 100 }),
    enabled: tab === "seeds",
  });

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Integration health"
        description="Monitor the transactional outbox, webhook deliveries and external references."
        actions={
          <>
            <Button onClick={() => void health.refetch()} busy={health.isFetching}>
              <RefreshCw size={16} aria-hidden="true" /> Refresh
            </Button>
            {tab === "refs" ? (
              <Button variant="primary" onClick={() => setEditor(true)}>
                <Plus size={16} aria-hidden="true" /> New reference
              </Button>
            ) : null}
          </>
        }
      />
      <div className="kpi-grid">
        <Stat
          label="Service"
          value={health.data?.status ? titleCase(health.data.status) : "—"}
          hint={health.data?.service ?? "tcms"}
          tone="brand"
        />
        <Stat
          label="Outbox pending"
          value={health.data?.outbox_pending ?? "—"}
          tone={health.data?.outbox_pending ? "warn" : "ok"}
        />
        <Stat
          label="Outbox failed"
          value={health.data?.outbox_failed ?? "—"}
          tone={health.data?.outbox_failed ? "danger" : "ok"}
        />
        <Stat label="Delivery model" value="At least once" hint="Idempotent handlers" />
      </div>

      <div className="tabs" role="tablist" aria-label="Integration sections">
        {(["outbox", "webhooks", "refs", "seeds"] as const).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={tab === item ? "tab active" : "tab"}
            onClick={() => {
              setTab(item);
              setPage(1);
            }}
          >
            {item === "outbox"
              ? "Outbox"
              : item === "webhooks"
                ? "Webhook deliveries"
                : item === "refs"
                  ? "External references"
                  : "Seed markers"}
          </button>
        ))}
      </div>

      {tab === "outbox" ? (
        <Card title="Outbox events">
          {outbox.isLoading ? <Loading rows={5} /> : null}
          {outbox.isError ? (
            <ErrorState message={firstError(outbox.error)} retry={() => void outbox.refetch()} />
          ) : null}
          {outbox.data ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Topic</th>
                      <th>Status</th>
                      <th className="num">Attempts</th>
                      <th>Created</th>
                      <th>Processed</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outbox.data.data.map((row) => (
                      <tr key={row.id}>
                        <td className="mono">{row.topic}</td>
                        <td>
                          <StatusBadge status={row.status} />
                        </td>
                        <td className="num">{row.attempts}</td>
                        <td>{formatDateTime(row.created_at)}</td>
                        <td>{formatDateTime(row.processed_at)}</td>
                        <td>{row.error || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={25}
                total={outbox.data.total}
                onPage={setPage}
              />
            </>
          ) : null}
        </Card>
      ) : null}

      {tab === "webhooks" ? (
        <Card title="Webhook deliveries">
          {webhooks.isLoading ? <Loading rows={5} /> : null}
          {webhooks.isError ? (
            <ErrorState
              message={firstError(webhooks.error)}
              retry={() => void webhooks.refetch()}
            />
          ) : null}
          {webhooks.data ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Event</th>
                      <th>URL</th>
                      <th>Status</th>
                      <th className="num">Attempts</th>
                      <th>Last error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {webhooks.data.data.map((row) => (
                      <tr key={row.id}>
                        <td className="mono">#{row.event}</td>
                        <td>{row.url}</td>
                        <td>
                          <StatusBadge status={row.status} />
                        </td>
                        <td className="num">{row.attempts}</td>
                        <td>{row.last_error || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={25}
                total={webhooks.data.total}
                onPage={setPage}
              />
            </>
          ) : null}
        </Card>
      ) : null}

      {tab === "refs" ? (
        <Card title="External references">
          {refs.isLoading ? <Loading rows={5} /> : null}
          {refs.isError ? (
            <ErrorState message={firstError(refs.error)} retry={() => void refs.refetch()} />
          ) : null}
          {refs.data ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>System</th>
                      <th>Entity</th>
                      <th>Entity ID</th>
                      <th>External ID</th>
                    </tr>
                  </thead>
                  <tbody>
                    {refs.data.data.map((row) => (
                      <tr key={row.id}>
                        <td>{row.system}</td>
                        <td>{row.entity}</td>
                        <td className="mono">#{row.entity_id}</td>
                        <td className="mono">{row.external_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={page}
                pageSize={25}
                total={refs.data.total}
                onPage={setPage}
              />
            </>
          ) : null}
        </Card>
      ) : null}

      {tab === "seeds" ? (
        <Card title="Seed markers">
          {seeds.isLoading ? <Loading rows={5} /> : null}
          {seeds.isError ? (
            <ErrorState message={firstError(seeds.error)} retry={() => void seeds.refetch()} />
          ) : null}
          {seeds.data ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Tier</th>
                    <th>Code</th>
                    <th>Applied</th>
                  </tr>
                </thead>
                <tbody>
                  {seeds.data.data.map((row) => (
                    <tr key={row.id}>
                      <td>{row.tier}</td>
                      <td className="mono">{row.code}</td>
                      <td>{formatDateTime(row.applied_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </Card>
      ) : null}

      {editor ? <ExternalRefEditor onClose={() => setEditor(false)} /> : null}
    </>
  );
}

function ReportAccessEditor({
  definition,
  roles,
  onClose,
}: {
  definition: ReportDef;
  roles: Role[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [selected, setSelected] = useState<number[]>(definition.roles);
  const save = useMutation({
    mutationFn: () =>
      request<ReportDef>(`/report-defs/${definition.id}/`, {
        method: "PATCH",
        body: JSON.stringify({ roles: selected }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["report-defs"] });
      toast.push("Report access updated.");
      onClose();
    },
  });

  function toggle(id: number) {
    setSelected((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title={`Access to ${definition.name}`}
      description={definition.code}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="report-access-form"
            variant="primary"
            busy={save.isPending}
          >
            Save access
          </Button>
        </>
      }
    >
      <form
        id="report-access-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {save.isError ? (
          <div className="form-error form-span" role="alert">
            {firstError(save.error)}
          </div>
        ) : null}
        <div className="check-grid">
          {roles.map((role) => (
            <label className="check" key={role.id}>
              <input
                type="checkbox"
                checked={selected.includes(role.id)}
                onChange={() => toggle(role.id)}
              />
              {role.name}
            </label>
          ))}
        </div>
      </form>
    </Modal>
  );
}

export function ReportAccessPage() {
  const { user } = useAuth();
  const [editing, setEditing] = useState<ReportDef | null>(null);
  const [query, setQuery] = useState("");
  const search = useDebounced(query);
  const definitions = useQuery({
    queryKey: ["report-defs", search],
    queryFn: () =>
      getList<ReportDef>("/report-defs/", {
        page_size: 200,
        ...(search ? { search } : {}),
      }),
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => getList<Role>("/roles/", { page_size: 100 }),
  });
  const roleById = new Map((roles.data?.data ?? []).map((role) => [role.id, role]));
  const editable = can(user, ["system_admin"]);

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Report access"
        description="Decide which roles can see each reporting dataset. Reports also enforce their own role checks."
        actions={
          <Button onClick={() => void definitions.refetch()}>
            <RefreshCw size={16} aria-hidden="true" /> Refresh
          </Button>
        }
      />
      <Card title="Reporting catalogue">
        <Toolbar>
          <SearchInput value={query} onChange={setQuery} placeholder="Search report code or name" />
          <span className="toolbar-count">{definitions.data?.total ?? 0} datasets</span>
        </Toolbar>
        {definitions.isLoading ? <Loading rows={5} /> : null}
        {definitions.isError ? (
          <ErrorState
            message={firstError(definitions.error)}
            retry={() => void definitions.refetch()}
          />
        ) : null}
        {definitions.data ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Report</th>
                  <th>Roles</th>
                  <th>View</th>
                  {editable ? <th /> : null}
                </tr>
              </thead>
              <tbody>
                {definitions.data.data.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{row.code}</td>
                    <td>{row.name}</td>
                    <td>
                      <div className="row-actions">
                        {row.roles.length ? (
                          row.roles.map((id) => (
                            <Badge key={id}>{roleById.get(id)?.name ?? `Role ${id}`}</Badge>
                          ))
                        ) : (
                          <span className="muted">No roles</span>
                        )}
                      </div>
                    </td>
                    <td className="mono">{row.sql_view}</td>
                    {editable ? (
                      <td>
                        <Button size="sm" onClick={() => setEditing(row)}>
                          <GitBranch size={14} aria-hidden="true" /> Access
                        </Button>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>

      {editing ? (
        <ReportAccessEditor
          definition={editing}
          roles={roles.data?.data ?? []}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}
