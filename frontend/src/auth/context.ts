import { createContext, useContext } from "react";
import type { Session } from "../api/client";
import type { StaffUser } from "../api/types";

export interface AuthValue {
  session: Session | null;
  user: StaffUser | null;
  signIn: (identifier: string, password: string) => Promise<StaffUser>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthValue | null>(null);

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
