export type FreshnessClass = 'FRESH' | 'OKAY' | 'OLD';
export type ImageQuality = 'GOOD' | 'ACCEPTABLE' | 'POOR';

export interface EggGeometry {
  area: number;
  width: number;
  height: number;
  aspect_ratio: number;
  centroid: [number, number];
  orientation_deg: number;
}

export type AnalysisStatus = 'EGG_DETECTED' | 'NO_EGG_DETECTED' | 'UNCERTAIN' | 'INVALID_IMAGE' | 'INFERENCE_ERROR';

export interface AnalysisEvidence {
  status: AnalysisStatus | string;
  model?: {
    name?: string;
    version?: string;
    task?: string;
    validated_egg_detector?: boolean;
  } | null;
  detections?: unknown[];
  limitations?: string[];
  message?: string | null;
}

export interface PredictionResponse {
  id: string;
  scan_id: string;
  freshness_class?: FreshnessClass | string | null;
  freshness_score?: number | null;
  estimated_age_min?: number | null;
  estimated_age_max?: number | null;
  predicted_haugh_unit?: number | null;
  confidence?: number | null;
  air_cell_area?: number | null;
  air_cell_ratio?: number | null;
  yolk_visibility?: string | null;
  crack_probability?: number | null;
  blood_spot_probability?: number | null;
  explanation?: Record<string, any> | string[] | null;
  heatmap_url?: string | null;
  model_version?: string | null;
  inference_time_ms?: number | null;
  status: string;
  created_at: string;
}

export interface ScanResponse {
  id: string;
  egg_id?: string | null;
  batch_id?: string | null;
  original_image_url?: string | null;
  processed_image_url?: string | null;
  image_quality?: ImageQuality | string | null;
  image_quality_score?: number | null;
  image_quality_warnings?: string[];
  retake_recommended?: boolean;
  recommendation?: string | null;
  analysis?: AnalysisEvidence | null;
  candidate_contour_geometry?: EggGeometry | null;
  egg_geometry?: EggGeometry | null;
  capture_date?: string;
  created_at?: string;
  prediction?: PredictionResponse | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface HealthResponse {
  status: string;
  database: { status: string; latency_ms?: number | null };
  redis: { status: string; latency_ms?: number | null };
  storage: { status: string; latency_ms?: number | null };
  model_service: { status: string; latency_ms?: number | null };
  version: string;
  timestamp: string;
}

export interface ModelInfoResponse {
  model_version: string;
  model_type?: string | null;
  is_ready: boolean;
  description?: string | null;
  dataset_version?: string | null;
  metrics?: Record<string, any> | null;
  trained_at?: string | null;
}

export interface CountByLabel {
  label: string;
  count: number;
}

export interface DashboardResponse {
  total_scans: number;
  usable_scans: number;
  retake_scans: number;
  model_ready: boolean;
  image_quality_distribution: CountByLabel[];
  prediction_status_distribution: CountByLabel[];
  freshness_distribution: CountByLabel[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
