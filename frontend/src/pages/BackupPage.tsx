import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Archive,
  CheckCircle2,
  Database,
  FolderOpen,
  HardDrive,
  RotateCcw,
  Upload,
} from "lucide-react";
import { request } from "../api/client";
import type { BackupResult, BackupTestResult } from "../api/types";
import { Badge, Button, Card, PageHeader } from "../components/ui";
import { useToast } from "../components/toastContext";
import { errorMessage, formatDateTime } from "../lib/format";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = "B";
  for (const next of units) {
    value /= 1024;
    unit = next;
    if (value < 1024) break;
  }
  return `${value.toFixed(1)} ${unit}`;
}

export function BackupPage() {
  const toast = useToast();
  const [lastBackup, setLastBackup] = useState<BackupResult | null>(null);
  const [lastTest, setLastTest] = useState<BackupTestResult | null>(null);

  const createBackup = useMutation({
    mutationFn: () => request<BackupResult>("/backup/backup", { method: "POST" }),
    onSuccess: (result) => {
      setLastBackup(result);
      toast.push(`Backup created: ${result.file_name}`);
    },
    onError: (error) => toast.push(errorMessage(error), "error"),
  });

  const testStorage = useMutation({
    mutationFn: () => request<BackupTestResult>("/backup/test", { method: "POST" }),
    onSuccess: (result) => {
      setLastTest(result);
      toast.push(result.message);
    },
    onError: (error) => toast.push(errorMessage(error), "error"),
  });

  return (
    <>
      <PageHeader
        eyebrow="Administration"
        title="Backup processes"
        description="Create a server-side snapshot of the TCMS database and verify that backup storage is writable before it is needed."
      />
      <div className="backup-grid">
        <Card
          title="Backup data"
          aside={<Badge tone="ok">Available</Badge>}
        >
          <p className="hint">
            Creates a timestamped, gzipped JSON snapshot of the database on the application
            server. Files are kept outside the public media directory.
          </p>
          <div className="backup-actions">
            <Button
              variant="primary"
              busy={createBackup.isPending}
              onClick={() => createBackup.mutate()}
            >
              <Database size={16} aria-hidden="true" /> Backup data
            </Button>
            <Button
              busy={testStorage.isPending}
              onClick={() => testStorage.mutate()}
            >
              <HardDrive size={16} aria-hidden="true" /> Test files
            </Button>
            <Button disabled title="Not enabled in this build">
              <Archive size={16} aria-hidden="true" /> Zip files
            </Button>
            <Button disabled title="Not enabled in this build">
              <Upload size={16} aria-hidden="true" /> Push files
            </Button>
          </div>

          {lastBackup ? (
            <div className="backup-result">
              <CheckCircle2 size={18} aria-hidden="true" />
              <div>
                <strong>{lastBackup.file_name}</strong>
                <small>
                  {formatBytes(lastBackup.bytes)} · {formatDateTime(lastBackup.created_at)}
                </small>
              </div>
            </div>
          ) : null}

          {lastTest ? (
            <div className="backup-result">
              <HardDrive size={18} aria-hidden="true" />
              <div>
                <strong>{lastTest.message}</strong>
                <small>
                  {formatBytes(lastTest.free_bytes)} free · {formatDateTime(lastTest.checked_at)}
                </small>
              </div>
            </div>
          ) : null}
        </Card>

        <Card
          title="Restore data"
          aside={<Badge tone="warn">Disabled</Badge>}
        >
          <p className="hint">
            Restore operations are intentionally unavailable in the staff console. A restore
            should be run as a controlled maintenance task with a verified snapshot and a
            database administrator present.
          </p>
          <div className="backup-actions">
            <Button disabled>
              <FolderOpen size={16} aria-hidden="true" /> Unzip files
            </Button>
            <Button disabled>
              <RotateCcw size={16} aria-hidden="true" /> Restore data
            </Button>
          </div>
          <div className="detail-section">
            <h3>Operational notes</h3>
            <ul className="plain-list">
              <li>
                <span>
                  <strong>Retention</strong>
                  <small>Copy snapshots to protected storage and remove old files on schedule.</small>
                </span>
              </li>
              <li>
                <span>
                  <strong>Access</strong>
                  <small>Only system administrators can create snapshots or test backup storage.</small>
                </span>
              </li>
              <li>
                <span>
                  <strong>Verification</strong>
                  <small>Run “Test files” after changing the backup directory or host.</small>
                </span>
              </li>
            </ul>
          </div>
        </Card>
      </div>
    </>
  );
}
