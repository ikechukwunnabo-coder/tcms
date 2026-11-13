import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  BadgeCheck,
  Banknote,
  BookOpenCheck,
  Calculator,
  Check,
  Download,
  FileDown,
  Landmark,
  Plus,
  RefreshCw,
  Send,
  ShieldAlert,
  WalletCards,
} from "lucide-react";
import { downloadPaymentFile, getList, request } from "../api/client";
import type {
  Account,
  AccountType,
  Journal,
  PayElement,
  PaymentFile,
  PayRun,
  Payslip,
  TaxBand,
  TrialBalanceRow,
} from "../api/types";
import { useAuth } from "../auth/context";
import { FINANCE_ROLES, can } from "../auth/roles";
import { downloadCsv } from "../api/client";
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
  Select,
  Stat,
  StatusBadge,
  Textarea,
} from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDate, money, titleCase } from "../lib/format";

type Tab =
  | "overview"
  | "accounts"
  | "journals"
  | "pay-runs"
  | "payslips"
  | "payment-files"
  | "policy";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "accounts", label: "Chart of accounts" },
  { id: "journals", label: "Journals & trial balance" },
  { id: "pay-runs", label: "Pay runs" },
  { id: "payslips", label: "Payslips" },
  { id: "payment-files", label: "Payment files" },
  { id: "policy", label: "Pay policy & tax" },
];

function todayISO() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 10);
}

function firstError(error: unknown) {
  return errorMessage(error);
}

function AccountEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState<AccountType>("expense");

  const create = useMutation({
    mutationFn: () =>
      request<Account>("/accounts/", {
        method: "POST",
        body: JSON.stringify({ code, name, type, active: true }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["finance-accounts"] });
      toast.push("Account created.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="New account"
      description="Create a ledger account for journals and payroll postings."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            type="submit"
            form="account-form"
            busy={create.isPending}
          >
            Create account
          </Button>
        </>
      }
    >
      <form
        id="account-form"
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
        <Field label="Code" htmlFor="account-code">
          <Input
            id="account-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            required
          />
        </Field>
        <Field label="Name" htmlFor="account-name">
          <Input
            id="account-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </Field>
        <Field label="Type" htmlFor="account-type">
          <Select
            id="account-type"
            value={type}
            onChange={(event) => setType(event.target.value as AccountType)}
          >
            {(["asset", "liability", "equity", "income", "expense"] as AccountType[]).map(
              (value) => (
                <option value={value} key={value}>
                  {titleCase(value)}
                </option>
              ),
            )}
          </Select>
        </Field>
      </form>
    </Modal>
  );
}

function JournalEditor({
  accounts,
  onClose,
}: {
  accounts: Account[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [date, setDate] = useState(todayISO());
  const [memo, setMemo] = useState("");
  const [debitAccount, setDebitAccount] = useState("");
  const [creditAccount, setCreditAccount] = useState("");
  const [amount, setAmount] = useState("");

  const create = useMutation({
    mutationFn: () =>
      request<Journal>("/journal-entries/", {
        method: "POST",
        body: JSON.stringify({
          date,
          memo,
          source: "manual",
          lines: [
            { account: Number(debitAccount), debit: Number(amount), credit: 0 },
            { account: Number(creditAccount), debit: 0, credit: Number(amount) },
          ],
        }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["finance-journals"] });
      void queryClient.invalidateQueries({ queryKey: ["finance-trial-balance"] });
      toast.push("Draft journal created.");
      onClose();
    },
  });

  const balanced =
    debitAccount && creditAccount && debitAccount !== creditAccount && Number(amount) > 0;

  return (
    <Modal
      open
      onClose={onClose}
      title="New journal"
      description="Create a balanced two-line journal. Post it after review."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="primary"
            type="submit"
            form="journal-form"
            busy={create.isPending}
            disabled={!balanced}
          >
            Create draft
          </Button>
        </>
      }
    >
      <form
        id="journal-form"
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
        <Field label="Date" htmlFor="journal-date">
          <Input
            id="journal-date"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
            required
          />
        </Field>
        <Field label="Amount" htmlFor="journal-amount">
          <Input
            id="journal-amount"
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            required
          />
        </Field>
        <Field label="Debit account" htmlFor="journal-debit">
          <Select
            id="journal-debit"
            value={debitAccount}
            onChange={(event) => setDebitAccount(event.target.value)}
            required
          >
            <option value="">Choose account</option>
            {accounts.map((account) => (
              <option value={account.id} key={account.id}>
                {account.code} · {account.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Credit account" htmlFor="journal-credit">
          <Select
            id="journal-credit"
            value={creditAccount}
            onChange={(event) => setCreditAccount(event.target.value)}
            required
          >
            <option value="">Choose account</option>
            {accounts.map((account) => (
              <option value={account.id} key={account.id}>
                {account.code} · {account.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Memo" htmlFor="journal-memo" className="form-span">
          <Textarea
            id="journal-memo"
            rows={3}
            value={memo}
            onChange={(event) => setMemo(event.target.value)}
          />
        </Field>
      </form>
    </Modal>
  );
}

function PayRunEditor({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [period, setPeriod] = useState(todayISO().slice(0, 7));
  const [runDate, setRunDate] = useState(todayISO());

  const create = useMutation({
    mutationFn: () =>
      request<PayRun>("/pay-runs/", {
        method: "POST",
        body: JSON.stringify({ period, run_date: runDate }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["finance-pay-runs"] });
      toast.push("Pay run created. Compute it when employees are ready.");
      onClose();
    },
  });

  return (
    <Modal
      open
      onClose={onClose}
      title="New pay run"
      description="Start a payroll period. No payments are made until the run is approved and posted."
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            type="submit"
            form="pay-run-form"
            variant="primary"
            busy={create.isPending}
          >
            Create pay run
          </Button>
        </>
      }
    >
      <form
        id="pay-run-form"
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
        <Field label="Period" htmlFor="pay-run-period" hint="Use YYYY-MM.">
          <Input
            id="pay-run-period"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            pattern="\d{4}-\d{2}"
            required
          />
        </Field>
        <Field label="Run date" htmlFor="pay-run-date">
          <Input
            id="pay-run-date"
            type="date"
            value={runDate}
            onChange={(event) => setRunDate(event.target.value)}
            required
          />
        </Field>
      </form>
    </Modal>
  );
}

function Overview({ financeWrite }: { financeWrite: boolean }) {
  const trial = useQuery({
    queryKey: ["finance-trial-balance"],
    queryFn: () => request<TrialBalanceRow[]>("/journal-entries/trial-balance/"),
  });
  const journals = useQuery({
    queryKey: ["finance-journals", "overview"],
    queryFn: () => getList<Journal>("/journal-entries/", { page_size: 5 }),
  });
  const runs = useQuery({
    queryKey: ["finance-pay-runs", "overview"],
    queryFn: () => getList<PayRun>("/pay-runs/", { page_size: 5 }),
  });
  const files = useQuery({
    queryKey: ["finance-payment-files", "overview"],
    queryFn: () => getList<PaymentFile>("/payment-files/", { page_size: 5 }),
  });

  if (trial.isLoading || journals.isLoading || runs.isLoading || files.isLoading) {
    return <Loading rows={5} />;
  }
  if (trial.isError || journals.isError || runs.isError || files.isError) {
    return (
      <ErrorState
        message={firstError(trial.error ?? journals.error ?? runs.error ?? files.error)}
        retry={() => {
          void trial.refetch();
          void journals.refetch();
          void runs.refetch();
          void files.refetch();
        }}
      />
    );
  }

  const debitTotal = (trial.data ?? []).reduce((sum, row) => sum + Number(row.debit), 0);
  const creditTotal = (trial.data ?? []).reduce((sum, row) => sum + Number(row.credit), 0);
  const draft = (journals.data?.data ?? []).filter((row) => row.status === "draft").length;
  const approved = (runs.data?.data ?? []).find((row) => row.status === "approved");

  return (
    <>
      <div className="kpi-grid">
        <Stat label="Ledger accounts" value={trial.data?.length ?? 0} tone="brand" />
        <Stat
          label="Trial balance debit"
          value={money(debitTotal)}
          hint={`Credit ${money(creditTotal)}`}
          tone={debitTotal === creditTotal ? "ok" : "danger"}
        />
        <Stat
          label="Journals awaiting review"
          value={journals.data?.total ?? 0}
          hint={`${draft} draft journal${draft === 1 ? "" : "s"}`}
          tone={draft ? "warn" : "neutral"}
        />
        <Stat
          label="Approved pay runs"
          value={approved ? approved.period : "None"}
          hint={approved ? "Ready for posting" : "Review the pay-run queue"}
          tone={approved ? "warn" : "neutral"}
        />
      </div>

      <div className="dashboard-grid">
        <Card title="Recent journals" aside={<Badge tone="neutral">Last 5</Badge>}>
          {journals.data?.data.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Journal</th>
                    <th>Date</th>
                    <th>Memo</th>
                    <th className="num">Debit</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {journals.data.data.map((journal) => (
                    <tr key={journal.id}>
                      <td className="mono">{journal.journal_no}</td>
                      <td>{formatDate(journal.date)}</td>
                      <td>{journal.memo || journal.source || "-"}</td>
                      <td className="num">{money(journal.total_debit)}</td>
                      <td>
                        <StatusBadge status={journal.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No journals yet"
              body={
                financeWrite
                  ? "Create a journal to begin posting operating activity."
                  : "No journals have been created in this workspace."
              }
            />
          )}
        </Card>

        <Card title="Payroll position" aside={<Badge tone="brand">Latest runs</Badge>}>
          {(runs.data?.data ?? []).length ? (
            <div className="stage-list">
              {(runs.data?.data ?? []).map((run) => (
                <div className="stage-row" key={run.id}>
                  <span className="stage-index">
                    <WalletCards size={16} aria-hidden="true" />
                  </span>
                  <span className="stage-name">
                    <strong>{run.period}</strong>
                    <small>
                      {run.payslip_count} payslip{run.payslip_count === 1 ? "" : "s"} ·{" "}
                      {run.status}
                    </small>
                  </span>
                  <span className="stage-count">{money(run.total_net)}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No pay runs" body="Start a pay run when the period is ready." />
          )}
          <p className="hint">
            {files.data?.total ?? 0} payment file{(files.data?.total ?? 0) === 1 ? "" : "s"} on
            record.
          </p>
        </Card>
      </div>
    </>
  );
}

function AccountsTab({ financeWrite }: { financeWrite: boolean }) {
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const accounts = useQuery({
    queryKey: ["finance-accounts", page],
    queryFn: () => getList<Account>("/accounts/", { page, page_size: 50 }),
  });

  return (
    <Card
      title="Chart of accounts"
      aside={
        financeWrite ? (
          <Button size="sm" variant="primary" onClick={() => setEditor(true)}>
            <Plus size={15} aria-hidden="true" /> New account
          </Button>
        ) : (
          <Badge>Read only</Badge>
        )
      }
    >
      {accounts.isLoading ? <Loading rows={5} /> : null}
      {accounts.isError ? (
        <ErrorState
          message={firstError(accounts.error)}
          retry={() => void accounts.refetch()}
        />
      ) : null}
      {accounts.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Account</th>
                  <th>Type</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {accounts.data.data.map((account) => (
                  <tr key={account.id}>
                    <td className="mono">{account.code}</td>
                    <td>{account.name}</td>
                    <td>{titleCase(account.type)}</td>
                    <td>{account.active ? <Badge tone="ok">Active</Badge> : <Badge>Inactive</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!accounts.data.data.length ? (
            <EmptyState
              title="No accounts"
              body="Create the ledger accounts used by journals and payroll."
            />
          ) : null}
          <Pagination
            page={page}
            pageSize={50}
            total={accounts.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
      {editor ? <AccountEditor onClose={() => setEditor(false)} /> : null}
    </Card>
  );
}

function JournalsTab({
  accounts,
  financeWrite,
}: {
  accounts: Account[];
  financeWrite: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const journals = useQuery({
    queryKey: ["finance-journals", page],
    queryFn: () => getList<Journal>("/journal-entries/", { page, page_size: 25 }),
  });
  const trial = useQuery({
    queryKey: ["finance-trial-balance"],
    queryFn: () => request<TrialBalanceRow[]>("/journal-entries/trial-balance/"),
  });
  const action = useMutation({
    mutationFn: ({ id, verb }: { id: number; verb: "post" | "void" }) =>
      request<Journal>(`/journal-entries/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify({ reason: "Voided from finance console" }),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["finance-journals"] });
      void queryClient.invalidateQueries({ queryKey: ["finance-trial-balance"] });
      toast.push("Journal updated.");
    },
  });

  return (
    <>
      <Card
        title="Journals"
        aside={
          financeWrite ? (
            <Button size="sm" variant="primary" onClick={() => setEditor(true)}>
              <Plus size={15} aria-hidden="true" /> New journal
            </Button>
          ) : null
        }
      >
        {journals.isLoading ? <Loading rows={5} /> : null}
        {journals.isError ? (
          <ErrorState
            message={firstError(journals.error)}
            retry={() => void journals.refetch()}
          />
        ) : null}
        {journals.data ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Journal</th>
                    <th>Date</th>
                    <th>Source</th>
                    <th>Memo</th>
                    <th className="num">Amount</th>
                    <th>Status</th>
                    {financeWrite ? <th /> : null}
                  </tr>
                </thead>
                <tbody>
                  {journals.data.data.map((journal) => (
                    <tr key={journal.id}>
                      <td className="mono">{journal.journal_no}</td>
                      <td>{formatDate(journal.date)}</td>
                      <td>{titleCase(journal.source) || "Manual"}</td>
                      <td>{journal.memo || "-"}</td>
                      <td className="num">{money(journal.total_debit)}</td>
                      <td>
                        <StatusBadge status={journal.status} />
                      </td>
                      {financeWrite ? (
                        <td>
                          <div className="row-actions">
                            {journal.status === "draft" ? (
                              <Button
                                size="sm"
                                variant="primary"
                                busy={action.isPending}
                                onClick={() => action.mutate({ id: journal.id, verb: "post" })}
                              >
                                <Check size={14} aria-hidden="true" /> Post
                              </Button>
                            ) : null}
                            {journal.status === "posted" ? (
                              <Button
                                size="sm"
                                variant="danger"
                                busy={action.isPending}
                                onClick={() => action.mutate({ id: journal.id, verb: "void" })}
                              >
                                Void
                              </Button>
                            ) : null}
                          </div>
                        </td>
                      ) : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!journals.data.data.length ? (
              <EmptyState title="No journals" body="Draft a journal to record a transaction." />
            ) : null}
            <Pagination
              page={page}
              pageSize={25}
              total={journals.data.total}
              onPage={setPage}
            />
          </>
        ) : null}
        {action.isError ? (
          <p className="form-error">{firstError(action.error)}</p>
        ) : null}
      </Card>

      <Card
        title="Trial balance"
        aside={
          <Button size="sm" onClick={() => void trial.refetch()} busy={trial.isFetching}>
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </Button>
        }
      >
        {trial.isLoading ? <Loading rows={4} /> : null}
        {trial.isError ? (
          <ErrorState message={firstError(trial.error)} retry={() => void trial.refetch()} />
        ) : null}
        {trial.data ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Account</th>
                  <th>Type</th>
                  <th className="num">Debit</th>
                  <th className="num">Credit</th>
                  <th className="num">Balance</th>
                </tr>
              </thead>
              <tbody>
                {trial.data.map((row) => (
                  <tr key={row.code}>
                    <td className="mono">{row.code}</td>
                    <td>{row.name}</td>
                    <td>{titleCase(row.type)}</td>
                    <td className="num">{money(row.debit)}</td>
                    <td className="num">{money(row.credit)}</td>
                    <td className="num">{money(row.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
      {editor ? (
        <JournalEditor accounts={accounts} onClose={() => setEditor(false)} />
      ) : null}
    </>
  );
}

function PayRunsTab({ financeWrite }: { financeWrite: boolean }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [editor, setEditor] = useState(false);
  const [page, setPage] = useState(1);
  const runs = useQuery({
    queryKey: ["finance-pay-runs", page],
    queryFn: () => getList<PayRun>("/pay-runs/", { page, page_size: 25 }),
  });
  const action = useMutation({
    mutationFn: async ({ id, verb }: { id: number; verb: string }) => {
      if (verb === "bank-file") {
        return request<PaymentFile>(`/pay-runs/${id}/bank-file/`, { method: "POST" });
      }
      return request<PayRun>(`/pay-runs/${id}/${verb}/`, {
        method: "POST",
        body: JSON.stringify({ reason: "Voided from finance console" }),
      });
    },
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["finance-pay-runs"] });
      void queryClient.invalidateQueries({ queryKey: ["finance-payment-files"] });
      void queryClient.invalidateQueries({ queryKey: ["finance-payslips"] });
      toast.push(
        variables.verb === "bank-file"
          ? "Payment file generated."
          : `Pay run ${variables.verb === "post" ? "posted" : variables.verb}.`,
      );
    },
  });

  function actionsFor(run: PayRun) {
    const list: { verb: string; label: string; icon: typeof Check; variant?: "primary" | "danger" }[] = [];
    if (run.status === "draft") list.push({ verb: "compute", label: "Compute", icon: Calculator });
    if (run.status === "draft") list.push({ verb: "approve", label: "Approve", icon: BadgeCheck, variant: "primary" });
    if (run.status === "approved") list.push({ verb: "post", label: "Post", icon: BookOpenCheck, variant: "primary" });
    if (run.status === "approved" || run.status === "posted")
      list.push({ verb: "bank-file", label: "Bank file", icon: Banknote });
    if (run.status === "posted") list.push({ verb: "pay", label: "Mark paid", icon: Send, variant: "primary" });
    if (run.status !== "paid" && run.status !== "void")
      list.push({ verb: "void", label: "Void", icon: ShieldAlert, variant: "danger" });
    return list;
  }

  return (
    <Card
      title="Pay runs"
      aside={
        financeWrite ? (
          <Button size="sm" variant="primary" onClick={() => setEditor(true)}>
            <Plus size={15} aria-hidden="true" /> New pay run
          </Button>
        ) : null
      }
    >
      {runs.isLoading ? <Loading rows={5} /> : null}
      {runs.isError ? (
        <ErrorState message={firstError(runs.error)} retry={() => void runs.refetch()} />
      ) : null}
      {runs.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Run date</th>
                  <th className="num">Gross</th>
                  <th className="num">Tax</th>
                  <th className="num">Net</th>
                  <th>Payslips</th>
                  <th>Status</th>
                  {financeWrite ? <th>Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {runs.data.data.map((run) => (
                  <tr key={run.id}>
                    <td>
                      <strong>{run.period}</strong>
                    </td>
                    <td>{formatDate(run.run_date)}</td>
                    <td className="num">{money(run.total_gross)}</td>
                    <td className="num">{money(run.total_tax)}</td>
                    <td className="num">{money(run.total_net)}</td>
                    <td>{run.payslip_count}</td>
                    <td>
                      <StatusBadge status={run.status} />
                    </td>
                    {financeWrite ? (
                      <td>
                        <div className="row-actions">
                          {actionsFor(run).map((item) => {
                            const Icon = item.icon;
                            return (
                              <Button
                                key={item.verb}
                                size="sm"
                                variant={item.variant ?? "secondary"}
                                busy={action.isPending}
                                onClick={() => action.mutate({ id: run.id, verb: item.verb })}
                              >
                                <Icon size={13} aria-hidden="true" /> {item.label}
                              </Button>
                            );
                          })}
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!runs.data.data.length ? (
            <EmptyState
              title="No pay runs"
              body="Create a pay run for the current payroll period."
            />
          ) : null}
          <Pagination
            page={page}
            pageSize={25}
            total={runs.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
      {action.isError ? <p className="form-error">{firstError(action.error)}</p> : null}
      {editor ? <PayRunEditor onClose={() => setEditor(false)} /> : null}
    </Card>
  );
}

function PayslipsTab() {
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<number | null>(null);
  const payslips = useQuery({
    queryKey: ["finance-payslips", page],
    queryFn: () => getList<Payslip>("/payslips/", { page, page_size: 25 }),
  });

  return (
    <Card
      title="Payslips"
      aside={
        <Button size="sm" onClick={() => void downloadCsv("payslips")}>
          <FileDown size={14} aria-hidden="true" /> Export
        </Button>
      }
    >
      {payslips.isLoading ? <Loading rows={5} /> : null}
      {payslips.isError ? (
        <ErrorState
          message={firstError(payslips.error)}
          retry={() => void payslips.refetch()}
        />
      ) : null}
      {payslips.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Staff no.</th>
                  <th className="num">Gross</th>
                  <th className="num">Tax</th>
                  <th className="num">Pension</th>
                  <th className="num">Deductions</th>
                  <th className="num">Net</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {payslips.data.data.map((payslip) => (
                  <>
                    <tr key={payslip.id}>
                      <td>{payslip.employee_name}</td>
                      <td className="mono">{payslip.staff_no}</td>
                      <td className="num">{money(payslip.gross)}</td>
                      <td className="num">{money(payslip.tax)}</td>
                      <td className="num">{money(payslip.pension)}</td>
                      <td className="num">{money(payslip.deductions)}</td>
                      <td className="num">{money(payslip.net)}</td>
                      <td>
                        <Button
                          size="sm"
                          onClick={() =>
                            setExpanded((current) =>
                              current === payslip.id ? null : payslip.id,
                            )
                          }
                        >
                          {expanded === payslip.id ? "Hide" : "Lines"}
                        </Button>
                      </td>
                    </tr>
                    {expanded === payslip.id ? (
                      <tr key={`${payslip.id}-lines`}>
                        <td colSpan={8}>
                          <div className="table-wrap">
                            <table className="table table-compact">
                              <thead>
                                <tr>
                                  <th>Description</th>
                                  <th>Kind</th>
                                  <th className="num">Quantity</th>
                                  <th className="num">Rate</th>
                                  <th className="num">Amount</th>
                                </tr>
                              </thead>
                              <tbody>
                                {payslip.lines.map((line) => (
                                  <tr key={line.id}>
                                    <td>{line.description}</td>
                                    <td>{titleCase(line.kind)}</td>
                                    <td className="num">{line.quantity}</td>
                                    <td className="num">{money(line.rate)}</td>
                                    <td className="num">{money(line.amount)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </>
                ))}
              </tbody>
            </table>
          </div>
          {!payslips.data.data.length ? (
            <EmptyState
              title="No payslips"
              body="Payslips appear after a pay run is computed."
            />
          ) : null}
          <Pagination
            page={page}
            pageSize={25}
            total={payslips.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
    </Card>
  );
}

function PaymentFilesTab() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const files = useQuery({
    queryKey: ["finance-payment-files", page],
    queryFn: () => getList<PaymentFile>("/payment-files/", { page, page_size: 25 }),
  });

  async function download(file: PaymentFile) {
    try {
      await downloadPaymentFile(file.id, file.filename);
    } catch (error) {
      toast.push(errorMessage(error));
    }
  }

  return (
    <Card title="Payment files">
      {files.isLoading ? <Loading rows={5} /> : null}
      {files.isError ? (
        <ErrorState message={firstError(files.error)} retry={() => void files.refetch()} />
      ) : null}
      {files.data ? (
        <>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Pay run</th>
                  <th>Status</th>
                  <th>Generated</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {files.data.data.map((file) => (
                  <tr key={file.id}>
                    <td className="mono">{file.filename}</td>
                    <td>#{file.pay_run}</td>
                    <td>
                      <StatusBadge status={file.status} />
                    </td>
                    <td>{formatDate(file.generated_at)}</td>
                    <td>
                      <Button size="sm" onClick={() => void download(file)}>
                        <Download size={14} aria-hidden="true" /> Download
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!files.data.data.length ? (
            <EmptyState
              title="No payment files"
              body="Generate a bank file from an approved pay run."
            />
          ) : null}
          <Pagination
            page={page}
            pageSize={25}
            total={files.data.total}
            onPage={setPage}
          />
        </>
      ) : null}
    </Card>
  );
}

function PolicyTab() {
  const elements = useQuery({
    queryKey: ["finance-pay-elements"],
    queryFn: () => getList<PayElement>("/pay-elements/", { page_size: 100 }),
  });
  const bands = useQuery({
    queryKey: ["finance-tax-bands"],
    queryFn: () => getList<TaxBand>("/tax-bands/", { page_size: 100 }),
  });

  return (
    <div className="dashboard-grid">
      <Card title="Pay elements" aside={<Badge tone="brand">Definitions</Badge>}>
        {elements.isLoading ? <Loading rows={4} /> : null}
        {elements.isError ? (
          <ErrorState
            message={firstError(elements.error)}
            retry={() => void elements.refetch()}
          />
        ) : null}
        {elements.data ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Element</th>
                  <th>Kind</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {elements.data.data.map((element) => (
                  <tr key={element.id}>
                    <td className="mono">{element.code}</td>
                    <td>{element.name}</td>
                    <td>{titleCase(element.kind)}</td>
                    <td>
                      <div className="row-actions">
                        {element.taxable ? <Badge>Taxable</Badge> : null}
                        {element.pensionable ? <Badge>Pensionable</Badge> : null}
                        {!element.active ? <Badge tone="warn">Inactive</Badge> : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>

      <Card title="Tax bands" aside={<Badge tone="brand">PAYE policy</Badge>}>
        {bands.isLoading ? <Loading rows={4} /> : null}
        {bands.isError ? (
          <ErrorState
            message={firstError(bands.error)}
            retry={() => void bands.refetch()}
          />
        ) : null}
        {bands.data ? (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Band</th>
                  <th className="num">Lower</th>
                  <th className="num">Upper</th>
                  <th className="num">Rate</th>
                  <th>Effective</th>
                </tr>
              </thead>
              <tbody>
                {bands.data.data.map((band) => (
                  <tr key={band.id}>
                    <td>{band.name}</td>
                    <td className="num">{money(band.lower)}</td>
                    <td className="num">{band.upper ? money(band.upper) : "No limit"}</td>
                    <td className="num">{band.rate_pct}%</td>
                    <td>{formatDate(band.effective_from)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </Card>
    </div>
  );
}

export function FinancePage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab");
  const tab: Tab = TABS.some((item) => item.id === rawTab) ? (rawTab as Tab) : "overview";
  const financeWrite = can(user, FINANCE_ROLES);
  const accounts = useQuery({
    queryKey: ["finance-accounts", "options"],
    queryFn: () => getList<Account>("/accounts/", { page_size: 100 }),
    enabled: tab === "journals",
  });
  const trialDebit = useQuery({
    queryKey: ["finance-trial-balance"],
    queryFn: () => request<TrialBalanceRow[]>("/journal-entries/trial-balance/"),
    enabled: tab === "overview",
  });

  function setTab(next: Tab) {
    const copy = new URLSearchParams(params);
    copy.set("tab", next);
    setParams(copy, { replace: true });
  }

  return (
    <>
      <PageHeader
        eyebrow="Finance"
        title="Finance & payroll"
        description="Control the ledger, run payroll, issue payslips and keep payment files auditable."
        actions={
          <Button onClick={() => void downloadCsv("trial-balance")}>
            <FileDown size={16} aria-hidden="true" /> Trial balance
          </Button>
        }
      />

      <div className="tabs" role="tablist" aria-label="Finance sections">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "tab active" : "tab"}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {!financeWrite ? (
        <div className="notice notice-info">
          <Landmark size={18} aria-hidden="true" />
          <div>
            <strong>Read-only finance access</strong>
            <p>
              Your role can inspect finance records but cannot alter journals, pay runs or
              payroll policy.
            </p>
          </div>
        </div>
      ) : null}

      {tab === "overview" ? (
        <>
          <Overview financeWrite={financeWrite} />
          {trialDebit.isError ? (
            <p className="hint">{firstError(trialDebit.error)}</p>
          ) : null}
        </>
      ) : null}
      {tab === "accounts" ? <AccountsTab financeWrite={financeWrite} /> : null}
      {tab === "journals" ? (
        <JournalsTab accounts={accounts.data?.data ?? []} financeWrite={financeWrite} />
      ) : null}
      {tab === "pay-runs" ? <PayRunsTab financeWrite={financeWrite} /> : null}
      {tab === "payslips" ? <PayslipsTab /> : null}
      {tab === "payment-files" ? <PaymentFilesTab /> : null}
      {tab === "policy" ? <PolicyTab /> : null}
    </>
  );
}
