export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface Project {
  id: string;
  org_id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface APIKey {
  id: string;
  project_id: string;
  name: string;
  key_prefix: string;
  created_at: string;
  last_used_at?: string;
  revoked_at?: string;
  raw_key?: string;
}

export interface Trace {
  id: string;
  project_id: string;
  name: string;
  status: "running" | "success" | "error";
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  span_count: number;
  error_count: number;
  total_tokens?: number;
  total_cost_usd?: number;
  model?: string;
  created_at: string;
  input_tokens?: number;
  output_tokens?: number;
  updated_at?: string;
}

export interface Span {
  id: string;
  trace_id: string;
  parent_span_id?: string;
  name: string;
  span_type: string;
  status: "running" | "success" | "error";
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  model?: string;
  provider?: string;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  tool_name?: string;
  tool_call_id?: string;
  input?: any;
  output?: any;
  metadata?: any;
  tags?: string[];
  error_type?: string;
  error_message?: string;
  error_stack?: string;
}

export interface SpanNode extends Span {
  children: SpanNode[];
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || (typeof window !== "undefined" ? window.location.origin.replace(":3000", ":8000") : "http://localhost:8000");

async function request(path: string, token?: string, options: RequestInit = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };
  
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = `API request failed: ${response.statusText}`;
    try {
      const data = await response.json();
      if (data.error && typeof data.error.message === "string") {
        errorMsg = data.error.message;
      } else if (Array.isArray(data.detail)) {
        errorMsg = data.detail.map((err: any) => `${err.loc.join(".")}: ${err.msg}`).join(", ");
      } else if (typeof data.detail === "string") {
        errorMsg = data.detail;
      }
    } catch (e) {}
    throw new Error(errorMsg);
  }

  if (response.status === 204) {
    return;
  }

  return response.json();
}

export const api = {
  // Organizations
  async listOrgs(token: string): Promise<Organization[]> {
    return request("/v1/orgs", token);
  },

  async getOrg(orgId: string, token: string): Promise<Organization> {
    return request(`/v1/orgs/${orgId}`, token);
  },

  async createOrg(name: string, slug: string, token: string): Promise<Organization> {
    return request("/v1/orgs", token, {
      method: "POST",
      body: JSON.stringify({ name, slug }),
    });
  },

  async deleteOrg(orgId: string, token: string): Promise<void> {
    return request(`/v1/orgs/${orgId}`, token, {
      method: "DELETE",
    });
  },

  // Projects
  async listProjects(orgId: string, token: string): Promise<Project[]> {
    return request(`/v1/projects?org_id=${orgId}`, token);
  },

  async getProject(projectId: string, token: string): Promise<Project> {
    return request(`/v1/projects/${projectId}`, token);
  },

  async createProject(orgId: string, name: string, slug: string, token: string): Promise<Project> {
    return request("/v1/projects", token, {
      method: "POST",
      body: JSON.stringify({ org_id: orgId, name, slug }),
    });
  },

  async deleteProject(projectId: string, token: string): Promise<void> {
    return request(`/v1/projects/${projectId}`, token, {
      method: "DELETE",
    });
  },

  // API Keys
  async listAPIKeys(projectId: string, token: string): Promise<APIKey[]> {
    return request(`/v1/api-keys?project_id=${projectId}`, token);
  },

  async createAPIKey(projectId: string, name: string, token: string): Promise<APIKey> {
    return request("/v1/api-keys", token, {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, name }),
    });
  },

  async revokeAPIKey(keyId: string, token: string): Promise<void> {
    return request(`/v1/api-keys/${keyId}`, token, {
      method: "DELETE",
    });
  },

  // Traces & Spans
  async listTraces(
    projectId: string,
    token: string,
    filters: { status?: string; model?: string; startDate?: string | null; limit?: number } = {}
  ): Promise<{ data: Trace[]; meta: { total: number; limit: number }; next_cursor: string | null }> {
    const params = new URLSearchParams();
    params.append("project_id", projectId);
    
    if (filters.limit) {
      params.append("limit", String(filters.limit));
    }
    if (filters.status && filters.status !== "all") {
      params.append("status", filters.status);
    }
    if (filters.model && filters.model !== "all") {
      params.append("model", filters.model);
    }
    if (filters.startDate) {
      params.append("start_date", filters.startDate);
    }

    return request(`/v1/traces?${params.toString()}`, token);
  },

  async getTrace(traceId: string, token: string): Promise<Trace> {
    return request(`/v1/traces/${traceId}`, token);
  },

  async getTraceSpans(traceId: string, token: string): Promise<{ data: SpanNode[]; meta: { total: number } }> {
    return request(`/v1/traces/${traceId}/spans`, token);
  },
};
