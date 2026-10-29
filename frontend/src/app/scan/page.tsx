"use client";

import { useState } from "react";
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

export default function ScanPage() {
  const router = useRouter();
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Metadata state
  const [eggType, setEggType] = useState("white");
  const [storageCond, setStorageCond] = useState("unknown");
  const [temperature, setTemperature] = useState("");
  const [humidity, setHumidity] = useState("");

  const [qualityReport, setQualityReport] = useState<{
    image_quality: string;
    quality_score: number;
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
          quality_score: scanResponse.image_quality_score || 0,
          warnings: scanResponse.image_quality_warnings || [],
          retake_recommended: true,
          recommendation: scanResponse.recommendation || 'Image quality below threshold. Please retake the photo under controlled candling illumination.',
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
                  <Badge variant={qualityReport.retake_recommended ? "destructive" : "secondary"}>
                    Score: {Math.round(qualityReport.quality_score * 100)}%
                  </Badge>
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
                        <span key={idx} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          {w.replace(/_/g, " ")}
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
              <strong>For best results:</strong> Use controlled lighting (candling preferred), center the egg in the frame, and ensure the background is dark and uniform.
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
            <div className="p-3 text-sm text-destructive-foreground bg-destructive/90 rounded-md shadow-sm">
              {error}
            </div>
          )}

          <ScanButton 
            onClick={handleScan} 
            disabled={!selectedImage} 
            loading={isScanning} 
          />
        </div>
      </div>
    </div>
  );
}
