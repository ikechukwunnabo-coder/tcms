import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  BadgeDollarSign,
  Ban,
  Check,
  CircleDollarSign,
  FilePlus2,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { getList, request } from "../api/client";
import type { CorporateAccount, Invoice, Payment } from "../api/types";
import { useAuth } from "../auth/context";
import { BILLING_ROLES, can } from "../auth/roles";
import { LearnerPicker } from "../components/LearnerPicker";
import {
  Button,
  Card,
  ConfirmDialog,
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
  Textarea,
  Toolbar,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, formatDateTime, money, titleCase } from "../lib/format";
import { useDebounced } from "../lib/hooks";
import { useReference } from "../lib/useReference";

type Tab = "invoices" | "payments" | "accounts";

interface InvoiceLineDraft {
  description: string;
  quantity: string;
  unit_price: string;
}

function todayISO() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}

function InvoiceEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const references = useReference();
  const [account, setAccount] = useState("");
  const [learner, setLearner] = useState("");
  const [issueDate, setIssueDate] = useState(todayISO());
  const [dueDate, setDueDate] = useState("");
  const [currency, setCurrency] = useState("NGN");
  const [taxPct, setTaxPct] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<InvoiceLineDraft[]>([
    { description: "", quantity: "1", unit_price: "" },
  ]);

  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      request<Invoice>("/invoices/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (invoice) => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(`Invoice ${invoice.invoice_no} created.`);
      onClose();
    },
  });

  function setLine(index: number, key: keyof InvoiceLineDraft, value: string) {
    setLines((current) =>
      current.map((line, position) => (position === index ? { ...line, [key]: value } : line)),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      corporate_account: account ? Number(account) : null,
      learner: learner ? Number(learner) : null,
      issue_date: issueDate,
      due_date: dueDate || null,
      currency,
      tax_pct: taxPct ? Number(taxPct) : null,
      notes,
      lines: lines
        .filter((line) => line.description.trim() && line.unit_price)
        .map((line) => ({
          description: line.description.trim(),
          quantity: Number(line.quantity || 1),
          unit_price: Number(line.unit_price),
        })),
    });
  }

  return (
    <Modal
      open
      wide
      onClose={onClose}
      title="Create an invoice"
      description="Attach the invoice to a corporate account, an enrolment learner, or both."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="invoice-form" variant="primary" busy={create.isPending}>
            Create draft invoice
          </Button>
        </>
      }
    >
      <form id="invoice-form" className="form-grid" onSubmit={submit}>
        {create.isError ? (
          <div className="form-error form-span" role="alert">
            {errorMessage(create.error)}
          </div>
        ) : null}
        <Field label="Corporate account" htmlFor="invoice-account">
          <Select
            id="invoice-account"
            value={account}
            onChange={(event) => setAccount(event.target.value)}
          >
            <option value="">No corporate account</option>
            {(references.data?.accounts ?? []).map((row) => (
              <option value={row.id} key={row.id}>
                {row.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Learner" htmlFor="invoice-learner">
          <LearnerPicker id="invoice-learner" value={learner} onChange={setLearner} />
        </Field>
        <Field label="Issue date" htmlFor="invoice-issue">
          <Input
            id="invoice-issue"
            type="date"
            required
            value={issueDate}
            onChange={(event) => setIssueDate(event.target.value)}
          />
        </Field>
        <Field label="Due date" htmlFor="invoice-due">
          <Input
            id="invoice-due"
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
          />
        </Field>
        <Field label="Currency" htmlFor="invoice-currency">
          <Input
            id="invoice-currency"
            maxLength={3}
            value={currency}
            onChange={(event) => setCurrency(event.target.value.toUpperCase())}
          />
        </Field>
        <Field label="Tax %" htmlFor="invoice-tax" hint="Leave blank to use the centre default.">
          <Input
            id="invoice-tax"
            type="number"
            step="0.01"
            min="0"
            value={taxPct}
            onChange={(event) => setTaxPct(event.target.value)}
          />
        </Field>
        <div className="form-span">
          <div className="line-head">
            <h3>Invoice lines</h3>
            <Button
              size="sm"
              onClick={() =>
                setLines((current) => [
                  ...current,
                  { description: "", quantity: "1", unit_price: "" },
                ])
              }
            >
              <Plus size={14} aria-hidden="true" /> Add line
            </Button>
          </div>
          <div className="line-list">
            {lines.map((line, index) => (
              <div className="line-row" key={index}>
                <Input
                  aria-label={`Line ${index + 1} description`}
                  placeholder="Description"
                  required={index === 0}
                  value={line.description}
                  onChange={(event) => setLine(index, "description", event.target.value)}
                />
                <Input
                  aria-label={`Line ${index + 1} quantity`}
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={line.quantity}
                  onChange={(event) => setLine(index, "quantity", event.target.value)}
                />
                <Input
                  aria-label={`Line ${index + 1} unit price`}
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="Unit price"
                  required={index === 0}
                  value={line.unit_price}
                  onChange={(event) => setLine(index, "unit_price", event.target.value)}
                />
                <button
                  type="button"
                  className="icon-btn"
                  aria-label="Remove line"
                  disabled={lines.length === 1}
                  onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        </div>
        <Field label="Notes" htmlFor="invoice-notes" className="form-span">
          <Textarea
            id="invoice-notes"
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </Field>
      </form>
    </Modal>
  );
}

function PaymentEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const invoices = useQuery({
    queryKey: ["invoice-options"],
    queryFn: () => getList<Invoice>("/invoices/", { page_size: 150 }),
  });
  const [invoiceId, setInvoiceId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("transfer");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");

  const openInvoices = (invoices.data?.data ?? []).filter((invoice) =>
    ["draft", "issued", "part_paid"].includes(invoice.status),
  );

  const create = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      request<Payment>("/payments/", { method: "POST", body: JSON.stringify(payload) }),
    onSuccess: (payment) => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(`Payment ${payment.payment_ref} recorded.`);
      onClose();
    },
  });

  function pickInvoice(value: string) {
    setInvoiceId(value);
    const invoice = openInvoices.find((row) => String(row.id) === value);
    if (invoice) setAmount(invoice.balance);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      invoice: Number(invoiceId),
      amount: Number(amount),
      method,
      payment_ref: reference.trim(),
      notes,
      confirm: true,
    });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Record a payment"
      description="Confirmed payments update the invoice balance and the centre's collections position."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="payment-form" variant="primary" busy={create.isPending}>
            Record payment
          </Button>
        </>
      }
    >
      <form id="payment-form" className="form-stack" onSubmit={submit}>
        {create.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(create.error)}
          </div>
        ) : null}
        <Field label="Invoice" htmlFor="payment-invoice">
          <Select
            id="payment-invoice"
            required
            value={invoiceId}
            onChange={(event) => pickInvoice(event.target.value)}
          >
            <option value="">
              {invoices.isLoading ? "Loading invoices…" : "Choose an invoice"}
            </option>
            {openInvoices.map((invoice) => (
              <option value={invoice.id} key={invoice.id}>
                {invoice.invoice_no} · {invoice.learner_name || invoice.corporate_account_name} ·{" "}
                {money(invoice.balance, invoice.currency)} due
              </option>
            ))}
          </Select>
        </Field>
        <div className="form-grid">
          <Field label="Amount" htmlFor="payment-amount">
            <Input
              id="payment-amount"
              type="number"
              min="0.01"
              step="0.01"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
          </Field>
          <Field label="Method" htmlFor="payment-method">
            <Select
              id="payment-method"
              value={method}
              onChange={(event) => setMethod(event.target.value)}
            >
              {["transfer", "cash", "card", "cheque", "other"].map((option) => (
                <option value={option} key={option}>
                  {titleCase(option)}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <Field label="Payment reference" htmlFor="payment-ref" hint="Optional — the server generates one.">
          <Input
            id="payment-ref"
            value={reference}
            onChange={(event) => setReference(event.target.value)}
          />
        </Field>
        <Field label="Notes" htmlFor="payment-notes">
          <Textarea
            id="payment-notes"
            rows={2}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </Field>
      </form>
    </Modal>
  );
}

function AccountEditor({
  account,
  onClose,
}: {
  account?: CorporateAccount;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const references = useReference();
  const [form, setForm] = useState({
    name: account?.name ?? "",
    company: account?.company ? String(account.company) : "",
    lead_email: account?.lead_email ?? "",
    credit_limit: account?.credit_limit ?? "",
    terms_days: account ? String(account.terms_days) : "30",
  });

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      account
        ? request<CorporateAccount>(`/corporate-accounts/${account.id}/`, {
            method: "PATCH",
            body: JSON.stringify(payload),
          })
        : request<CorporateAccount>("/corporate-accounts/", {
            method: "POST",
            body: JSON.stringify(payload),
          }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["accounts"] });
      void queryClient.invalidateQueries({ queryKey: ["reference"] });
      toast.push(account ? "Corporate account updated." : "Corporate account created.");
      onClose();
    },
  });

  function set(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate({
      name: form.name.trim(),
      company: form.company ? Number(form.company) : null,
      lead_email: form.lead_email.trim(),
      credit_limit: form.credit_limit ? form.credit_limit : null,
      terms_days: Number(form.terms_days || 30),
    });
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={account ? "Edit corporate account" : "New corporate account"}
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" form="account-form" variant="primary" busy={save.isPending}>
            {account ? "Save account" : "Create account"}
          </Button>
        </>
      }
    >
      <form id="account-form" className="form-stack" onSubmit={submit}>
        {save.isError ? (
          <div className="form-error" role="alert">
            {errorMessage(save.error)}
          </div>
        ) : null}
        <Field label="Account name" htmlFor="account-name">
          <Input
            id="account-name"
            required
            value={form.name}
            onChange={(event) => set("name", event.target.value)}
          />
        </Field>
        <Field label="Company" htmlFor="account-company">
          <Select
            id="account-company"
            value={form.company}
            onChange={(event) => set("company", event.target.value)}
          >
            <option value="">Not linked</option>
            {(references.data?.companies ?? []).map((company) => (
              <option value={company.id} key={company.id}>
                {company.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Lead email" htmlFor="account-email">
          <Input
            id="account-email"
            type="email"
            value={form.lead_email}
            onChange={(event) => set("lead_email", event.target.value)}
          />
        </Field>
        <div className="form-grid">
          <Field label="Credit limit" htmlFor="account-limit" hint="Leave blank for no limit.">
            <Input
              id="account-limit"
              type="number"
              min="0"
              step="0.01"
              value={form.credit_limit}
              onChange={(event) => set("credit_limit", event.target.value)}
            />
          </Field>
          <Field label="Terms (days)" htmlFor="account-terms">
            <Input
              id="account-terms"
              type="number"
              min="0"
              value={form.terms_days}
              onChange={(event) => set("terms_days", event.target.value)}
            />
          </Field>
        </div>
      </form>
    </Modal>
  );
}

export function BillingPage() {
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab = (["invoices", "payments", "accounts"].includes(params.get("tab") ?? "")
    ? params.get("tab")
    : "invoices") as Tab;
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [invoiceEditor, setInvoiceEditor] = useState(false);
  const [paymentEditor, setPaymentEditor] = useState(false);
  const [accountEditor, setAccountEditor] = useState<{ account?: CorporateAccount } | null>(null);
  const [voiding, setVoiding] = useState<Invoice | null>(null);
  const search = useDebounced(query);

  const invoices = useQuery({
    queryKey: ["invoices", search, status, page],
    queryFn: () =>
      getList<Invoice>("/invoices/", { search, status, page, page_size: 25 }),
    enabled: tab === "invoices",
  });
  const payments = useQuery({
    queryKey: ["payments", search, status, page],
    queryFn: () =>
      getList<Payment>("/payments/", { search, status, page, page_size: 25 }),
    enabled: tab === "payments",
  });
  const accounts = useQuery({
    queryKey: ["accounts", search, page],
    queryFn: () => getList<CorporateAccount>("/corporate-accounts/", { search, page, page_size: 25 }),
    enabled: tab === "accounts",
  });

  const invoiceAction = useMutation({
    mutationFn: ({ invoice, action, reason }: { invoice: Invoice; action: string; reason?: string }) =>
      request<Invoice>(`/invoices/${invoice.id}/${action}/`, {
        method: "POST",
        body: JSON.stringify(reason ? { reason } : {}),
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push(variables.action === "issue" ? "Invoice issued." : "Invoice voided.");
      setVoiding(null);
    },
  });

  const paymentAction = useMutation({
    mutationFn: (payment: Payment) =>
      request<Payment>(`/payments/${payment.id}/confirm/`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payments"] });
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.push("Payment confirmed.");
    },
  });

  if (!can(user, BILLING_ROLES)) {
    return (
      <EmptyState
        title="Billing is restricted"
        body="Your role does not include access to invoices, payments or corporate accounts."
      />
    );
  }

  function changeTab(next: Tab) {
    setParams(next === "invoices" ? {} : { tab: next });
    setQuery("");
    setStatus("");
    setPage(1);
  }

  const loading =
    (tab === "invoices" && invoices.isLoading) ||
    (tab === "payments" && payments.isLoading) ||
    (tab === "accounts" && accounts.isLoading);
  const failed =
    (tab === "invoices" && invoices.isError) ||
    (tab === "payments" && payments.isError) ||
    (tab === "accounts" && accounts.isError);

  if (loading) return <Loading rows={7} />;
  if (failed) {
    return (
      <ErrorState
        message={errorMessage(
          tab === "invoices" ? invoices.error : tab === "payments" ? payments.error : accounts.error,
        )}
        retry={() => {
          if (tab === "invoices") void invoices.refetch();
          else if (tab === "payments") void payments.refetch();
          else void accounts.refetch();
        }}
      />
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Finance"
        title="Billing"
        description="Invoices, verified payments and corporate account positions."
        actions={
          <>
            <CsvButton
              dataset={tab === "payments" ? "payments" : "invoices"}
              label="Export CSV"
            />
            {tab === "invoices" ? (
              <Button variant="primary" onClick={() => setInvoiceEditor(true)}>
                <FilePlus2 size={16} aria-hidden="true" /> New invoice
              </Button>
            ) : null}
            {tab === "payments" ? (
              <Button variant="primary" onClick={() => setPaymentEditor(true)}>
                <CircleDollarSign size={16} aria-hidden="true" /> Record payment
              </Button>
            ) : null}
            {tab === "accounts" ? (
              <Button variant="primary" onClick={() => setAccountEditor({})}>
                <Plus size={16} aria-hidden="true" /> New account
              </Button>
            ) : null}
          </>
        }
      />

      <div className="tabs" role="tablist" aria-label="Billing sections">
        {(["invoices", "payments", "accounts"] as Tab[]).map((item) => (
          <button
            key={item}
            type="button"
            role="tab"
            aria-selected={tab === item}
            className={tab === item ? "tab active" : "tab"}
            onClick={() => changeTab(item)}
          >
            {titleCase(item)}
          </button>
        ))}
      </div>

      <Card>
        <Toolbar>
          <SearchInput
            value={query}
            onChange={(value) => {
              setQuery(value);
              setPage(1);
            }}
            placeholder={
              tab === "invoices"
                ? "Search invoice no, badge or surname"
                : tab === "payments"
                  ? "Search payment ref or invoice no"
                  : "Search account, company or lead email"
            }
          />
          {tab !== "accounts" ? (
            <Select
              aria-label="Filter by status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              {(tab === "invoices"
                ? ["draft", "issued", "part_paid", "paid", "void"]
                : ["pending", "confirmed", "failed", "refunded"]
              ).map((option) => (
                <option value={option} key={option}>
                  {titleCase(option)}
                </option>
              ))}
            </Select>
          ) : null}
        </Toolbar>

        {tab === "invoices" && invoices.data ? (
          invoices.data.data.length ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Billed to</th>
                      <th>Issued</th>
                      <th>Due</th>
                      <th className="num">Total</th>
                      <th className="num">Balance</th>
                      <th>Status</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.data.data.map((invoice) => (
                      <tr key={invoice.id}>
                        <td className="mono">{invoice.invoice_no}</td>
                        <td>
                          <strong>{invoice.learner_name || invoice.corporate_account_name}</strong>
                          <div className="cell-sub">
                            {invoice.learner_name ? invoice.corporate_account_name || "Individual" : "Corporate"}
                          </div>
                        </td>
                        <td>{formatDate(invoice.issue_date)}</td>
                        <td>{formatDate(invoice.due_date)}</td>
                        <td className="num">{money(invoice.total, invoice.currency)}</td>
                        <td className="num">{money(invoice.balance, invoice.currency)}</td>
                        <td>
                          <StatusBadge status={invoice.status} />
                        </td>
                        <td className="row-actions">
                          {invoice.status === "draft" ? (
                            <Button
                              size="sm"
                              busy={invoiceAction.isPending}
                              onClick={() =>
                                invoiceAction.mutate({ invoice, action: "issue" })
                              }
                            >
                              <Check size={14} aria-hidden="true" /> Issue
                            </Button>
                          ) : null}
                          {["issued", "part_paid"].includes(invoice.status) ? (
                            <Button
                              size="sm"
                              variant="danger"
                              onClick={() => setVoiding(invoice)}
                            >
                              <Ban size={14} aria-hidden="true" /> Void
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={invoices.data.page}
                pageSize={invoices.data.page_size}
                total={invoices.data.total}
                onPage={setPage}
              />
            </>
          ) : (
            <EmptyState
              title="No invoices found"
              body="Adjust the filters or create a draft invoice."
              action={
                <Button variant="primary" onClick={() => setInvoiceEditor(true)}>
                  New invoice
                </Button>
              }
            />
          )
        ) : null}

        {tab === "payments" && payments.data ? (
          payments.data.data.length ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Payment</th>
                      <th>Invoice</th>
                      <th>Paid</th>
                      <th>Method</th>
                      <th className="num">Amount</th>
                      <th>Status</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {payments.data.data.map((payment) => (
                      <tr key={payment.id}>
                        <td className="mono">{payment.payment_ref}</td>
                        <td className="mono">{payment.invoice_no}</td>
                        <td>{formatDateTime(payment.paid_at)}</td>
                        <td>{titleCase(payment.method)}</td>
                        <td className="num">{money(payment.amount)}</td>
                        <td>
                          <StatusBadge status={payment.status} />
                        </td>
                        <td className="row-actions">
                          {payment.status === "pending" ? (
                            <Button
                              size="sm"
                              busy={paymentAction.isPending}
                              onClick={() => paymentAction.mutate(payment)}
                            >
                              <BadgeDollarSign size={14} aria-hidden="true" /> Confirm
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={payments.data.page}
                pageSize={payments.data.page_size}
                total={payments.data.total}
                onPage={setPage}
              />
            </>
          ) : (
            <EmptyState
              title="No payments found"
              body="Record a payment against an open invoice."
              action={
                <Button variant="primary" onClick={() => setPaymentEditor(true)}>
                  Record payment
                </Button>
              }
            />
          )
        ) : null}

        {tab === "accounts" && accounts.data ? (
          accounts.data.data.length ? (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Account</th>
                      <th>Lead</th>
                      <th>Terms</th>
                      <th className="num">Balance</th>
                      <th className="num">Nominees</th>
                      <th>Status</th>
                      <th aria-label="Actions" />
                    </tr>
                  </thead>
                  <tbody>
                    {accounts.data.data.map((account) => (
                      <tr key={account.id}>
                        <td>
                          <strong>{account.name}</strong>
                          <div className="cell-sub">
                            {account.company ? `Company #${account.company}` : "No company link"}
                          </div>
                        </td>
                        <td>{account.lead_email || "—"}</td>
                        <td>{account.terms_days} days</td>
                        <td className="num">{money(account.balance)}</td>
                        <td className="num">{account.nominee_count}</td>
                        <td>
                          <StatusBadge
                            status={account.active ? "active" : "inactive"}
                            label={account.active ? "Active" : "Inactive"}
                          />
                        </td>
                        <td className="row-actions">
                          <Button
                            size="sm"
                            onClick={() => setAccountEditor({ account })}
                          >
                            <Pencil size={14} aria-hidden="true" /> Edit
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={accounts.data.page}
                pageSize={accounts.data.page_size}
                total={accounts.data.total}
                onPage={setPage}
              />
            </>
          ) : (
            <EmptyState
              title="No corporate accounts"
              body="Create an account to invoice nominees and track terms."
              action={
                <Button variant="primary" onClick={() => setAccountEditor({})}>
                  New account
                </Button>
              }
            />
          )
        ) : null}
      </Card>

      <ConfirmDialog
        open={Boolean(voiding)}
        title="Void this invoice"
        message={`Void ${voiding?.invoice_no ?? ""}? This removes it from the outstanding balance and cannot be undone from the console.`}
        confirmLabel="Void invoice"
        tone="danger"
        busy={invoiceAction.isPending}
        onConfirm={() => {
          if (voiding) {
            invoiceAction.mutate({
              invoice: voiding,
              action: "void",
              reason: "Voided from the staff operations console.",
            });
          }
        }}
        onClose={() => setVoiding(null)}
      />

      {invoiceAction.isError ? (
        <div className="form-error floating-error" role="alert">
          {errorMessage(invoiceAction.error)}
        </div>
      ) : null}
      {paymentAction.isError ? (
        <div className="form-error floating-error" role="alert">
          {errorMessage(paymentAction.error)}
        </div>
      ) : null}

      {invoiceEditor ? <InvoiceEditor onClose={() => setInvoiceEditor(false)} /> : null}
      {paymentEditor ? <PaymentEditor onClose={() => setPaymentEditor(false)} /> : null}
      {accountEditor ? (
        <AccountEditor
          account={accountEditor.account}
          onClose={() => setAccountEditor(null)}
        />
      ) : null}
    </>
  );
}
