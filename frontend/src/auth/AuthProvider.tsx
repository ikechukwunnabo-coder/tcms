import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { login as loginRequest, logout as logoutRequest, sessionStore } from "../api/client";
import type { Session } from "../api/client";
import { AuthContext } from "./context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => sessionStore.load());

  useEffect(() => {
    const expired = () => setSession(null);
    window.addEventListener("tcms:unauthorized", expired);
    return () => window.removeEventListener("tcms:unauthorized", expired);
  }, []);

  const signIn = useCallback(async (identifier: string, password: string) => {
    const response = await loginRequest(identifier, password);
    const user = {
      ...response.user,
      role_codes: response.roles.length ? response.roles : response.user.role_codes,
    };
    const next = { token: response.token, user };
    sessionStore.save(next);
    setSession(next);
    return user;
  }, []);

  const signOut = useCallback(async () => {
    try {
      await logoutRequest();
    } catch {
      sessionStore.clear();
    }
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({ session, user: session?.user ?? null, signIn, signOut }),
    [session, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
