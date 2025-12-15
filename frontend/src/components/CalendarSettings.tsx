"use client";

import React, { useState, useEffect } from 'react';
import { Calendar, Link2, Trash2, RefreshCw, ExternalLink, AlertCircle, CheckCircle, Key, Eye, EyeOff, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

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

interface OAuthCredentials {
  configured: boolean;
  client_id?: string;
  client_secret_masked?: string;
  redirect_uri?: string;
  created_at?: string;
}

const API_BASE = 'http://localhost:5167';

export function CalendarSettings() {
  const [accounts, setAccounts] = useState<CalendarAccount[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [oauthCredentials, setOauthCredentials] = useState<OAuthCredentials | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Credential form state
  const [showCredentialForm, setShowCredentialForm] = useState(false);
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [isSavingCredentials, setIsSavingCredentials] = useState(false);

  useEffect(() => {
    fetchOAuthCredentials();
    fetchAccounts();
    fetchEvents();
  }, []);

  const fetchOAuthCredentials = async () => {
    try {
      const response = await fetch(`${API_BASE}/calendar/oauth-credentials`);
      if (response.ok) {
        const data = await response.json();
        setOauthCredentials(data);
      }
    } catch (err) {
      console.error('Failed to fetch OAuth credentials:', err);
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

  const handleSaveCredentials = async () => {
    if (!clientId.trim() || !clientSecret.trim()) {
      toast.error('Please enter both Client ID and Client Secret');
      return;
    }

    setIsSavingCredentials(true);
    try {
      const response = await fetch(`${API_BASE}/calendar/oauth-credentials`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: clientId.trim(),
          client_secret: clientSecret.trim()
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save credentials');
      }

      toast.success('OAuth credentials saved successfully');
      setShowCredentialForm(false);
      setClientId('');
      setClientSecret('');
      await fetchOAuthCredentials();
    } catch (err) {
      toast.error('Failed to save credentials');
      console.error(err);
    } finally {
      setIsSavingCredentials(false);
    }
  };

  const handleDeleteCredentials = async () => {
    if (!confirm('Are you sure? This will disconnect all calendar accounts.')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/calendar/oauth-credentials`, {
        method: 'DELETE'
      });

      if (response.ok) {
        toast.success('OAuth credentials deleted');
        setOauthCredentials(null);
        setAccounts([]);
        setEvents([]);
      }
    } catch (err) {
      toast.error('Failed to delete credentials');
      console.error(err);
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
        toast.success('Account disconnected');
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
        toast.success('Calendar synced');
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
          <h2 className="text-lg font-semibold">Google Calendar Integration</h2>
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

      {/* OAuth Credentials Section */}
      <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Key className="h-4 w-4 text-gray-600" />
            <span className="font-medium text-sm">OAuth Credentials</span>
          </div>
          {oauthCredentials?.configured && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDeleteCredentials}
              className="text-red-500 hover:text-red-700 hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>

        {oauthCredentials?.configured ? (
          <div className="space-y-2">
            <div className={cn(
              "flex items-center gap-2 p-2 rounded-lg bg-green-50 text-green-700"
            )}>
              <CheckCircle className="h-4 w-4" />
              <span className="text-sm">OAuth credentials configured</span>
            </div>
            <div className="text-xs text-gray-500 space-y-1">
              <p><span className="font-medium">Client ID:</span> {oauthCredentials.client_id}</p>
              <p><span className="font-medium">Secret:</span> {oauthCredentials.client_secret_masked}</p>
              <p><span className="font-medium">Redirect URI:</span> {oauthCredentials.redirect_uri}</p>
            </div>
          </div>
        ) : showCredentialForm ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-600">
              Enter your Google Cloud OAuth credentials. Create them at{' '}
              <a
                href="https://console.cloud.google.com/apis/credentials"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline"
              >
                Google Cloud Console
              </a>
            </p>

            <div className="space-y-3">
              <div>
                <Label htmlFor="client-id" className="text-sm">Client ID</Label>
                <Input
                  id="client-id"
                  value={clientId}
                  onChange={(e) => setClientId(e.target.value)}
                  placeholder="xxxx.apps.googleusercontent.com"
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="client-secret" className="text-sm">Client Secret</Label>
                <div className="relative mt-1">
                  <Input
                    id="client-secret"
                    type={showSecret ? 'text' : 'password'}
                    value={clientSecret}
                    onChange={(e) => setClientSecret(e.target.value)}
                    placeholder="GOCSPX-..."
                    className="pr-10"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7"
                    onClick={() => setShowSecret(!showSecret)}
                  >
                    {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                <p className="text-xs text-amber-800">
                  <strong>Important:</strong> Make sure to add <code className="bg-amber-100 px-1 rounded">http://localhost:5167/calendar/auth/google/callback</code> as an authorized redirect URI in your Google Cloud Console.
                </p>
              </div>
            </div>

            <div className="flex gap-2">
              <Button
                onClick={handleSaveCredentials}
                disabled={isSavingCredentials}
                className="flex-1"
              >
                {isSavingCredentials ? 'Saving...' : 'Save Credentials'}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setShowCredentialForm(false);
                  setClientId('');
                  setClientSecret('');
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className={cn(
              "flex items-center gap-2 p-2 rounded-lg bg-amber-50 text-amber-700"
            )}>
              <AlertCircle className="h-4 w-4" />
              <span className="text-sm">No OAuth credentials configured</span>
            </div>
            <p className="text-xs text-gray-500">
              To use Google Calendar, you need to create OAuth credentials in your Google Cloud Console.
            </p>
            <Button
              variant="outline"
              onClick={() => setShowCredentialForm(true)}
              className="w-full"
            >
              <Settings2 className="h-4 w-4 mr-2" />
              Configure OAuth Credentials
            </Button>
          </div>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-sm">
          {error}
        </div>
      )}

      {/* Connected accounts - only show if credentials are configured */}
      {oauthCredentials?.configured && (
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

          <Button
            variant="outline"
            className="w-full"
            onClick={handleConnectGoogle}
            disabled={isLoading}
          >
            <Link2 className="h-4 w-4 mr-2" />
            Connect Google Calendar
          </Button>
        </div>
      )}

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
