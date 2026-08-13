import axios from "axios";
import { loginPath } from "../auth/redirect";

const DEFAULT_TIMEOUT_MS = 30_000;
export const FEISHU_LOGIN_URL = "/api/auth/feishu/login";

export const http = axios.create({
  baseURL: "/api",
  withCredentials: true,
  timeout: DEFAULT_TIMEOUT_MS,
});

http.interceptors.request.use((config) => {
  config.headers = config.headers ?? {};
  config.headers["X-Requested-With"] = "mme-frontend";
  return config;
});

http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (
      error?.response?.status === 401 &&
      window.location.pathname !== "/login"
    ) {
      window.location.href = loginPath();
    }
    return Promise.reject(error);
  }
);
