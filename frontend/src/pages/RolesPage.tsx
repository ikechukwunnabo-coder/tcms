import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { getList } from "../api/client";
import type { Role, StaffUser } from "../api/types";
import { useAuth } from "../auth/context";
import { USER_ADMIN_ROLES, can } from "../auth/roles";
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Loading,
  PageHeader,
} from "../components/ui";
import { errorMessage } from "../lib/format";

export function RolesPage() {
  const { user } = useAuth();
  const allowed = can(user, USER_ADMIN_ROLES);

  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => getList<Role>("/roles/", { page_size: 100 }),
    enabled: allowed,
  });
  const users = useQuery({
    queryKey: ["users", "role-counts"],
    queryFn: () => getList<StaffUser>("/users/", { page_size: 500 }),
    enabled: allowed,
  });

  if (!allowed) {
    return (
      <EmptyState
        title="User roles are restricted"
        body="Only the System Admin role can review role assignments."
      />
    );
  }
  if (roles.isLoading) return <Loading rows={7} />;
  if (roles.isError || !roles.data) {
    return <ErrorState message={errorMessage(roles.error)} retry={() => void roles.refetch()} />;
  }

  const members = users.data?.data ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Access control"
        title="User Roles"
        description="Manage user roles and see how each role is currently assigned across the console."
      />
      <Card>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Role</th>
                <th>Code</th>
                <th className="num">Members</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {roles.data.data.map((role) => {
                const count = members.filter((member) =>
                  member.role_codes.includes(role.code),
                ).length;
                return (
                  <tr key={role.id}>
                    <td>
                      <Badge tone="brand">{role.name}</Badge>
                    </td>
                    <td className="mono">{role.code}</td>
                    <td className="num">{users.isLoading ? "—" : count}</td>
                    <td>
                      <Link className="btn btn-ghost btn-sm" to="/users">
                        Manage members <ArrowRight size={14} aria-hidden="true" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <p className="hint page-note">
        Roles are assigned from a staff member&apos;s account. Open Users to add or remove a
        role from a member.
      </p>
    </>
  );
}
