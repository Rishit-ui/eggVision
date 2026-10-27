"use client";

import * as React from "react";
import { Upload, Camera } from "lucide-react";
import { cn } from "@/lib/utils";

interface ImageUploaderProps {
  onImageSelected: (file: File) => void;
  className?: string;
}

export function ImageUploader({ onImageSelected, className }: ImageUploaderProps) {
  const [isDragging, setIsDragging] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };
  
  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };
  
  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (isValidImage(file)) {
        onImageSelected(file);
      } else {
        alert("Please upload a valid image file (JPG, PNG, WebP) under 10MB.");
      }
    }
  };
  
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      if (isValidImage(file)) {
        onImageSelected(file);
      } else {
        alert("Please upload a valid image file (JPG, PNG, WebP) under 10MB.");
      }
    }
  };
  
  const isValidImage = (file: File) => {
    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    const maxSize = 10 * 1024 * 1024; // 10MB
    return validTypes.includes(file.type) && file.size <= maxSize;
  };
  
  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center w-full h-64 md:h-80 rounded-xl border-2 border-dashed transition-colors bg-muted/20 cursor-pointer overflow-hidden group",
        isDragging ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50",
        className
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={triggerFileInput}
    >
      <input 
        type="file" 
        className="hidden" 
        ref={fileInputRef} 
        onChange={handleFileInputChange} 
        accept="image/jpeg,image/png,image/webp" 
      />
      
      <div className="flex flex-col items-center justify-center p-6 text-center space-y-4">
        <div className="p-4 bg-background rounded-full shadow-sm group-hover:scale-105 transition-transform duration-200">
          <Upload className="w-8 h-8 text-primary" />
        </div>
        
        <div>
          <p className="text-lg font-medium">
            Drag & drop an egg image or click to browse
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Supports JPG, PNG, WebP • Max 10MB
          </p>
        </div>
        
        <div className="flex items-center text-xs text-muted-foreground mt-4" onClick={(e) => e.stopPropagation()}>
          <div className="flex-1 h-px bg-border w-12" />
          <span className="mx-2">OR</span>
          <div className="flex-1 h-px bg-border w-12" />
        </div>
        
        <button 
          type="button"
          className="flex items-center gap-2 text-sm font-medium text-primary hover:text-primary/80 transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            if (fileInputRef.current) {
              fileInputRef.current.setAttribute('capture', 'environment');
              fileInputRef.current.click();
              // Remove capture attribute after so normal browse works next time
              setTimeout(() => {
                fileInputRef.current?.removeAttribute('capture');
              }, 100);
            }
          }}
        >
          <Camera className="w-4 h-4" />
          Open Camera
        </button>
      </div>
    </div>
  );
}
