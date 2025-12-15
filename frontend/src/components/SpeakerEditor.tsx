"use client";

import React, { useState, useEffect } from 'react';
import { Users, Edit2, Trash2, Save, X, RefreshCw, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { SpeakerLabel } from './SpeakerLabel';
import { cn } from '@/lib/utils';

interface Speaker {
  id: string;
  meeting_id: string;
  label: string;
  color: string;
  created_at: string;
}

interface SpeakerEditorProps {
  meetingId: string;
  onSpeakersChange?: (speakers: Speaker[]) => void;
}

const API_BASE = 'http://localhost:5167';

export function SpeakerEditor({ meetingId, onSpeakersChange }: SpeakerEditorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingLabel, setEditingLabel] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [diarizationStatus, setDiarizationStatus] = useState<string>('not_started');
  const [error, setError] = useState<string | null>(null);
  const [pyannoteAvailable, setPyannoteAvailable] = useState(false);

  // Check diarization availability
  useEffect(() => {
    const checkAvailability = async () => {
      try {
        const response = await fetch(`${API_BASE}/speakers/status`);
        if (response.ok) {
          const data = await response.json();
          setPyannoteAvailable(data.pyannote_available);
        }
      } catch (err) {
        console.error('Failed to check diarization availability:', err);
      }
    };
    checkAvailability();
  }, []);

  // Fetch speakers when dialog opens
  useEffect(() => {
    if (isOpen) {
      fetchSpeakers();
      fetchDiarizationStatus();
    }
  }, [isOpen, meetingId]);

  const fetchSpeakers = async () => {
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/speakers`);
      if (response.ok) {
        const data = await response.json();
        setSpeakers(data);
        onSpeakersChange?.(data);
      }
    } catch (err) {
      console.error('Failed to fetch speakers:', err);
    }
  };

  const fetchDiarizationStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/diarization-status`);
      if (response.ok) {
        const data = await response.json();
        setDiarizationStatus(data.status || 'not_started');
      }
    } catch (err) {
      console.error('Failed to fetch diarization status:', err);
    }
  };

  const handleStartDiarization = async (audioPath: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/diarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ audio_path: audioPath })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to start diarization');
      }

      setDiarizationStatus('processing');

      // Poll for completion
      const pollInterval = setInterval(async () => {
        const statusResponse = await fetch(`${API_BASE}/meetings/${meetingId}/diarization-status`);
        if (statusResponse.ok) {
          const statusData = await statusResponse.json();
          setDiarizationStatus(statusData.status);

          if (statusData.status === 'completed' || statusData.status === 'failed') {
            clearInterval(pollInterval);
            if (statusData.status === 'completed') {
              fetchSpeakers();
            }
            if (statusData.status === 'failed' && statusData.error) {
              setError(statusData.error);
            }
          }
        }
      }, 2000);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start diarization');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveLabel = async (speakerId: string) => {
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/speakers/${speakerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: editingLabel })
      });

      if (response.ok) {
        setSpeakers(prev =>
          prev.map(s => s.id === speakerId ? { ...s, label: editingLabel } : s)
        );
        setEditingId(null);
        onSpeakersChange?.(speakers.map(s => s.id === speakerId ? { ...s, label: editingLabel } : s));
      }
    } catch (err) {
      console.error('Failed to update speaker:', err);
    }
  };

  const handleDeleteSpeaker = async (speakerId: string) => {
    try {
      const response = await fetch(`${API_BASE}/meetings/${meetingId}/speakers/${speakerId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        const newSpeakers = speakers.filter(s => s.id !== speakerId);
        setSpeakers(newSpeakers);
        onSpeakersChange?.(newSpeakers);
      }
    } catch (err) {
      console.error('Failed to delete speaker:', err);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2">
          <Users className="h-4 w-4" />
          Speakers
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Speaker Identification
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Status indicator */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <p className="text-sm font-medium">Diarization Status</p>
              <p className={cn(
                "text-xs",
                diarizationStatus === 'completed' && "text-green-600",
                diarizationStatus === 'processing' && "text-blue-600",
                diarizationStatus === 'failed' && "text-red-600",
                diarizationStatus === 'not_started' && "text-gray-500"
              )}>
                {diarizationStatus === 'not_started' ? 'Not started' :
                  diarizationStatus === 'processing' ? 'Processing...' :
                    diarizationStatus === 'completed' ? 'Completed' :
                      diarizationStatus === 'failed' ? 'Failed' : diarizationStatus}
              </p>
            </div>
            {!pyannoteAvailable && (
              <div className="flex items-center text-xs text-amber-600">
                <AlertCircle className="h-4 w-4 mr-1" />
                Basic mode
              </div>
            )}
          </div>

          {/* Error message */}
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-600 text-sm">
              {error}
            </div>
          )}

          {/* Speaker list */}
          <div className="space-y-2">
            {speakers.length === 0 ? (
              <p className="text-sm text-gray-500 text-center py-4">
                No speakers identified yet.
              </p>
            ) : (
              speakers.map(speaker => (
                <div
                  key={speaker.id}
                  className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg"
                >
                  {editingId === speaker.id ? (
                    <div className="flex items-center gap-2 flex-1">
                      <input
                        type="text"
                        value={editingLabel}
                        onChange={(e) => setEditingLabel(e.target.value)}
                        className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                        autoFocus
                      />
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => handleSaveLabel(speaker.id)}
                      >
                        <Save className="h-4 w-4 text-green-600" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => setEditingId(null)}
                      >
                        <X className="h-4 w-4 text-gray-500" />
                      </Button>
                    </div>
                  ) : (
                    <>
                      <SpeakerLabel label={speaker.label} color={speaker.color} />
                      <div className="flex items-center gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={() => {
                            setEditingId(speaker.id);
                            setEditingLabel(speaker.label);
                          }}
                        >
                          <Edit2 className="h-4 w-4 text-gray-500" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={() => handleDeleteSpeaker(speaker.id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}
          </div>

          {/* Refresh button */}
          <Button
            variant="outline"
            className="w-full"
            onClick={fetchSpeakers}
            disabled={isLoading || diarizationStatus === 'processing'}
          >
            <RefreshCw className={cn("h-4 w-4 mr-2", isLoading && "animate-spin")} />
            Refresh Speakers
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
