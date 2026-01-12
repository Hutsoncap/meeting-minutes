"use client";

import React from 'react';
import { cn } from '@/lib/utils';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <div className={cn(
      "flex w-full mb-4",
      isUser ? "justify-end" : "justify-start"
    )}>
      <div className={cn(
        "max-w-[80%] rounded-lg px-4 py-3 shadow-sm",
        isUser
          ? "bg-blue-500 text-white rounded-br-sm"
          : "bg-gray-100 text-gray-900 rounded-bl-sm"
      )}>
        <div className="whitespace-pre-wrap text-sm leading-relaxed">
          {content}
        </div>
        {timestamp && (
          <div className={cn(
            "text-xs mt-1",
            isUser ? "text-blue-100" : "text-gray-400"
          )}>
            {new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>
    </div>
  );
}
