"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ButtonGroup } from '@/components/ui/button-group';
import { Copy, Save, Loader2, FolderOpen, Download, FileText, FileType, ChevronDown } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import Analytics from '@/lib/analytics';
import { exportAsMarkdown, exportAsPDF, exportAsDocx, Summary } from '@/lib/exportUtils';
import { toast } from 'sonner';

interface SummaryUpdaterButtonGroupProps {
  isSaving: boolean;
  isDirty: boolean;
  onSave: () => Promise<void>;
  onCopy: () => Promise<void>;
  onFind?: () => void;
  onOpenFolder: () => Promise<void>;
  hasSummary: boolean;
  summary?: Summary | null;
  meetingTitle?: string;
}

export function SummaryUpdaterButtonGroup({
  isSaving,
  isDirty,
  onSave,
  onCopy,
  onFind,
  onOpenFolder,
  hasSummary,
  summary,
  meetingTitle = 'Meeting Summary'
}: SummaryUpdaterButtonGroupProps) {
  const [isExporting, setIsExporting] = useState(false);

  const handleExportMarkdown = () => {
    if (!summary) return;
    try {
      Analytics.trackButtonClick('export_markdown', 'meeting_details');
      exportAsMarkdown(summary, meetingTitle);
      toast.success('Exported as Markdown');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export as Markdown');
    }
  };

  const handleExportPDF = () => {
    if (!summary) return;
    try {
      Analytics.trackButtonClick('export_pdf', 'meeting_details');
      exportAsPDF(summary, meetingTitle);
      toast.success('Exported as PDF');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export as PDF');
    }
  };

  const handleExportDocx = async () => {
    if (!summary) return;
    setIsExporting(true);
    try {
      Analytics.trackButtonClick('export_docx', 'meeting_details');
      await exportAsDocx(summary, meetingTitle);
      toast.success('Exported as Word document');
    } catch (error) {
      console.error('Export failed:', error);
      toast.error('Failed to export as Word document');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <ButtonGroup>
      {/* Save button */}
      <Button
        variant="outline"
        size="sm"
        className={`${isDirty ? 'bg-green-200' : ""}`}
        title={isSaving ? "Saving" : "Save Changes"}
        onClick={() => {
          Analytics.trackButtonClick('save_changes', 'meeting_details');
          onSave();
        }}
        disabled={isSaving}
      >
        {isSaving ? (
          <>
            <Loader2 className="animate-spin" />
            <span className="hidden lg:inline">Saving...</span>
          </>
        ) : (
          <>
            <Save />
            <span className="hidden lg:inline">Save</span>
          </>
        )}
      </Button>

      {/* Copy button */}
      <Button
        variant="outline"
        size="sm"
        title="Copy Summary"
        onClick={() => {
          Analytics.trackButtonClick('copy_summary', 'meeting_details');
          onCopy();
        }}
        disabled={!hasSummary}
        className="cursor-pointer"
      >
        <Copy />
        <span className="hidden lg:inline">Copy</span>
      </Button>

      {/* Recording folder button */}
      <Button
        variant="outline"
        size="sm"
        className="xl:px-4"
        onClick={() => {
          Analytics.trackButtonClick('open_recording_folder', 'meeting_details');
          onOpenFolder();
        }}
        title="Open Recording Folder"
      >
        <FolderOpen className="xl:mr-2" size={18} />
        <span className="hidden xl:inline">Recording</span>
      </Button>

      {/* Export dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasSummary || isExporting}
            title="Export Summary"
          >
            {isExporting ? (
              <Loader2 className="animate-spin" size={18} />
            ) : (
              <Download size={18} />
            )}
            <span className="hidden lg:inline ml-1">Export</span>
            <ChevronDown size={14} className="ml-1" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={handleExportMarkdown}>
            <FileText className="mr-2 h-4 w-4" />
            Markdown (.md)
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleExportPDF}>
            <FileType className="mr-2 h-4 w-4" />
            PDF (.pdf)
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleExportDocx}>
            <FileText className="mr-2 h-4 w-4" />
            Word (.docx)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </ButtonGroup>
  );
}
