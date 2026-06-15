import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, MeResponse } from "../api";

interface AuthState {
  loading: boolean;
  authRequired: boolean;
  user: MeResponse["user"];
  refresh: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>({
  loading: true,
  authRequired: false,
  user: null,
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authRequired, setAuthRequired] = useState(false);
  const [user, setUser] = useState<MeResponse["user"]>(null);

  const refresh = useCallback(async () => {
    try {
      const me = await api.getMe();
      setAuthRequired(me.auth_required);
      setUser(me.user);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ loading, authRequired, user, refresh }),
    [loading, authRequired, user, refresh]
  );
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}
