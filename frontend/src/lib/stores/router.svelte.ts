export type Route =
  | { name: "home"; params: Record<string, never> }
  | { name: "list"; params: { slug: string } }
  | { name: "stock"; params: { symbol: string } }
  | { name: "notFound"; params: Record<string, never> };

function decodePart(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function parsePath(pathname: string): Route {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) {
    return { name: "home", params: {} };
  }
  if (parts[0] === "list" && parts.length === 2) {
    return { name: "list", params: { slug: decodePart(parts[1]) } };
  }
  if (parts[0] === "stock" && parts.length === 2) {
    return { name: "stock", params: { symbol: decodePart(parts[1]).toUpperCase() } };
  }
  return { name: "notFound", params: {} };
}

class RouterStore {
  route = $state<Route>(parsePath(typeof window === "undefined" ? "/" : window.location.pathname));

  constructor() {
    if (typeof window === "undefined") return;
    window.addEventListener("popstate", () => {
      this.route = parsePath(window.location.pathname);
    });
  }

  navigate(path: string): void {
    if (typeof window === "undefined") return;
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    this.route = parsePath(window.location.pathname);
  }
}

export const router = new RouterStore();
