import { http } from "./client";
import type { MeResponse } from "./types";

export const authApi = {
  getMe: () => http.get<MeResponse>("/auth/me").then((r) => r.data),
  logout: () => http.post("/auth/logout").then((r) => r.data),
};
