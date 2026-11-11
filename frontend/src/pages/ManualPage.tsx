import { Link, useParams } from "react-router-dom";
import { ArrowLeft, BookOpen, CheckCircle2, ShieldCheck } from "lucide-react";
import { Badge, Card, PageHeader } from "../components/ui";
import { ROLE_LABELS } from "../auth/roles";
import { manualForFile } from "../lib/manuals";

export function ManualPage() {
  const { file = "" } = useParams();
  const manual = manualForFile(file);

  if (!manual) {
    return (
      <div className="standalone-state">
        <BookOpen size={26} aria-hidden="true" />
        <h1>Manual not found</h1>
        <p>The requested role manual is not part of this console.</p>
        <Link className="btn btn-secondary btn-md" to="/profile">
          Return to your profile
        </Link>
      </div>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Role manual"
        title={manual.title}
        description={manual.summary}
        actions={
          <Link className="btn btn-secondary btn-md" to="/profile">
            <ArrowLeft size={16} aria-hidden="true" /> Back to profile
          </Link>
        }
      />

      <div className="manual-grid">
        <Card
          title="Your responsibilities"
          aside={<Badge tone="brand">{ROLE_LABELS[manual.role]}</Badge>}
        >
          <ul className="manual-list">
            {manual.duties.map((duty) => (
              <li key={duty}>
                <CheckCircle2 size={16} aria-hidden="true" />
                <span>{duty}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Controls to observe">
          <ul className="manual-list">
            {manual.controls.map((control) => (
              <li key={control}>
                <ShieldCheck size={16} aria-hidden="true" />
                <span>{control}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Escalation">
        <p>{manual.escalation}</p>
        <p className="hint manual-note">
          When in doubt, stop the workflow step and escalate. The audit trail is stronger than an
          undocumented correction.
        </p>
      </Card>
    </>
  );
}
