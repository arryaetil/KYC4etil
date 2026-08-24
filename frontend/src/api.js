import {batchesQuery} from "./lib/mappen.js";
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
    batches: (mapId) => request(batchesQuery(mapId)),
    mappen: (gearchiveerd) => request(
      gearchiveerd ? "/mappen?gearchiveerd=true" : "/mappen",
    ),
    maakMap: (naam) => request("/mappen", {method: "POST", json: {naam}}),
    hernoemMap: (id, naam) => request(`/mappen/${id}`, {method: "PATCH", json: {naam}}),
    archiveerMap: (id) => request(`/mappen/${id}/archiveren`, {method: "POST"}),
    herstelMap: (id) => request(`/mappen/${id}/herstellen`, {method: "POST"}),
    verwijderMap: (id, ontkoppelLijsten) => request(
      `/mappen/${id}${ontkoppelLijsten ? "?ontkoppel_lijsten=true" : ""}`,
      {method: "DELETE"},
    ),
    batch: (id) => request(`/batches/${id}`),
    companies: (batchId, label) => request(`/batches/${batchId}/companies${label ? `?label=${label}` : ""}`),
    company: (batchId, companyId) => request(`/batches/${batchId}/companies/${companyId}`),
    uploadBatch: (file, naam, jaar, mapId, {monitoringlijst = false} = {}) => {
      const body = new FormData();
      body.append("file", file);
      const params = new URLSearchParams();
      if (naam) params.set("naam", naam);
      if (jaar) params.set("jaar", jaar);
      if (mapId) params.set("map_id", mapId);
      // Zonder deze vlag was een watchlist alleen via de API aan te maken; de
      // interface gaf hem nooit mee.
      if (monitoringlijst) params.set("monitoringlijst", "true");
      return request(`/batches/upload?${params.toString()}`, {method: "POST", body});
    },
    voegBedrijfToe: (batchId, velden) => request(`/batches/${batchId}/companies`, {
      method: "POST",
      json: velden,
    }),
    runBatch: (id) => request(`/batches/${id}/run`, {method: "POST"}),
    monitoringStatus: () => request("/monitoring"),
    monitorRun: () => request("/monitoring/run", {method: "POST"}),
    startResearch: (companyId, gevraagdJaar) => request(`/research/companies/${companyId}/run`, {
      method: "POST",
      json: {gevraagd_jaar: gevraagdJaar},
    }),
    researchRun: (runId) => request(`/research/runs/${runId}`),
    researchCandidates: (companyId) => request(`/research/companies/${companyId}/candidates`),
    reviewResearchCandidate: (candidateId, body) => request(`/research/candidates/${candidateId}/review`, {
      method: "POST",
      json: body,
    }),
    addManualResearchSource: (companyId, body) => request(`/research/companies/${companyId}/manual-source`, {
      method: "POST",
      json: body,
    }),
    uploadMonitoringlijst: (file) => {
      const body = new FormData();
      body.append("file", file);
      return request("/batches/upload?monitoringlijst=true", {method: "POST", body});
    },
    cancelBatch: (id) => request(`/batches/${id}/cancel`, {method: "POST"}),
    resetVastgelopen: (id) => request(`/batches/${id}/reset-vastgelopen`, {method: "POST"}),
    deleteBatch: (id) => request(`/batches/${id}`, {method: "DELETE"}),
    download: async (path, filename) => {
      const headers = new Headers();
      if (token) headers.set("Authorization", `Bearer ${token}`);
      const response = await fetch(`${API_URL}${path}`, {headers});
      if (!response.ok) throw new ApiError(response.statusText, response.status);
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
