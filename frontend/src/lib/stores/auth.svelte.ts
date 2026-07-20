import { apiJson, setUnauthorizedHandler } from "../api/client";
import type { CurrentUser } from "../api/types";

interface DemoLoginResponse {
  role: "demo";
}

class AuthStore {
  currentUser = $state<CurrentUser | null>(null);
  /** true while the cookie-backed session is being restored on startup */
  restoring = $state(true);

  get isAdmin(): boolean {
    return this.currentUser?.role === "admin";
  }

  get isDemo(): boolean {
    return this.currentUser?.role === "demo";
  }

  get sessionLabel(): string {
    if (this.isDemo) return "Demo";
    return this.currentUser?.displayName || "Admin";
  }

  /** Restore the cookie-backed session on app start. */
  async restore(): Promise<boolean> {
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

  async loginAsDemo(): Promise<void> {
    const data = await apiJson<DemoLoginResponse>("/api/auth/demo-login", {
      method: "POST",
    });
    this.currentUser = data;
  }

  logout(): void {
    this.currentUser = null;
  }
}

export const auth = new AuthStore();

setUnauthorizedHandler(() => auth.logout());
