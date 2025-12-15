"use client";

import React, { useState, useEffect, useRef } from 'react';
import { MessageSquare, Plus, Trash2, ChevronLeft, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { cn } from '@/lib/utils';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
}

interface Conversation {
  id: string;
  meeting_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

interface ChatPanelProps {
  meetingId: string;
  meetingTitle?: string;
  modelProvider?: string;
  modelName?: string;
}

const API_BASE = 'http://localhost:5167';

export function ChatPanel({ meetingId, meetingTitle, modelProvider = 'ollama', modelName = 'llama3.2:latest' }: ChatPanelProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showConversationList, setShowConversationList] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch conversations for this meeting
  useEffect(() => {
    fetchConversations();
  }, [meetingId]);

  // Fetch messages when active conversation changes
  useEffect(() => {
    if (activeConversation) {
      fetchMessages(activeConversation);
    } else {
      setMessages([]);
    }
  }, [activeConversation]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const fetchConversations = async () => {
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/chat/conversations`);
      if (response.ok) {
        const data = await response.json();
        setConversations(data);
      }
    } catch (err) {
      console.error('Failed to fetch conversations:', err);
    }
  };

  const fetchMessages = async (conversationId: string) => {
    try {
      const response = await fetch(`${API_BASE}/chat/conversations/${conversationId}/messages`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data);
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    }
  };

  const handleSendMessage = async (content: string) => {
    setIsLoading(true);
    setError(null);

    // Optimistically add user message
    const tempUserMessage: Message = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      created_at: new Date().toISOString()
    };

    setMessages(prev => [...prev, tempUserMessage]);

    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          conversation_id: activeConversation,
          model_provider: modelProvider,
          model_name: modelName
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to send message');
      }

      const data = await response.json();

      // Update conversation ID if new
      if (!activeConversation) {
        setActiveConversation(data.conversation_id);
        fetchConversations(); // Refresh conversation list
      }

      // Add assistant response
      const assistantMessage: Message = {
        id: data.message_id,
        role: 'assistant',
        content: data.response,
        created_at: new Date().toISOString()
      };

      setMessages(prev => [...prev.slice(0, -1), { ...tempUserMessage, id: `msg-${Date.now()}` }, assistantMessage]);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
      // Remove optimistic message on error
      setMessages(prev => prev.filter(m => m.id !== tempUserMessage.id));
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    setActiveConversation(null);
    setMessages([]);
    setShowConversationList(false);
  };

  const handleDeleteConversation = async (conversationId: string) => {
    try {
      const response = await fetch(`${API_BASE}/chat/conversations/${conversationId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setConversations(prev => prev.filter(c => c.id !== conversationId));
        if (activeConversation === conversationId) {
          setActiveConversation(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
  };

  const handleSelectConversation = (conversationId: string) => {
    setActiveConversation(conversationId);
    setShowConversationList(false);
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center gap-2">
          {!showConversationList && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowConversationList(true)}
              className="h-8 w-8"
            >
              <ChevronLeft className="h-5 w-5" />
            </Button>
          )}
          <MessageSquare className="h-5 w-5 text-blue-500" />
          <h2 className="font-semibold text-gray-900">Chat with Meeting</h2>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleNewConversation}
          className="h-8 w-8"
          title="New Conversation"
        >
          <Plus className="h-5 w-5" />
        </Button>
      </div>

      {/* Conversation List View */}
      {showConversationList && (
        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full p-8 text-center">
              <MessageSquare className="h-12 w-12 text-gray-300 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No conversations yet</h3>
              <p className="text-sm text-gray-500 mb-4">
                Start a conversation to ask questions about this meeting.
              </p>
              <Button variant="blue" onClick={handleNewConversation}>
                <Plus className="h-4 w-4 mr-2" />
                New Conversation
              </Button>
            </div>
          ) : (
            <div className="p-4 space-y-2">
              {conversations.map(conversation => (
                <div
                  key={conversation.id}
                  className={cn(
                    "flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors",
                    activeConversation === conversation.id
                      ? "bg-blue-50 border border-blue-200"
                      : "bg-white border border-gray-200 hover:bg-gray-50"
                  )}
                  onClick={() => handleSelectConversation(conversation.id)}
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{conversation.title}</p>
                    <p className="text-xs text-gray-500">
                      {new Date(conversation.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-gray-400 hover:text-red-500 flex-shrink-0"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conversation.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Chat View */}
      {!showConversationList && (
        <>
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <MessageSquare className="h-10 w-10 text-gray-300 mb-3" />
                <p className="text-gray-500 mb-1">Ask a question about this meeting</p>
                <p className="text-sm text-gray-400">I'll answer based on the transcript content.</p>
              </div>
            ) : (
              <>
                {messages.map(message => (
                  <ChatMessage
                    key={message.id}
                    role={message.role}
                    content={message.content}
                    timestamp={message.created_at}
                  />
                ))}
                <div ref={messagesEndRef} />
              </>
            )}

            {/* Error message */}
            {error && (
              <div className="mx-4 mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
                {error}
              </div>
            )}
          </div>

          {/* Input */}
          <ChatInput
            onSend={handleSendMessage}
            isLoading={isLoading}
            placeholder="Ask about this meeting..."
          />
        </>
      )}
    </div>
  );
}
