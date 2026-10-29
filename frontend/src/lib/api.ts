
import type {
  ScanResponse,
  PredictionResponse,
  PaginatedResponse,
  HealthResponse,
  ModelInfoResponse,
  DashboardResponse,
  TokenResponse,
} from './types';

// Use localhost during development and the deployed Render API in production.
const API_BASE_URL =
  process.env.NODE_ENV === 'development'
    ? 'http://localhost:8000/api/v1'
    : 'https://eggvision-1.onrender.com/api/v1';

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
  if (!API_BASE_URL) {
    throw new ApiError(503, 'The EggVision API URL is not configured.');
  }

  return API_BASE_URL.replace(/\/+$/, '');
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

  try {
    response = await fetch(url, {
      ...options,
      credentials: 'include',
      headers,
    });
  } catch {
    throw new ApiError(
      0,
      `Unable to connect to EggVision API at ${url}. Check that the backend is running and that CORS allows https://egg-vision.vercel.app.`,
    );
  }

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;

    try {
      const errorData = await response.json();
      errorMessage =
        errorData.message || errorData.detail || errorMessage;
    } catch {
      // The response may not contain JSON.
    }

    throw new ApiError(response.status, errorMessage);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
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

  logout(): void {
    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem('eggvision_access_token');
    }
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
