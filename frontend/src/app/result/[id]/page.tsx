"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, AlertTriangle, ShieldCheck, Sparkles, Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { api, apiAssetUrl } from "@/lib/api";
import { ScanResponse } from "@/lib/types";

export default function ResultPage({ params }: { params: { id: string } }) {
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"normalized" | "original">("normalized");
  const [artifactUrls, setArtifactUrls] = useState<{ original: string | null; processed: string | null }>({ original: null, processed: null });

  useEffect(() => {
    async function loadScan() {
      try {
        setLoading(true);
        const data = await api.getScanResult(params.id);
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
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={currentImageUrl}
                  alt="Egg Candling Inspection"
                  className="max-h-[320px] max-w-full object-contain rounded-md shadow-md"
                />
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
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Morphometry & Freshness Prediction */}
        <div className="md:col-span-7 space-y-6">
          {/* Evidence state */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Scale className="w-4 h-4 text-primary" /> Egg Presence Evidence
              </CardTitle>
              <CardDescription className="text-xs">
                Capture mode: {analysis?.capture_mode?.replaceAll("_", " ") || "unknown"}. No trained egg detector is currently installed.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 p-3 rounded-lg border border-amber-200 bg-amber-50 text-sm">
                <p className="font-semibold">{analysis?.status || "INFERENCE_ERROR"}</p>
                <p className="text-xs text-muted-foreground mt-1">{analysis?.message || "Analysis evidence was unavailable."}</p>
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
          <strong>Scientific Disclaimer:</strong> This research build records capture quality and candidate-contour evidence only. It does not establish egg identity, visible defects, freshness, microbiological contamination, or food safety.
        </span>
        <Button variant="outline" size="sm" asChild className="shrink-0 ml-4">
          <Link href="/scan">Scan Another Egg</Link>
        </Button>
      </div>
    </div>
  );
}
