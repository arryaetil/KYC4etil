const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export function createApi(token, onUnauthorized) {
  async function request(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (options.json !== undefined) headers.set("Content-Type", "application/json");

    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
      body: options.json !== undefined ? JSON.stringify(options.json) : options.body,
    });
    if (response.status === 401 && onUnauthorized) onUnauthorized();
    if (!response.ok) {
      let detail = response.statusText;
      try {
        detail = (await response.json()).detail || detail;
      } catch {
        // CSV/error bodies do not always contain JSON.
      }
      throw new ApiError(detail, response.status);
    }
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) return response.json();
    return response;
  }

  return {
    login: (email, password) => request("/auth/login", {
      method: "POST",
      headers: {"Content-Type": "application/x-www-form-urlencoded"},
      body: new URLSearchParams({username: email, password}),
    }),
    me: () => request("/auth/me"),
    batches: () => request("/batches"),
    batch: (id) => request(`/batches/${id}`),
    companies: (batchId, label) => request(`/batches/${batchId}/companies${label ? `?label=${label}` : ""}`),
    company: (batchId, companyId) => request(`/batches/${batchId}/companies/${companyId}`),
    uploadBatch: (file, naam, jaar) => {
      const body = new FormData();
      body.append("file", file);
      const params = new URLSearchParams();
      if (naam) params.set("naam", naam);
      if (jaar) params.set("jaar", jaar);
      return request(`/batches/upload?${params.toString()}`, {method: "POST", body});
    },
    runBatch: (id) => request(`/batches/${id}/run`, {method: "POST"}),
    approve: (candidateId) => request(`/candidates/${candidateId}/approve`, {method: "POST"}),
    correct: (candidateId, wp_waarde, reden) => request(`/candidates/${candidateId}/correct`, {
      method: "POST",
      json: {wp_waarde: Number(wp_waarde), reden},
    }),
    bellijst: (candidateId, reden) => request(`/candidates/${candidateId}/bellijst`, {
      method: "POST",
      json: {reden},
    }),
    approveAllGreen: (batchId) => request(`/batches/${batchId}/approve-all-green`, {method: "POST"}),
    download: async (path, filename) => {
      const response = await request(path);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    },
  };
}
