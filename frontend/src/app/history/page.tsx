"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Eye, RefreshCw, AlertCircle, ArrowLeft, ArrowRight, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { ScanResponse } from "@/lib/types";

export default function HistoryPage() {
  const [scans, setScans] = useState<ScanResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async (targetPage = page) => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getScanHistory(targetPage, 10);
      setScans(res.items || []);
      setTotal(res.total || 0);
      setPage(res.page || targetPage);
      setPages(res.pages || 1);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Unable to retrieve scan history.");
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchHistory(page);
  }, [fetchHistory, page]);

  return (
    <div className="container mx-auto px-4 py-8 max-w-6xl min-h-[calc(100vh-4rem)]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Scan History</h1>
          <p className="text-muted-foreground">View and review all controlled-capture research records.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => fetchHistory(page)} disabled={loading} className="self-start sm:self-auto flex items-center gap-2">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error && (
        <div className="p-4 mb-6 text-sm text-destructive-foreground bg-destructive/90 rounded-md shadow-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
          {!api.isAuthenticated() && (
            <Button asChild size="sm" variant="secondary">
              <Link href="/login">Sign in</Link>
            </Button>
          )}
        </div>
      )}

      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : scans.length === 0 ? (
        <Card className="text-center p-12">
          <CardContent className="space-y-4">
            <Clock className="h-12 w-12 text-muted-foreground mx-auto" />
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">No Scans Recorded Yet</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Completed egg candling captures and optical screening records will appear here for longitudinal research.
              </p>
            </div>
            <Button asChild className="mt-4">
              <Link href="/scan">Capture New Scan</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="border border-border rounded-lg overflow-hidden bg-background shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-muted/50 text-muted-foreground text-xs uppercase font-medium border-b border-border">
                  <tr>
                    <th className="px-4 py-3">Scan Date</th>
                    <th className="px-4 py-3">Quality</th>
                    <th className="px-4 py-3">Candidate Aspect Ratio</th>
                    <th className="px-4 py-3">Model Status</th>
                    <th className="px-4 py-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {scans.map((scan) => {
                    const candidate = scan.candidate_contour_geometry;
                    const captureDate = scan.created_at ? new Date(scan.created_at) : null;
                    return (
                      <tr key={scan.id} className="hover:bg-muted/30 transition-colors">
                        <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                          {captureDate ? captureDate.toISOString().replace("T", " ").slice(0, 19) : "N/A"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={scan.image_quality === "GOOD" ? "default" : scan.image_quality === "ACCEPTABLE" ? "secondary" : "destructive"}>
                            {scan.image_quality || "UNKNOWN"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {candidate?.aspect_ratio ? candidate.aspect_ratio.toFixed(2) : "N/A"}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className="text-xs">
                            {scan.prediction?.status || "model_not_ready"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button asChild variant="ghost" size="sm" className="h-8 flex items-center gap-1.5 ml-auto">
                            <Link href={`/result/${scan.id}`}>
                              <Eye className="h-4 w-4" />
                              View
                            </Link>
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Pagination controls */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {scans.length} of {total} total scans (Page {page} of {pages})
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page <= 1 || loading}
                className="flex items-center gap-1"
              >
                <ArrowLeft className="h-4 w-4" /> Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(p + 1, pages))}
                disabled={page >= pages || loading}
                className="flex items-center gap-1"
              >
                Next <ArrowRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
