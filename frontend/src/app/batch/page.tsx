import { Upload } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export default function BatchPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Batch Scanning</h1>
        <p className="text-muted-foreground">Upload multiple egg images for batch analysis.</p>
      </div>

      <Card className="mb-8 border-dashed border-2 bg-muted/10">
        <CardContent className="flex flex-col items-center justify-center p-12 text-center">
          <div className="w-16 h-16 bg-background rounded-full shadow-sm flex items-center justify-center mb-4">
            <Upload className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium mb-2">Drag & drop multiple files</h3>
          <p className="text-sm text-muted-foreground max-w-md">
            Upload up to 50 images at once. Supports JPG, PNG, WebP. Batch processing is queued and processed in the background.
          </p>
          <Skeleton className="h-10 w-32 mt-6 rounded-md" />
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h3 className="font-medium text-lg">Recent Batches</h3>
        <div className="border border-border rounded-lg overflow-hidden bg-background">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-4 border-b border-border last:border-0 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded bg-muted" />
                <div>
                  <Skeleton className="h-4 w-32 mb-2" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <div className="flex flex-col items-end gap-2">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-2 w-24" />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-8 text-center text-sm text-primary p-4 bg-primary/5 rounded-lg border border-primary/10">
        <p>Batch scanning is coming in a future update.</p>
      </div>
    </div>
  );
}
