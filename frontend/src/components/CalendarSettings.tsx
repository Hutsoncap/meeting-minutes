"use client";

import React, { useState, useEffect } from 'react';
import { Calendar, Link2, Trash2, RefreshCw, ExternalLink, AlertCircle, CheckCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface CalendarAccount {
  id: string;
  provider: string;
  email: string;
  token_expires_at: string;
  created_at: string;
}

interface CalendarEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  meeting_url: string | null;
  account_email: string;
}

const API_BASE = 'http://localhost:5167';

export function CalendarSettings() {
  const [accounts, setAccounts] = useState<CalendarAccount[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isConfigured, setIsConfigured] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkStatus();
    fetchAccounts();
    fetchEvents();
  }, []);

  const checkStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/calendar/status`);
      if (response.ok) {
        const data = await response.json();
        setIsConfigured(data.available);
      }
    } catch (err) {
      console.error('Failed to check calendar status:', err);
    }
  };

  const fetchAccounts = async () => {
    try {
      const response = await fetch(`${API_BASE}/calendar/accounts`);
      if (response.ok) {
        const data = await response.json();
        setAccounts(data);
      }
    } catch (err) {
      console.error('Failed to fetch accounts:', err);
    }
  };

  const fetchEvents = async () => {
    try {
      const response = await fetch(`${API_BASE}/calendar/events?limit=5`);
      if (response.ok) {
        const data = await response.json();
        setEvents(data);
      }
    } catch (err) {
      console.error('Failed to fetch events:', err);
    }
  };

  const handleConnectGoogle = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/calendar/auth/google`);
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to initiate Google auth');
      }

      const data = await response.json();
      // Open OAuth URL in new window
      window.open(data.auth_url, '_blank', 'width=600,height=700');

      // Note: User will need to refresh after completing OAuth
      setError('Complete authentication in the popup window, then refresh this page.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect to Google');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDisconnect = async (accountId: string) => {
    try {
      const response = await fetch(`${API_BASE}/calendar/accounts/${accountId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setAccounts(prev => prev.filter(a => a.id !== accountId));
        fetchEvents();
      }
    } catch (err) {
      console.error('Failed to disconnect account:', err);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const response = await fetch(`${API_BASE}/calendar/sync`, { method: 'POST' });
      if (response.ok) {
        fetchEvents();
      }
    } catch (err) {
      console.error('Failed to sync calendar:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="h-5 w-5 text-blue-500" />
          <h2 className="text-lg font-semibold">Calendar Integration</h2>
        </div>
        {accounts.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleSync}
            disabled={isSyncing}
          >
            <RefreshCw className={cn("h-4 w-4 mr-2", isSyncing && "animate-spin")} />
            Sync
          </Button>
        )}
      </div>

      {/* Status indicator */}
      <div className={cn(
        "flex items-center gap-2 p-3 rounded-lg",
        isConfigured ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"
      )}>
        {isConfigured ? (
          <>
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm">Google Calendar integration is available</span>
          </>
        ) : (
          <>
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">
              Google Calendar requires configuration. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.
            </span>
          </>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-sm">
          {error}
        </div>
      )}

      {/* Connected accounts */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-700">Connected Accounts</h3>
        {accounts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Calendar className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p className="text-sm">No calendar accounts connected</p>
          </div>
        ) : (
          <div className="space-y-2">
            {accounts.map(account => (
              <div
                key={account.id}
                className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                    <span className="text-red-600 font-medium text-sm">G</span>
                  </div>
                  <div>
                    <p className="font-medium text-sm">{account.email}</p>
                    <p className="text-xs text-gray-500">
                      Connected {new Date(account.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-gray-400 hover:text-red-500"
                  onClick={() => handleDisconnect(account.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}

        {isConfigured && (
          <Button
            variant="outline"
            className="w-full"
            onClick={handleConnectGoogle}
            disabled={isLoading}
          >
            <Link2 className="h-4 w-4 mr-2" />
            Connect Google Calendar
          </Button>
        )}
      </div>

      {/* Upcoming events */}
      {events.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700">Upcoming Events</h3>
          <div className="space-y-2">
            {events.map(event => (
              <div
                key={event.id}
                className="p-3 bg-white border border-gray-200 rounded-lg"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-medium text-sm">{event.title}</p>
                    <p className="text-xs text-gray-500">{formatDateTime(event.start_time)}</p>
                  </div>
                  {event.meeting_url && (
                    <a
                      href={event.meeting_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-500 hover:text-blue-600"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
