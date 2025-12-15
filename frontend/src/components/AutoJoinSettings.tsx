"use client";

import React, { useState, useEffect } from 'react';
import { Clock, Video, Bell, ExternalLink, AlertCircle, CheckCircle, Settings2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';

interface AutoJoinSettings {
  id: string;
  enabled: boolean;
  auto_record: boolean;
  reminder_minutes: number;
  supported_platforms: string[];
}

interface UpcomingMeeting {
  id: string;
  title: string;
  start_time: string;
  meeting_url: string | null;
  account_email: string;
}

const API_BASE = 'http://localhost:5167';

const PLATFORM_OPTIONS = [
  { id: 'zoom', name: 'Zoom', color: 'bg-blue-500' },
  { id: 'teams', name: 'Microsoft Teams', color: 'bg-purple-500' },
  { id: 'meet', name: 'Google Meet', color: 'bg-green-500' },
  { id: 'webex', name: 'Webex', color: 'bg-cyan-500' },
];

const REMINDER_OPTIONS = [
  { value: 1, label: '1 minute' },
  { value: 2, label: '2 minutes' },
  { value: 5, label: '5 minutes' },
  { value: 10, label: '10 minutes' },
  { value: 15, label: '15 minutes' },
];

export function AutoJoinSettings() {
  const [settings, setSettings] = useState<AutoJoinSettings>({
    id: '1',
    enabled: false,
    auto_record: true,
    reminder_minutes: 5,
    supported_platforms: ['zoom', 'teams', 'meet']
  });
  const [upcomingMeetings, setUpcomingMeetings] = useState<UpcomingMeeting[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasCalendarAccounts, setHasCalendarAccounts] = useState(false);

  useEffect(() => {
    fetchSettings();
    fetchUpcomingMeetings();
    checkCalendarAccounts();
  }, []);

  const checkCalendarAccounts = async () => {
    try {
      const response = await fetch(`${API_BASE}/calendar/accounts`);
      if (response.ok) {
        const accounts = await response.json();
        setHasCalendarAccounts(accounts.length > 0);
      }
    } catch (err) {
      console.error('Failed to check calendar accounts:', err);
    }
  };

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE}/auto-join/settings`);
      if (response.ok) {
        const data = await response.json();
        setSettings({
          ...data,
          supported_platforms: data.supported_platforms || ['zoom', 'teams', 'meet']
        });
      }
    } catch (err) {
      console.error('Failed to fetch auto-join settings:', err);
      setError('Failed to load settings');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchUpcomingMeetings = async () => {
    try {
      const response = await fetch(`${API_BASE}/auto-join/upcoming?minutes_ahead=60`);
      if (response.ok) {
        const data = await response.json();
        setUpcomingMeetings(data);
      }
    } catch (err) {
      console.error('Failed to fetch upcoming meetings:', err);
    }
  };

  const updateSettings = async (updates: Partial<AutoJoinSettings>) => {
    setIsSaving(true);
    setError(null);

    const newSettings = { ...settings, ...updates };
    setSettings(newSettings);

    try {
      const response = await fetch(`${API_BASE}/auto-join/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: newSettings.enabled,
          auto_record: newSettings.auto_record,
          reminder_minutes: newSettings.reminder_minutes,
          supported_platforms: newSettings.supported_platforms
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save settings');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
      // Revert on error
      setSettings(settings);
    } finally {
      setIsSaving(false);
    }
  };

  const togglePlatform = (platformId: string) => {
    const currentPlatforms = settings.supported_platforms;
    const newPlatforms = currentPlatforms.includes(platformId)
      ? currentPlatforms.filter(p => p !== platformId)
      : [...currentPlatforms, platformId];

    updateSettings({ supported_platforms: newPlatforms });
  };

  const handleJoinMeeting = async (meeting: UpcomingMeeting) => {
    if (!meeting.meeting_url) return;

    // Log the join action
    try {
      await fetch(`${API_BASE}/auto-join/trigger/${meeting.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'joined' })
      });
    } catch (err) {
      console.error('Failed to log join action:', err);
    }

    // Open the meeting URL
    window.open(meeting.meeting_url, '_blank');
  };

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    const diffMins = Math.round(diffMs / 60000);

    if (diffMins < 0) {
      return 'Started';
    } else if (diffMins === 0) {
      return 'Starting now';
    } else if (diffMins < 60) {
      return `In ${diffMins} min`;
    } else {
      return date.toLocaleString(undefined, {
        weekday: 'short',
        hour: 'numeric',
        minute: '2-digit'
      });
    }
  };

  const getTimeUntilStart = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = date.getTime() - now.getTime();
    return Math.round(diffMs / 60000);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Video className="h-5 w-5 text-blue-500" />
          <h2 className="text-lg font-semibold">Auto-Join Meetings</h2>
        </div>
        {isSaving && (
          <span className="text-sm text-gray-500">Saving...</span>
        )}
      </div>

      {/* Prerequisite check */}
      {!hasCalendarAccounts && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm flex items-start gap-2">
          <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-medium">Calendar Required</p>
            <p className="mt-1">Connect a calendar account in the Calendar tab to enable auto-join features.</p>
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Main enable toggle */}
      <div className={cn(
        "flex items-center justify-between p-4 rounded-lg border",
        settings.enabled ? "bg-blue-50 border-blue-200" : "bg-gray-50 border-gray-200"
      )}>
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-10 h-10 rounded-full flex items-center justify-center",
            settings.enabled ? "bg-blue-100" : "bg-gray-200"
          )}>
            <Bell className={cn(
              "h-5 w-5",
              settings.enabled ? "text-blue-600" : "text-gray-500"
            )} />
          </div>
          <div>
            <p className="font-medium">Enable Meeting Reminders</p>
            <p className="text-sm text-gray-500">
              Get notified before meetings with quick join
            </p>
          </div>
        </div>
        <Switch
          checked={settings.enabled}
          onCheckedChange={(checked) => updateSettings({ enabled: checked })}
          disabled={!hasCalendarAccounts}
        />
      </div>

      {/* Settings (only shown when enabled) */}
      {settings.enabled && (
        <div className="space-y-4">
          {/* Reminder timing */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Remind me before meetings</label>
            <div className="flex flex-wrap gap-2">
              {REMINDER_OPTIONS.map(option => (
                <button
                  key={option.value}
                  onClick={() => updateSettings({ reminder_minutes: option.value })}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                    settings.reminder_minutes === option.value
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {/* Auto-record toggle */}
          <div className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg">
            <div>
              <p className="font-medium text-sm">Auto-start recording</p>
              <p className="text-xs text-gray-500">Automatically start recording when joining</p>
            </div>
            <Switch
              checked={settings.auto_record}
              onCheckedChange={(checked) => updateSettings({ auto_record: checked })}
            />
          </div>

          {/* Supported platforms */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Supported Platforms</label>
            <div className="grid grid-cols-2 gap-2">
              {PLATFORM_OPTIONS.map(platform => (
                <button
                  key={platform.id}
                  onClick={() => togglePlatform(platform.id)}
                  className={cn(
                    "flex items-center gap-2 p-3 rounded-lg border transition-colors",
                    settings.supported_platforms.includes(platform.id)
                      ? "bg-white border-blue-300 ring-1 ring-blue-200"
                      : "bg-gray-50 border-gray-200 hover:border-gray-300"
                  )}
                >
                  <div className={cn(
                    "w-3 h-3 rounded-full",
                    platform.color
                  )} />
                  <span className="text-sm font-medium">{platform.name}</span>
                  {settings.supported_platforms.includes(platform.id) && (
                    <CheckCircle className="h-4 w-4 text-blue-500 ml-auto" />
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Upcoming meetings */}
      {hasCalendarAccounts && upcomingMeetings.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Upcoming Meetings (Next Hour)
          </h3>
          <div className="space-y-2">
            {upcomingMeetings.map(meeting => {
              const minsUntilStart = getTimeUntilStart(meeting.start_time);
              const isImminent = minsUntilStart <= settings.reminder_minutes;

              return (
                <div
                  key={meeting.id}
                  className={cn(
                    "p-3 rounded-lg border",
                    isImminent ? "bg-orange-50 border-orange-200" : "bg-white border-gray-200"
                  )}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <p className="font-medium text-sm">{meeting.title}</p>
                      <p className={cn(
                        "text-xs mt-1",
                        isImminent ? "text-orange-600 font-medium" : "text-gray-500"
                      )}>
                        {formatDateTime(meeting.start_time)}
                      </p>
                    </div>
                    {meeting.meeting_url && (
                      <Button
                        size="sm"
                        variant={isImminent ? "default" : "outline"}
                        onClick={() => handleJoinMeeting(meeting)}
                        className="flex items-center gap-1"
                      >
                        <ExternalLink className="h-3 w-3" />
                        Join
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state for upcoming meetings */}
      {hasCalendarAccounts && upcomingMeetings.length === 0 && settings.enabled && (
        <div className="text-center py-6 text-gray-500">
          <Clock className="h-10 w-10 mx-auto mb-2 text-gray-300" />
          <p className="text-sm">No meetings in the next hour</p>
        </div>
      )}

      {/* Help text */}
      <div className="text-xs text-gray-500 flex items-start gap-2">
        <Settings2 className="h-4 w-4 mt-0.5 flex-shrink-0" />
        <p>
          Auto-join detects meeting links in your calendar events and shows a notification
          before the meeting starts. Click "Join" to open the meeting and optionally start recording.
        </p>
      </div>
    </div>
  );
}
