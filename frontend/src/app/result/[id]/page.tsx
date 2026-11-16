"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, AlertTriangle, ShieldCheck, Sparkles, Scale, ScanLine, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { api, apiAssetUrl } from "@/lib/api";
import { EggDetection, ScanResponse } from "@/lib/types";

export default function ResultPage({ params }: { params: { id: string } }) {
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"normalized" | "original">("original");
  const [isPredicting, setIsPredicting] = useState(false);
  const [predictionError, setPredictionError] = useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);
  const [artifactUrls, setArtifactUrls] = useState<{ original: string | null; processed: string | null }>({ original: null, processed: null });

  useEffect(() => {
    async function loadScan() {
      try {
        setLoading(true);
        let data = await api.getScanResult(params.id);
        // Older scans and transient first-pass failures can have no prediction.
        // Attempt inference once on page entry, then reload the persisted result.
        if (!data.prediction) {
          try {
            await api.requestPrediction(params.id, force);
            data = await api.getScanResult(params.id);
          } catch (predictionErr) {
            setPredictionError(predictionErr instanceof Error ? predictionErr.message : "Detection could not be completed.");
          }
        }
        setScan(data);
      } catch (err: any) {
        console.error(err);
        setError(err.message || "Failed to retrieve scan data.");
      } finally {
        setLoading(false);
      }
    }
    loadScan();
  }, [params.id]);

  useEffect(() => {
    if (!scan) return;
    const createdUrls: string[] = [];
    let active = true;

    const resolveArtifact = async (path: string | null | undefined) => {
      if (!path) return null;
      if (path.startsWith("/api/v1/artifacts/")) {
        const blobUrl = URL.createObjectURL(await api.getAssetBlob(path));
        createdUrls.push(blobUrl);
        return blobUrl;
      }
      return apiAssetUrl(path);
    };

    void Promise.all([resolveArtifact(scan.original_image_url), resolveArtifact(scan.processed_image_url)])
      .then(([original, processed]) => {
        if (active) setArtifactUrls({ original, processed });
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : "Unable to retrieve an image artifact.");
      });

    return () => {
      active = false;
      createdUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [scan]);

  const prediction = scan?.prediction;
  const predictionExplanation =
    prediction?.explanation && !Array.isArray(prediction.explanation)
      ? prediction.explanation
      : null;
  const detections = Array.isArray(predictionExplanation?.detections)
    ? (predictionExplanation.detections as EggDetection[])
    : [];
  const detectionCount = typeof predictionExplanation?.detection_count === "number"
    ? predictionExplanation.detection_count
    : detections.length;
  const predictionCompleted = prediction?.status === "COMPLETED";
  const detectorDiagnostics =
    predictionExplanation?.diagnostics && typeof predictionExplanation.diagnostics === "object"
      ? predictionExplanation.diagnostics as {
          confidence_threshold?: number | null;
          max_candidate_confidence?: number | null;
          candidates_above_threshold?: number | null;
        }
      : null;

  const runDetection = async (force = false) => {
    setIsPredicting(true);
    setPredictionError(null);
    try {
      await api.requestPrediction(params.id);
      const refreshed = await api.getScanResult(params.id);
      setScan(refreshed);
    } catch (err) {
      setPredictionError(err instanceof Error ? err.message : "Detection could not be completed.");
    } finally {
      setIsPredicting(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 max-w-5xl">
        <div className="flex items-center gap-4 mb-8">
          <Skeleton className="h-9 w-9 rounded-md" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-48" />
            <Skeleton className="h-4 w-32" />
          </div>
        </div>
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Skeleton className="h-80 rounded-xl" />
          <div className="md:col-span-2 space-y-4">
            <Skeleton className="h-28 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  const isQualityGood = scan?.image_quality === "GOOD" || scan?.image_quality === "ACCEPTABLE";
  const analysis = scan?.analysis;
  const candidateGeo = scan?.candidate_contour_geometry;
  const eggEstablished = analysis?.status === "EGG_DETECTED";
  const originalUrl = artifactUrls.original || apiAssetUrl(scan?.original_image_url);
  const processedUrl = artifactUrls.processed || apiAssetUrl(scan?.processed_image_url) || originalUrl;
  const currentImageUrl = viewMode === "normalized" && processedUrl ? processedUrl : originalUrl;

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl min-h-[calc(100vh-4rem)]">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4 pb-4 border-b border-border">
        <div className="flex items-center gap-4">
          <Button variant="outline" size="icon" asChild className="h-9 w-9">
            <Link href="/scan"><ArrowLeft className="h-4 w-4" /></Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Candling Capture Evidence Report</h1>
            <p className="text-xs text-muted-foreground font-mono">Scan ID: {params.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant={isQualityGood ? "default" : "destructive"}>
            Capture Quality: {scan?.image_quality || "UNKNOWN"}
          </Badge>
          <Badge variant="outline" className="text-xs">Screening metrics only</Badge>
        </div>
      </div>

      {error && (
        <div className="p-4 mb-6 rounded-lg bg-destructive/10 text-destructive text-sm border border-destructive/20">
          {error}
        </div>
      )}

      <div className="grid md:grid-cols-12 gap-8 mb-8">
        {/* Left Column: Image Viewer with Toggle */}
        <div className="md:col-span-5 space-y-4">
          <Card className="overflow-hidden border-border/80 shadow-sm">
            <CardHeader className="p-3 bg-muted/40 border-b border-border flex flex-row items-center justify-between">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {viewMode === "normalized" ? "Normalized candidate frame" : "Original capture"}
              </span>
              <div className="flex rounded-md bg-muted p-0.5 text-xs">
                <button
                  onClick={() => setViewMode("normalized")}
                  className={`px-2 py-1 rounded transition-colors ${viewMode === "normalized" ? "bg-background font-medium shadow-xs" : "text-muted-foreground"}`}
                >
                  Normalized
                </button>
                <button
                  onClick={() => setViewMode("original")}
                  className={`px-2 py-1 rounded transition-colors ${viewMode === "original" ? "bg-background font-medium shadow-xs" : "text-muted-foreground"}`}
                >
                  Original
                </button>
              </div>
            </CardHeader>
            <CardContent className="p-4 flex items-center justify-center bg-black/95 min-h-[340px]">
              {currentImageUrl ? (
                <div className="relative inline-block max-w-full">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={currentImageUrl}
                    alt="Egg inspection capture"
                    onLoad={(event) => setImageDimensions({
                      width: event.currentTarget.naturalWidth,
                      height: event.currentTarget.naturalHeight,
                    })}
                    className="block max-h-[320px] max-w-full object-contain rounded-md shadow-md"
                  />
                  {viewMode === "original" && imageDimensions && detections.length > 0 && (
                    <svg
                      aria-label="Egg detector bounding boxes"
                      className="pointer-events-none absolute inset-0 h-full w-full"
                      viewBox={`0 0 ${imageDimensions.width} ${imageDimensions.height}`}
                      preserveAspectRatio="none"
                    >
                      {detections.map((detection, index) => {
                        const [x1, y1, x2, y2] = detection.bbox;
                        const strokeWidth = Math.max(imageDimensions.width, imageDimensions.height) * 0.004;
                        return (
                          <g key={index}>
                            <rect
                              x={x1}
                              y={y1}
                              width={Math.max(0, x2 - x1)}
                              height={Math.max(0, y2 - y1)}
                              fill="none"
                              stroke="#22c55e"
                              strokeWidth={strokeWidth}
                            />
                            <text
                              x={x1}
                              y={Math.max(strokeWidth * 5, y1 - strokeWidth)}
                              fill="#22c55e"
                              stroke="#111827"
                              strokeWidth={strokeWidth * 0.8}
                              paintOrder="stroke"
                              fontSize={Math.max(20, strokeWidth * 5)}
                              fontWeight="bold"
                            >
                              {detection.label} {(detection.confidence * 100).toFixed(1)}%
                            </text>
                          </g>
                        );
                      })}
                    </svg>
                  )}
                </div>
              ) : (
                <div className="text-center text-muted-foreground text-sm">
                  Image artifact unavailable.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quality Assessment Summary */}
          <Card className="border-border/60">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-primary" /> Image Quality Assessment
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-4 space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Quality Grade</span>
                <span className="font-semibold">{scan?.image_quality || "N/A"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-border/40">
                <span className="text-muted-foreground">Screening method</span>
                <span className="font-semibold">Non-ML capture metrics</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-muted-foreground">Warnings Detected</span>
                <span className="font-semibold">
                  {scan?.image_quality_warnings && scan.image_quality_warnings.length > 0
                    ? scan.image_quality_warnings.length
                    : "None (Clean)"}
                </span>
              </div>
              {scan?.image_quality_warnings && scan.image_quality_warnings.length > 0 && (
                <div className="pt-2 border-t border-border/40">
                  <span className="text-xs font-semibold">Capture-screening warnings</span>
                  <ul className="mt-1 list-disc pl-4 space-y-1 text-muted-foreground">
                    {scan.image_quality_warnings.map((warning) => (
                      <li key={warning}>{warning.replaceAll("_", " ").toLowerCase()}</li>
                    ))}
                  </ul>
                  {scan.recommendation && <p className="mt-2 text-muted-foreground">{scan.recommendation}</p>}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Morphometry & Freshness Prediction */}
        <div className="md:col-span-7 space-y-6">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <ScanLine className="w-4 h-4 text-primary" /> ONNX Egg Detection
                </CardTitle>
                <Badge variant={predictionCompleted ? "default" : "outline"} className="text-xs font-mono">
                  {prediction?.status || "PENDING"}
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Visible shell localization using the verified YOLOv8n ONNX model. This is object detection, not freshness analysis.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {predictionCompleted ? (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    <div className="rounded-lg border p-3">
                      <span className="block text-xs text-muted-foreground">Eggs detected</span>
                      <span className="text-2xl font-bold">{detectionCount}</span>
                    </div>
                    <div className="rounded-lg border p-3">
                      <span className="block text-xs text-muted-foreground">Best detection</span>
                      <span className="text-2xl font-bold">
                        {detections.length ? `${(Math.max(...detections.map((item) => item.confidence)) * 100).toFixed(1)}%` : "—"}
                      </span>
                    </div>
                    <div className="rounded-lg border p-3">
                      <span className="block text-xs text-muted-foreground">Inference time</span>
                      <span className="text-2xl font-bold">
                        {prediction?.inference_time_ms != null ? `${prediction.inference_time_ms.toFixed(1)} ms` : "—"}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Model version: {prediction?.model_version || "Unknown"} · Bounding boxes use original-image pixel coordinates.
                  </p>
                  {detections.length > 0 ? (
                    <div className="space-y-2">
                      <p className="text-sm font-semibold">Detection details</p>
                      {detections.map((item, index) => (
                        <div key={index} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
                          <span className="font-medium">{item.label} #{index + 1}</span>
                          <span className="text-muted-foreground">{(item.confidence * 100).toFixed(1)}% confidence</span>
                          <span className="w-full text-xs text-muted-foreground">
                            Box: [{item.bbox.map((value) => Math.round(value)).join(", ")}] px
                          </span>
                        </div>
                      ))}
                      <p className="text-xs text-green-700 dark:text-green-400">
                        Bounding boxes are overlaid on the original image above.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3 rounded-md border p-3">
                      <p className="text-sm">
                        No egg box passed the current confidence threshold for this image.
                      </p>
                      {detectorDiagnostics && (
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div className="rounded bg-muted/40 p-2">
                            <span className="block text-muted-foreground">Highest raw candidate score</span>
                            <strong>
                              {detectorDiagnostics.max_candidate_confidence != null
                                ? `${(detectorDiagnostics.max_candidate_confidence * 100).toFixed(2)}%`
                                : "Unavailable"}
                            </strong>
                          </div>
                          <div className="rounded bg-muted/40 p-2">
                            <span className="block text-muted-foreground">Configured threshold</span>
                            <strong>
                              {detectorDiagnostics.confidence_threshold != null
                                ? `${(detectorDiagnostics.confidence_threshold * 100).toFixed(0)}%`
                                : "Unavailable"}
                            </strong>
                          </div>
                          <div className="col-span-2 text-muted-foreground">
                            Candidates at or above threshold: {detectorDiagnostics.candidates_above_threshold ?? "Unavailable"}
                          </div>
                        </div>
                      )}
                      <Button onClick={() => runDetection(true)} disabled={isPredicting} size="sm" variant="outline">
                        <RefreshCw className={`mr-2 h-4 w-4 ${isPredicting ? "animate-spin" : ""}`} />
                        {isPredicting ? "Re-running detector…" : "Re-run detector"}
                      </Button>
                      <p className="text-xs text-muted-foreground">
                        A repeat run uses the current model and threshold. Do not interpret a low-confidence candidate as a confirmed egg.
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    {predictionExplanation?.reason || predictionError || "Detection has not completed for this scan."}
                  </p>
                  <Button onClick={runDetection} disabled={isPredicting} size="sm">
                    <RefreshCw className={`mr-2 h-4 w-4 ${isPredicting ? "animate-spin" : ""}`} />
                    {isPredicting ? "Running detection…" : "Run detection"}
                  </Button>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                The detector only localizes visible eggs. It does not assess freshness, age, Haugh Unit, cracks, spoilage, contamination, or food safety.
              </p>
            </CardContent>
          </Card>

          {/* Evidence state */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Scale className="w-4 h-4 text-primary" /> Egg Presence Evidence
              </CardTitle>
              <CardDescription className="text-xs">
                Capture mode: {analysis?.capture_mode?.replaceAll("_", " ") || "unknown"}. Candidate contours below are separate from the ONNX detector result above.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 p-3 rounded-lg border border-border bg-muted/30 text-sm">
                <p className="font-semibold">Capture screening: {analysis?.status || "INFERENCE_ERROR"}</p>
                <p className="text-xs text-muted-foreground mt-1">{analysis?.message || "Capture-analysis evidence was unavailable."}</p>
              </div>
              {analysis?.limitations && analysis.limitations.length > 0 && (
                <ul className="mb-4 list-disc pl-5 space-y-1 text-xs text-muted-foreground">
                  {analysis.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
                </ul>
              )}
              {candidateGeo && !eggEstablished && (
                <p className="mb-3 text-xs text-muted-foreground">
                  A candidate contour was recorded for research only. Its geometry is not presented as an egg measurement.
                </p>
              )}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-center">
                  <span className="block text-xs text-muted-foreground mb-1">
                    {eggEstablished ? "Egg Area" : "Candidate Area"}
                  </span>
                  <span className="text-base font-bold text-foreground">
                    {candidateGeo?.area ? `${Math.round(candidateGeo.area).toLocaleString()} px²` : "Not established"}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-center">
                  <span className="block text-xs text-muted-foreground mb-1">
                    {eggEstablished ? "Aspect Ratio" : "Candidate Aspect Ratio"}
                  </span>
                  <span className="text-base font-bold text-foreground">
                    {candidateGeo?.aspect_ratio ? candidateGeo.aspect_ratio.toFixed(2) : "Not established"}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-center">
                  <span className="block text-xs text-muted-foreground mb-1">Orientation</span>
                  <span className="text-base font-bold text-foreground">
                    {candidateGeo?.orientation_deg !== undefined ? `${candidateGeo.orientation_deg}°` : "Not established"}
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-muted/40 border border-border/50 text-center">
                  <span className="block text-xs text-muted-foreground mb-1">Centroid</span>
                  <span className="text-base font-bold text-foreground">
                    {candidateGeo?.centroid ? `(${Math.round(candidateGeo.centroid[0])}, ${Math.round(candidateGeo.centroid[1])})` : "Not established"}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Unsupported analysis status */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary" /> Quality and Defect Assessment
                </CardTitle>
                <Badge variant="outline" className="text-xs font-mono">
                  {scan?.prediction?.status || "MODEL_NOT_READY"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-xl border border-border/60 bg-muted/20">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
                  <div className="space-y-1 text-sm">
                    <p className="font-semibold text-foreground">
                      No validated quality or defect model is available
                    </p>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      No freshness, age, Haugh Unit, crack, broken-shell, leakage, spoilage, or food-safety result is shown. These require task-specific models trained and evaluated against representative held-out ground truth.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg border border-border/40">
                  <span className="text-muted-foreground block mb-0.5">Air Cell Analysis</span>
                  <span className="font-medium text-foreground">Unavailable — method not yet validated</span>
                </div>
                <div className="p-3 rounded-lg border border-border/40">
                  <span className="text-muted-foreground block mb-0.5">Haugh Unit Regression</span>
                  <span className="font-medium text-foreground">Unavailable — ground-truth calibration pending</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Scientific Disclaimer */}
      <div className="bg-muted/40 border border-border rounded-lg p-4 text-xs text-muted-foreground flex items-center justify-between">
        <span>
          <strong>Scientific Disclaimer:</strong> The ONNX model localizes visible egg shells only. Capture-quality and contour metrics are screening evidence; no freshness, defect, microbiological contamination, or food-safety assessment is performed.
        </span>
        <Button variant="outline" size="sm" asChild className="shrink-0 ml-4">
          <Link href="/scan">Scan Another Egg</Link>
        </Button>
      </div>
    </div>
  );
}
