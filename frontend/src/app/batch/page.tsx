import { Upload } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export default function BatchPage() {
  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">Batch Scanning</h1>
        <p className="text-muted-foreground">Batch capture is not available in this research build.</p>
      </div>

      <Card className="mb-8 border-dashed border-2 bg-muted/10">
        <CardContent className="flex flex-col items-center justify-center p-12 text-center">
          <div className="w-16 h-16 bg-background rounded-full shadow-sm flex items-center justify-center mb-4">
            <Upload className="w-8 h-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium mb-2">Batch capture is unavailable</h3>
          <p className="text-sm text-muted-foreground max-w-md">
            The current API supports one protected capture at a time. It does not provide a background batch queue.
          </p>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h3 className="font-medium text-lg">Batch history</h3>
        <div className="border border-border rounded-lg overflow-hidden bg-background">
          <p className="p-6 text-sm text-muted-foreground">No batch-processing records are available because batch processing has not been implemented.</p>
        </div>
      </div>

      <div className="mt-8 text-center text-sm text-primary p-4 bg-primary/5 rounded-lg border border-primary/10">
        <p>Use the single-capture workflow to record one image at a time.</p>
      </div>
    </div>
  );
}
