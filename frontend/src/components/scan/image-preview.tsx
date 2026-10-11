"use client";

import * as React from "react";
import { X, Image as ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ImagePreviewProps {
  file: File;
  onClear: () => void;
}

export function ImagePreview({ file, onClear }: ImagePreviewProps) {
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);

  React.useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [file]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-background shadow-sm">
      <div className="relative aspect-square w-full sm:aspect-video bg-muted/30 flex items-center justify-center overflow-hidden">
        {previewUrl ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img 
            src={previewUrl} 
            alt="Egg scan preview" 
            className="object-contain w-full h-full"
          />
        ) : (
          <div className="animate-pulse flex flex-col items-center">
            <ImageIcon className="h-8 w-8 text-muted-foreground opacity-50 mb-2" />
            <span className="text-sm text-muted-foreground">Loading preview...</span>
          </div>
        )}
        
        <Button
          variant="destructive"
          size="icon"
          className="absolute top-2 right-2 h-8 w-8 rounded-full shadow-md z-10"
          onClick={onClear}
          aria-label="Remove image"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
      
      <div className="p-3 bg-muted/10 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
        <span className="truncate max-w-[200px] font-medium" title={file.name}>
          {file.name}
        </span>
        <span className="flex-shrink-0 ml-4">
          {formatSize(file.size)}
        </span>
      </div>
    </div>
  );
}
