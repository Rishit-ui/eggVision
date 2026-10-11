import { ScanResponse, PredictionResponse, PaginatedResponse, HealthResponse, ModelInfoResponse } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export function apiAssetUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE_URL.replace(/\/api\/v1\/?$/, '')}${path}`;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchWithHandler(endpoint: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorMsg = 'An error occurred';
    try {
      const errorData = await response.json();
      errorMsg = errorData.message || errorData.detail || errorMsg;
    } catch (e) {
      // Ignore json parse error
    }
    throw new ApiError(response.status, errorMsg);
  }

  return response.json();
}

export const api = {
  async uploadScan(image: File, metadata?: object): Promise<ScanResponse> {
    const formData = new FormData();
    formData.append('image', image);
    formData.append('metadata', JSON.stringify(metadata || {}));

    return fetchWithHandler('/scan', {
      method: 'POST',
      body: formData,
    });
  },

  async requestPrediction(scanId: string): Promise<PredictionResponse> {
    return fetchWithHandler('/predict', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ scan_id: scanId }),
    });
  },

  async getScanResult(scanId: string): Promise<ScanResponse> {
    return fetchWithHandler(`/result/${scanId}`);
  },

  async getScanHistory(page = 1, perPage = 10): Promise<PaginatedResponse<ScanResponse>> {
    return fetchWithHandler(`/history?page=${page}&per_page=${perPage}`);
  },

  async getHealth(): Promise<HealthResponse> {
    return fetchWithHandler('/health');
  },

  async getModelInfo(): Promise<ModelInfoResponse> {
    return fetchWithHandler('/model/info');
  },
};
