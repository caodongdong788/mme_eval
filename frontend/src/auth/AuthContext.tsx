import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, MeResponse } from "../api/index";

interface AuthState {
  loading: boolean;
  authRequired: boolean;
  isAdmin: boolean;
  user: MeResponse["user"];
  refresh: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>({
  loading: true,
  authRequired: false,
  isAdmin: false,
  user: null,
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authRequired, setAuthRequired] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [user, setUser] = useState<MeResponse["user"]>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await api.getMe();
      setAuthRequired(me.auth_required);
      setIsAdmin(me.is_admin);
      setUser(me.user);
    } catch {
      setUser(null);
      setIsAdmin(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ loading, authRequired, isAdmin, user, refresh }),
    [loading, authRequired, isAdmin, user, refresh]
  );
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}
