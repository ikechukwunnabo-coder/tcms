import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ListChecks, Pencil } from "lucide-react";
import { request } from "../api/client";
import type {
  CertificateType,
  Course,
  CourseItem,
  CourseItemRelation,
  CourseModule,
  CourseModuleRelation,
} from "../api/types";
import { useAuth } from "../auth/context";
import { USER_ADMIN_ROLES, can } from "../auth/roles";
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
  SearchInput,
  Select,
  Textarea,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage } from "../lib/format";
import { useReference } from "../lib/useReference";

const EXPIRY_TYPES = [
  { value: 0, label: "No expiry" },
  { value: 1, label: "Calculated automatically" },
  { value: 2, label: "FOET expiration date calculation" },
];

function CourseEditor({
  course,
  certificateTypes,
  onClose,
}: {
  course: Course;
  certificateTypes: CertificateType[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState({
    name: course.name,
    cert_type: course.cert_type ?? "",
    expiry_type: course.expiry_type,
    duration_days: course.duration_days ?? "",
    validity_years: course.validity_years ?? "",
    id_card: course.id_card,
    foet_required: course.foet_required,
    opito_reg_code: course.opito_reg_code,
    front_id_text: course.front_id_text,
    back_id_text: course.back_id_text,
    active: course.active,
  });

  const save = useMutation({
    mutationFn: () =>
      request<Course>(`/courses/${course.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          name: draft.name,
          cert_type: draft.cert_type === "" ? null : Number(draft.cert_type),
          expiry_type: Number(draft.expiry_type),
          duration_days: draft.duration_days === "" ? null : Number(draft.duration_days),
          validity_years: draft.validity_years === "" ? null : Number(draft.validity_years),
          id_card: draft.id_card,
          foet_required: draft.foet_required,
          opito_reg_code: draft.opito_reg_code,
          front_id_text: draft.front_id_text,
          back_id_text: draft.back_id_text,
          active: draft.active,
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["reference"] });
      toast.push(`${course.course_code} updated.`);
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
      title={`Edit ${course.course_code}`}
      description="Certificate type and expiry rules are applied when a certificate is issued."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="course-form" variant="primary" busy={save.isPending}>
            Save course
          </Button>
        </>
      }
    >
      <form id="course-form" className="form-stack" onSubmit={submit}>
        {save.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        <Field label="Course name" htmlFor="course-name">
          <Input
            id="course-name"
            required
            value={draft.name}
            onChange={(event) => setDraft({ ...draft, name: event.target.value })}
          />
        </Field>
        <div className="form-grid">
          <Field label="Certificate type" htmlFor="course-cert-type">
            <Select
              id="course-cert-type"
              value={draft.cert_type}
              onChange={(event) => setDraft({ ...draft, cert_type: event.target.value })}
            >
              <option value="">None</option>
              {certificateTypes.map((type) => (
                <option value={type.id} key={type.id}>
                  {type.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Expiry rule" htmlFor="course-expiry-type">
            <Select
              id="course-expiry-type"
              value={draft.expiry_type}
              onChange={(event) =>
                setDraft({ ...draft, expiry_type: Number(event.target.value) })
              }
            >
              {EXPIRY_TYPES.map((type) => (
                <option value={type.value} key={type.value}>
                  {type.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="form-grid">
          <Field label="Duration (days)" htmlFor="course-duration">
            <Input
              id="course-duration"
              type="number"
              min={1}
              value={draft.duration_days}
              onChange={(event) =>
                setDraft({ ...draft, duration_days: event.target.value })
              }
            />
          </Field>
          <Field label="Validity (years)" htmlFor="course-validity">
            <Input
              id="course-validity"
              type="number"
              min={0}
              value={draft.validity_years}
              onChange={(event) =>
                setDraft({ ...draft, validity_years: event.target.value })
              }
            />
          </Field>
        </div>
        <Field
          label="OPITO registration code"
          htmlFor="course-opito"
          hint="Courses with a code are migrated to the OPITO certificate type."
        >
          <Input
            id="course-opito"
            value={draft.opito_reg_code}
            onChange={(event) => setDraft({ ...draft, opito_reg_code: event.target.value })}
          />
        </Field>
        <Field label="Front ID card text" htmlFor="course-front-id">
          <Textarea
            id="course-front-id"
            rows={3}
            value={draft.front_id_text}
            onChange={(event) => setDraft({ ...draft, front_id_text: event.target.value })}
          />
        </Field>
        <Field label="Back ID card text" htmlFor="course-back-id">
          <Textarea
            id="course-back-id"
            rows={3}
            value={draft.back_id_text}
            onChange={(event) => setDraft({ ...draft, back_id_text: event.target.value })}
          />
        </Field>
        <div className="form-checks">
          <label>
            <input
              type="checkbox"
              checked={draft.id_card}
              onChange={(event) => setDraft({ ...draft, id_card: event.target.checked })}
            />
            Issue an ID card
          </label>
          <label>
            <input
              type="checkbox"
              checked={draft.foet_required}
              onChange={(event) =>
                setDraft({ ...draft, foet_required: event.target.checked })
              }
            />
            FOET required
          </label>
          <label>
            <input
              type="checkbox"
              checked={draft.active}
              onChange={(event) => setDraft({ ...draft, active: event.target.checked })}
            />
            Active
          </label>
        </div>
      </form>
    </Modal>
  );
}

function CourseContentEditor({
  course,
  modules,
  items,
  onClose,
}: {
  course: Course;
  modules: CourseModule[];
  items: CourseItem[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [moduleIds, setModuleIds] = useState<number[] | null>(null);
  const [itemIds, setItemIds] = useState<number[] | null>(null);

  const assignedModules = useQuery({
    queryKey: ["course-module-rel", course.id],
    queryFn: () => request<CourseModuleRelation[]>(`/course-module-rel/${course.id}`),
  });
  const assignedItems = useQuery({
    queryKey: ["course-item-rel", course.id],
    queryFn: () => request<CourseItemRelation[]>(`/course-item-rel/${course.id}`),
  });

  useEffect(() => {
    if (assignedModules.data && moduleIds === null) {
      setModuleIds(assignedModules.data.map((row) => row.module));
    }
  }, [assignedModules.data, moduleIds]);
  useEffect(() => {
    if (assignedItems.data && itemIds === null) {
      setItemIds(assignedItems.data.map((row) => row.item));
    }
  }, [assignedItems.data, itemIds]);

  const save = useMutation({
    mutationFn: async () => {
      const selectedModules = new Set(moduleIds ?? []);
      const selectedItems = new Set(itemIds ?? []);
      const initialModules = new Set(assignedModules.data?.map((row) => row.module) ?? []);
      const initialItems = new Set(assignedItems.data?.map((row) => row.item) ?? []);
      const addedModules = [...selectedModules].filter((id) => !initialModules.has(id));
      const addedItems = [...selectedItems].filter((id) => !initialItems.has(id));
      const removedModules =
        assignedModules.data?.filter((row) => !selectedModules.has(row.module)) ?? [];
      const removedItems =
        assignedItems.data?.filter((row) => !selectedItems.has(row.item)) ?? [];

      await Promise.all([
        addedModules.length
          ? request("/course-module-rel", {
              method: "POST",
              body: JSON.stringify({ parent: course.id, children: addedModules }),
            })
          : null,
        addedItems.length
          ? request("/course-item-rel", {
              method: "POST",
              body: JSON.stringify({ parent: course.id, children: addedItems }),
            })
          : null,
        ...removedModules.map((row) =>
          request(`/course-module-rel/${row.id}`, { method: "DELETE" }),
        ),
        ...removedItems.map((row) =>
          request(`/course-item-rel/${row.id}`, { method: "DELETE" }),
        ),
      ]);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["course-module-rel", course.id] });
      void queryClient.invalidateQueries({ queryKey: ["course-item-rel", course.id] });
      toast.push(`Content updated for ${course.course_code}.`);
      onClose();
    },
  });

  const loading = assignedModules.isLoading || assignedItems.isLoading;
  const failed = assignedModules.isError || assignedItems.isError;
  const ready = moduleIds !== null && itemIds !== null;

  function toggle(id: number, values: number[], setter: (next: number[]) => void) {
    setter(values.includes(id) ? values.filter((value) => value !== id) : [...values, id]);
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Manage content — ${course.course_code}`}
      description="Assign the shared modules and checklist items that make up this course."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="course-content-form"
            variant="primary"
            busy={save.isPending}
            disabled={!ready || loading || failed}
          >
            Save content
          </Button>
        </>
      }
    >
      <form
        id="course-content-form"
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        {save.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        {loading ? <Loading rows={4} /> : null}
        {failed ? (
          <ErrorState
            message={errorMessage(assignedModules.error ?? assignedItems.error)}
            retry={() => {
              void assignedModules.refetch();
              void assignedItems.refetch();
            }}
          />
        ) : null}
        {ready ? (
          <div className="relation-columns">
            <fieldset className="relation-list">
              <legend>Modules</legend>
              {modules.map((module) => (
                <label key={module.id}>
                  <input
                    type="checkbox"
                    checked={moduleIds.includes(module.id)}
                    onChange={() => toggle(module.id, moduleIds, setModuleIds)}
                  />
                  {module.name}
                </label>
              ))}
              {!modules.length ? <p className="muted">No modules defined.</p> : null}
            </fieldset>
            <fieldset className="relation-list">
              <legend>Items</legend>
              {items.map((item) => (
                <label key={item.id}>
                  <input
                    type="checkbox"
                    checked={itemIds.includes(item.id)}
                    onChange={() => toggle(item.id, itemIds, setItemIds)}
                  />
                  {item.name}
                </label>
              ))}
              {!items.length ? <p className="muted">No items defined.</p> : null}
            </fieldset>
          </div>
        ) : null}
      </form>
    </Modal>
  );
}

export function CoursesPage() {
  const { user } = useAuth();
  const reference = useReference();
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Course | null>(null);
  const [contentCourse, setContentCourse] = useState<Course | null>(null);

  if (reference.isLoading) return <Loading rows={8} />;
  if (reference.isError || !reference.data) {
    return (
      <ErrorState
        message={errorMessage(reference.error)}
        retry={() => void reference.refetch()}
      />
    );
  }

  const term = query.trim().toLowerCase();
  const courses = reference.data.courses.filter((course) =>
    [course.course_code, course.name, course.opito_reg_code]
      .join(" ")
      .toLowerCase()
      .includes(term),
  );
  const certificateTypes = reference.data.certificateTypes;
  const certificateTypeName = (id: number | null) =>
    certificateTypes.find((type) => type.id === id)?.name ?? "—";
  const expiryName = (id: number) =>
    EXPIRY_TYPES.find((type) => type.value === id)?.label ?? "—";

  return (
    <>
      <PageHeader
        eyebrow="Course setup"
        title="Courses"
        description="Certificate type, expiry rules, ID-card text and OPITO registration in one place."
      />
      <Card>
        <Toolbar>
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="Search course code, name or OPITO code"
          />
          <span className="toolbar-count">{courses.length} courses</span>
        </Toolbar>
        {courses.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Course</th>
                  <th>Certificate</th>
                  <th>Expiry</th>
                  <th>Validity</th>
                  <th>ID card</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {courses.map((course) => (
                  <tr key={course.id}>
                    <td>
                      <strong>{course.course_code}</strong>
                      <div className="cell-sub">{course.name}</div>
                    </td>
                    <td>{certificateTypeName(course.cert_type)}</td>
                    <td>{expiryName(course.expiry_type)}</td>
                    <td>{course.validity_years ? `${course.validity_years} yr` : "—"}</td>
                    <td>
                      <Badge tone={course.id_card ? "brand" : "neutral"}>
                        {course.id_card ? "Yes" : "No"}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone={course.active ? "ok" : "neutral"}>
                        {course.active ? "Active" : "Inactive"}
                      </Badge>
                    </td>
                    <td className="row-actions">
                      {can(user, USER_ADMIN_ROLES) ? (
                        <Button size="sm" onClick={() => setContentCourse(course)}>
                          <ListChecks size={14} aria-hidden="true" /> Content
                        </Button>
                      ) : null}
                      <Button size="sm" onClick={() => setEditing(course)}>
                        <Pencil size={14} aria-hidden="true" /> Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No courses found"
            body={query ? "No course matches this search." : "Seed the course catalogue first."}
            action={
              <Button onClick={() => void reference.refetch()}>
                <BookOpen size={16} aria-hidden="true" /> Refresh
              </Button>
            }
          />
        )}
      </Card>
      {editing ? (
        <CourseEditor
          course={editing}
          certificateTypes={certificateTypes}
          onClose={() => setEditing(null)}
        />
      ) : null}
      {contentCourse ? (
        <CourseContentEditor
          course={contentCourse}
          modules={reference.data.modules}
          items={reference.data.items}
          onClose={() => setContentCourse(null)}
        />
      ) : null}
    </>
  );
}
