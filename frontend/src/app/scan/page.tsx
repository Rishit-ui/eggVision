"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ThermometerSun, Droplets, Info, AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { ImageUploader } from "@/components/scan/image-uploader";
import { ImagePreview } from "@/components/scan/image-preview";
import { ScanButton } from "@/components/scan/scan-button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

const warningGuidance: Record<string, string> = {
  UNSUPPORTED_BACKGROUND: "The bright uniform background prevents reliable boundary screening. Use a contrasting matte background or the controlled chamber.",
  NO_CANDIDATE_CONTOUR: "No isolated candidate boundary was screened. Reframe one subject against a simpler background.",
  MULTIPLE_CANDIDATES: "Multiple isolated candidates were screened. Capture one subject at a time.",
  BLUR_DETECTED: "Focus or stabilize the camera before capture.",
  EXCESSIVE_CANDIDATE_GLARE: "Diffuse or reposition the light to reduce glare.",
  STRONG_CANDIDATE_SHADOWS: "Use more even illumination to reduce shadows.",
  CANDIDATE_PARTIALLY_VISIBLE_BORDER_CLIPPED: "Keep the full candidate inside the frame with a visible margin.",
  LOW_RESOLUTION: "Capture at a higher resolution with the subject larger in frame.",
};

export default function ScanPage() {
  const router = useRouter();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanElapsed, setScanElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Metadata state
  const [eggType, setEggType] = useState("white");
  const [storageCond, setStorageCond] = useState("unknown");
  const [temperature, setTemperature] = useState("");
  const [humidity, setHumidity] = useState("");

  useEffect(() => {
    let timer: NodeJS.Timeout | null = null;
    if (isScanning) {
      setScanElapsed(0);
      timer = setInterval(() => {
        setScanElapsed((prev) => prev + 1);
      }, 1000);
    } else {
      setScanElapsed(0);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isScanning]);

  const [qualityReport, setQualityReport] = useState<{
    image_quality: string;
    warnings: string[];
    retake_recommended: boolean;
    recommendation?: string | null;
    processed_image_url?: string | null;
  } | null>(null);

  const handleImageSelected = (file: File) => {
    setSelectedImage(file);
    setQualityReport(null);
    setError(null);
  };

  const handleClearImage = () => {
    setSelectedImage(null);
    setQualityReport(null);
    setError(null);
  };

  const handleScan = async () => {
    if (!selectedImage) return;
    if (!api.isAuthenticated()) {
      setError("Please sign in before submitting a protected scan.");
      return;
    }

    setIsScanning(true);
    setError(null);

    try {
      const metadata = {
        egg_type: eggType,
        storage_condition: storageCond,
        temperature: temperature ? parseFloat(temperature) : null,
        humidity: humidity ? parseFloat(humidity) : null,
      };

      // 1. Upload scan and execute Computer Vision Image Quality + Normalization Pipeline
      const scanResponse = await api.uploadScan(selectedImage, metadata);

      // Check Quality Gating
      if (scanResponse.retake_recommended || scanResponse.image_quality === 'POOR') {
        setQualityReport({
          image_quality: scanResponse.image_quality || 'POOR',
          warnings: scanResponse.image_quality_warnings || [],
          retake_recommended: true,
          recommendation: scanResponse.recommendation || 'Capture screening could not produce a usable candidate region. Adjust the background, framing, focus, or lighting and try again.',
          processed_image_url: scanResponse.processed_image_url,
        });
        setIsScanning(false);
        return; // DO NOT FORCE PREDICTION
      }

      // This research build has no validated egg detector/model. The report
      // presents the evidence state instead of forcing an egg prediction.
      // 2. Redirect to the transparent capture report.
      router.push(`/result/${scanResponse.id}`);

    } catch (err: any) {
      console.error(err);
      setError(err.message || "An error occurred during analysis. Please try again.");
      setIsScanning(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl min-h-[calc(100vh-4rem)]">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Candling Capture Review</h1>
        <p className="text-muted-foreground">Upload a controlled-chamber image for capture-quality review and research evidence recording.</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-8">
        {/* Left Column: Image Input */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardContent className="p-6">
              {!selectedImage ? (
                <ImageUploader onImageSelected={handleImageSelected} />
              ) : (
                <ImagePreview file={selectedImage} onClear={handleClearImage} />
              )}
            </CardContent>
          </Card>

          {qualityReport && (
            <Card className={qualityReport.retake_recommended ? "border-red-300 bg-red-50/50" : "border-amber-300 bg-amber-50/50"}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className={qualityReport.retake_recommended ? "w-5 h-5 text-red-600" : "w-5 h-5 text-amber-600"} />
                    <CardTitle className="text-base font-semibold">
                      {qualityReport.retake_recommended ? "Image Quality Substandard — Retake Recommended" : "Image Quality Warning"}
                    </CardTitle>
                  </div>
                  <Badge variant={qualityReport.retake_recommended ? "destructive" : "secondary"}>Capture screening</Badge>
                </div>
                <CardDescription className="text-sm">
                  {qualityReport.recommendation || "Controlled candling quality conditions must be satisfied before the capture can be retained for research."}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                {qualityReport.warnings.length > 0 && (
                  <div className="space-y-1">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Detected Quality Issues:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {qualityReport.warnings.map((w, idx) => (
                        <span key={idx} title={warningGuidance[w]} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          {warningGuidance[w] || w.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {qualityReport.retake_recommended && (
                  <div className="pt-2">
                    <Button variant="outline" size="sm" onClick={handleClearImage} className="w-full sm:w-auto text-xs flex items-center gap-1.5 bg-background">
                      <RefreshCw className="w-3.5 h-3.5" /> Clear &amp; Retake Image
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 flex items-start text-blue-800 text-sm">
            <Info className="w-5 h-5 mr-3 flex-shrink-0 mt-0.5 text-blue-500" />
            <p>
              <strong>For best results:</strong> Capture one centered subject with its full outline visible. Candling works with a dark chamber; general photographs need a matte, contrasting background. This screen only assesses capture conditions and does not identify eggs or assess freshness, defects, or food safety.
            </p>
          </div>
        </div>

        {/* Right Column: Metadata & Action */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Scan Metadata</CardTitle>
              <CardDescription>Optional details to improve accuracy</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Egg Type</label>
                <select 
                  className="w-full h-9 rounded-md border border-border bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                  value={eggType}
                  onChange={(e) => setEggType(e.target.value)}
                >
                  <option value="white">White Shell</option>
                  <option value="brown">Brown Shell</option>
                  <option value="desi">Desi / Native</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Storage Condition</label>
                <select 
                  className="w-full h-9 rounded-md border border-border bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                  value={storageCond}
                  onChange={(e) => setStorageCond(e.target.value)}
                >
                  <option value="unknown">Unknown</option>
                  <option value="refrigerated">Refrigerated</option>
                  <option value="room">Room Temperature</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    <ThermometerSun className="w-3 h-3" /> Temp (°C)
                  </label>
                  <Input 
                    type="number" 
                    placeholder="e.g. 24" 
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium flex items-center gap-1">
                    <Droplets className="w-3 h-3" /> Humidity (%)
                  </label>
                  <Input 
                    type="number" 
                    placeholder="e.g. 45" 
                    value={humidity}
                    onChange={(e) => setHumidity(e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {error && (
            <div className="p-3 text-sm text-destructive-foreground bg-destructive/90 rounded-md shadow-sm space-y-2">
              <p>{error}</p>
              <div className="flex gap-2 pt-1">
                {!api.isAuthenticated() && (
                  <Button asChild size="sm" variant="secondary">
                    <Link href="/login">Sign in</Link>
                  </Button>
                )}
                {selectedImage && (
                  <Button size="sm" variant="outline" className="bg-background text-foreground" onClick={handleScan}>
                    Retry Scan
                  </Button>
                )}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <ScanButton 
              onClick={handleScan} 
              disabled={!selectedImage} 
              loading={isScanning} 
            />
            {isScanning && scanElapsed >= 4 && (
              <p className="text-xs text-muted-foreground text-center animate-pulse">
                {scanElapsed < 15
                  ? "Uploading capture to server…"
                  : "Waking up backend service from sleep (free tier cold start)… please wait."}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
