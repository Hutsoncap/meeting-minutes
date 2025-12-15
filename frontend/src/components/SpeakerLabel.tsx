"use client";

import React from 'react';
import { cn } from '@/lib/utils';

interface SpeakerLabelProps {
  label: string;
  color?: string;
  onClick?: () => void;
  className?: string;
}

export function SpeakerLabel({ label, color = '#4299E1', onClick, className }: SpeakerLabelProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
        onClick && "cursor-pointer hover:opacity-80",
        className
      )}
      style={{
        backgroundColor: `${color}20`,
        color: color,
        borderColor: color,
        borderWidth: '1px'
      }}
      onClick={onClick}
    >
      {label}
    </span>
  );
}
