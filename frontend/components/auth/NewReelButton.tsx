"use client";

import { useAuth } from "@/lib/AuthContext";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import React from "react";

interface NewReelButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "link" | "destructive" | "secondary";
  size?: "default" | "sm" | "lg" | "icon";
  isHeader?: boolean;
}

export function NewReelButton({ 
  children, 
  className, 
  variant, 
  size, 
  isHeader,
  ...props 
}: NewReelButtonProps) {
  const { requireAuth } = useAuth();
  const router = useRouter();

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    requireAuth(() => {
      router.push("/projects/new");
    });
  };

  if (isHeader) {
    return (
      <button
        onClick={handleClick}
        className={cn(
          "ml-2 px-4 py-2 rounded-lg text-sm font-medium text-white bg-gradient-brand shadow-brand-soft hover:shadow-brand transition-shadow",
          className
        )}
        {...props}
      >
        {children || "New Reel"}
      </button>
    );
  }

  return (
    <Button 
      variant={variant} 
      size={size} 
      onClick={handleClick}
      className={className}
      {...props}
    >
      {children || "New Reel"}
    </Button>
  );
}
