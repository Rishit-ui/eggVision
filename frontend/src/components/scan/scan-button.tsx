"use client";

import { ScanSearch, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ScanButtonProps {
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

export function ScanButton({ onClick, disabled = false, loading = false, className }: ScanButtonProps) {
  return (
    <Button
      onClick={onClick}
      disabled={disabled || loading}
      size="lg"
      className={`w-full h-14 text-lg font-medium shadow-md transition-all ${className}`}
    >
      {loading ? (
        <>
          <Loader2 className="mr-2 h-6 w-6 animate-spin" />
          Analyzing Egg...
        </>
      ) : (
        <>
          <ScanSearch className="mr-2 h-6 w-6" />
          Analyze Egg
        </>
      )}
    </Button>
  );
}
