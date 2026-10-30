
import type {
  ScanResponse,
  PredictionResponse,
  PaginatedResponse,
  HealthResponse,
  ModelInfoResponse,
  DashboardResponse,
  TokenResponse,
} from './types';

export const LOCAL_API_BASE_URL = 'http://localhost:8000/api/v1';
export const PRODUCTION_API_BASE_URL = 'https://eggvision-1.onrender.com/api/v1';

function normalizeApiBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!trimmed) throw new Error('The EggVision API URL is empty.');

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error('The EggVision API URL must be an absolute http(s) URL.');
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('The EggVision API URL must use http or https.');
  }
  const path = parsed.pathname.replace(/\/+$/, '');
  if (path && path !== '/api/v1') {
    throw new Error('The EggVision API URL must end with /api/v1.');
  }
  parsed.pathname = '/api/v1';
  return parsed.toString().replace(/\/$/, '');
}

/** The sole API-url resolver. A public override is optional, never required. */
export function resolveApiBaseUrl(environment = process.env.NODE_ENV, configuredUrl = process.env.NEXT_PUBLIC_API_URL): string {
  const fallback = environment === 'development' ? LOCAL_API_BASE_URL : PRODUCTION_API_BASE_URL;
  return normalizeApiBaseUrl(configuredUrl || fallback);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function requireApiBaseUrl(): string {
  try {
    return resolveApiBaseUrl();
  } catch (error) {
    const message = error instanceof Error ? error.message : 'The EggVision API URL is not configured.';
    throw new ApiError(503, message);
  }
}

export function apiAssetUrl(
  path: string | null | undefined,
): string | null {
  if (!path) return null;

  if (/^https?:\/\//i.test(path)) {
    return path;
  }

  const baseUrl = requireApiBaseUrl();
  const origin = baseUrl.replace(/\/api\/v1\/?$/, '');
  const assetPath = path.startsWith('/') ? path : `/${path}`;

  return `${origin}${assetPath}`;
}

function statusMessage(status: number): string {
  return {
    400: 'The request is invalid. Please check your image format and metadata.',
    401: 'Your session has expired or authentication is required. Please sign in to continue.',
    403: 'Permission denied. Your account does not have access to this resource.',
    404: 'The requested EggVision resource was not found.',
    408: 'The EggVision API request timed out. The server may be waking up or processing took too long.',
    413: 'The selected image is too large. Maximum allowed size is 10 MB.',
    422: 'The submitted data is invalid. Please review metadata and try again.',
    429: 'Too many requests. Please wait and try again.',
    500: 'The EggVision backend encountered an unexpected error. Please try again later.',
    502: 'EggVision could not complete image processing or storage. Please try again.',
    503: 'EggVision storage or scan persistence is temporarily unavailable. The server may be starting up.',
    504: 'EggVision processing timed out. The backend may be waking up or under load. Please retry with a smaller image.',
  }[status] || (status >= 500
    ? 'The EggVision API encountered an error. Please try again later.'
    : `Request failed with status ${status}`);
}

async function fetchWithHandler(
  endpoint: string,
  options?: RequestInit,
): Promise<any> {
  const token =
    typeof window === 'undefined'
      ? null
      : window.sessionStorage.getItem('eggvision_access_token');

  const headers = new Headers(options?.headers);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const url = `${requireApiBaseUrl()}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  let response: Response;
  const controller = new AbortController();
  const timeoutMs = endpoint.includes('/scan') ? 60_000 : 30_000;
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    response = await fetch(url, {
      ...options,
      credentials: 'include',
      headers,
      signal: options?.signal || controller.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(408, 'The EggVision API request timed out. The server may be waking up from sleep.');
    }
    throw new ApiError(
      0,
      'Unable to reach the EggVision API. Check your internet connection, verify that the backend is awake, or check browser access policy.',
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    let errorMessage = statusMessage(response.status);

    try {
      const errorData = await response.json();
      errorMessage =
        errorData.message || errorData.detail || errorMessage;
    } catch {
      // The response may not contain JSON.
    }

    // Immediately purge expired/invalid tokens from browser storage on 401
    if (response.status === 401 && typeof window !== 'undefined') {
      window.sessionStorage.removeItem('eggvision_access_token');
    }

    throw new ApiError(response.status, errorMessage);
  }

  if (response.status === 204) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    throw new ApiError(502, 'The EggVision API returned an invalid response.');
  }
}

export const api = {
  async login(
    email: string,
    password: string,
  ): Promise<TokenResponse> {
    const result = await fetchWithHandler('/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    if (
      typeof window !== 'undefined' &&
      result?.access_token
    ) {
      window.sessionStorage.setItem(
        'eggvision_access_token',
        result.access_token,
      );
    }

    return result;
  },

  async logout(): Promise<void> {
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem('eggvision_access_token');
    }
    try {
      await fetchWithHandler('/auth/logout', { method: 'POST' });
    } catch {
      // Local storage has already been cleared. The next server response will
      // still reject an expired or retained cookie if it could not be cleared.
    }
  },

  isAuthenticated(): boolean {
    return typeof window !== 'undefined' && Boolean(window.sessionStorage.getItem('eggvision_access_token'));
  },

  /** Fetch a protected artifact as a browser blob so bearer auth is preserved. */
  async getAssetBlob(path: string): Promise<Blob> {
    const url = apiAssetUrl(path);
    if (!url) throw new ApiError(404, 'The image artifact is unavailable.');
    const token = typeof window === 'undefined' ? null : window.sessionStorage.getItem('eggvision_access_token');
    const headers = new Headers();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    let response: Response;
    try {
      response = await fetch(url, { credentials: 'include', headers });
    } catch {
      throw new ApiError(0, 'Unable to retrieve the image artifact.');
    }
    if (!response.ok) throw new ApiError(response.status, statusMessage(response.status));
    return response.blob();
  },

  async uploadScan(
    image: File,
    metadata?: object,
  ): Promise<ScanResponse> {
    const formData = new FormData();

    formData.append('image', image);
    formData.append('metadata', JSON.stringify(metadata || {}));

    // Do not set Content-Type manually for FormData.
    // The browser must supply the multipart boundary.
    return fetchWithHandler('/scan', {
      method: 'POST',
      body: formData,
    });
  },

  async requestPrediction(
    scanId: string,
  ): Promise<PredictionResponse> {
    return fetchWithHandler('/predict', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ scan_id: scanId }),
    });
  },

  async getScanResult(
    scanId: string,
  ): Promise<ScanResponse> {
    return fetchWithHandler(`/result/${encodeURIComponent(scanId)}`);
  },

  async getScanHistory(
    page = 1,
    perPage = 10,
  ): Promise<PaginatedResponse<ScanResponse>> {
    const query = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
    });

    return fetchWithHandler(`/history?${query.toString()}`);
  },

  async getHealth(): Promise<HealthResponse> {
    return fetchWithHandler('/health');
  },

  async getModelInfo(): Promise<ModelInfoResponse> {
    return fetchWithHandler('/model/info');
  },

  async getDashboard(): Promise<DashboardResponse> {
    return fetchWithHandler('/dashboard');
  },
};
