import {
  apiJson,
  getToken,
  postJson,
  removeToken,
  setToken,
  setUnauthorizedHandler,
} from "../api/client";
import type { CurrentUser } from "../api/types";

interface LoginResponse {
  token: string;
  email?: string;
  role: "admin" | "demo";
}

class AuthStore {
  currentUser = $state<CurrentUser | null>(null);
  /** true while the stored token is being validated on startup */
  restoring = $state(true);

  get isAdmin(): boolean {
    return this.currentUser?.role === "admin";
  }

  get isDemo(): boolean {
    return this.currentUser?.role === "demo";
  }

  get sessionLabel(): string {
    if (this.isDemo) return "Demo";
    return this.currentUser?.email || "Admin";
  }

  /** Validate a persisted token on app start. */
  async restore(): Promise<boolean> {
    if (!getToken()) {
      this.restoring = false;
      return false;
    }
    try {
      this.currentUser = await apiJson<CurrentUser>("/api/auth/me");
      return true;
    } catch {
      this.currentUser = null;
      return false;
    } finally {
      this.restoring = false;
    }
  }

  async login(email: string, password: string): Promise<void> {
    const data = await postJson<LoginResponse>(
      "/api/auth/login",
      { email, password },
      { auth: false },
    );
    setToken(data.token);
    this.currentUser = { email: data.email ?? "", role: data.role };
  }

  async loginAsDemo(): Promise<void> {
    const data = await apiJson<LoginResponse>("/api/auth/demo-login", {
      method: "POST",
      auth: false,
    });
    setToken(data.token);
    this.currentUser = { email: "", role: data.role };
  }

  logout(): void {
    removeToken();
    this.currentUser = null;
  }
}

export const auth = new AuthStore();

setUnauthorizedHandler(() => auth.logout());
