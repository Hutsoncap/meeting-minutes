'use client';

import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import {
  FileText,
  Plus,
  Star,
  Trash2,
  Edit3,
  Copy,
  ChevronDown,
  Briefcase,
  Zap,
  FileTextIcon,
  Code,
  Users,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

const API_BASE = 'http://localhost:5167';

interface TemplateSection {
  key: string;
  title: string;
  type: 'text' | 'list' | 'blocks' | 'notes';
}

interface TemplateSchema {
  sections: TemplateSection[];
}

interface Template {
  id: string;
  name: string;
  description: string;
  schema: TemplateSchema;
  prompt_template: string;
  is_default: number;
  is_preset: number;
  created_at: string;
  updated_at: string;
}

const templateIcons: Record<string, React.ReactNode> = {
  'Standard': <FileText className="w-5 h-5" />,
  'Action-Focused': <Zap className="w-5 h-5" />,
  'Brief': <FileTextIcon className="w-5 h-5" />,
  'Technical': <Code className="w-5 h-5" />,
  'Sales/Customer': <Users className="w-5 h-5" />,
};

const getTemplateIcon = (name: string) => {
  return templateIcons[name] || <Briefcase className="w-5 h-5" />;
};

export function TemplateSettings() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [templateToDelete, setTemplateToDelete] = useState<Template | null>(null);

  // Editor state
  const [editorMode, setEditorMode] = useState<'create' | 'edit' | 'view'>('view');
  const [editingTemplate, setEditingTemplate] = useState<Partial<Template>>({});

  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchTemplates = useCallback(async () => {
    setFetchError(null);
    try {
      const response = await fetch(`${API_BASE}/summary-templates`);
      if (!response.ok) throw new Error('Failed to fetch templates');
      const data = await response.json();
      setTemplates(data);

      // Set default template as selected
      const defaultTemplate = data.find((t: Template) => t.is_default === 1);
      if (defaultTemplate && !selectedTemplate) {
        setSelectedTemplate(defaultTemplate);
      }
    } catch (error) {
      console.error('Error fetching templates:', error);
      const errorMsg = error instanceof TypeError && error.message.includes('fetch')
        ? 'Cannot connect to backend. Please ensure the backend server is running on port 5167.'
        : 'Failed to load templates';
      setFetchError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [selectedTemplate]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleSetDefault = async (templateId: string) => {
    try {
      const response = await fetch(`${API_BASE}/summary-templates/${templateId}/set-default`, {
        method: 'POST',
      });
      if (!response.ok) throw new Error('Failed to set default template');
      toast.success('Default template updated');
      fetchTemplates();
    } catch (error) {
      console.error('Error setting default template:', error);
      toast.error('Failed to set default template');
    }
  };

  const handleDelete = async () => {
    if (!templateToDelete) return;

    try {
      const response = await fetch(`${API_BASE}/summary-templates/${templateToDelete.id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to delete template');
      }
      toast.success('Template deleted');
      setIsDeleteDialogOpen(false);
      setTemplateToDelete(null);
      if (selectedTemplate?.id === templateToDelete.id) {
        setSelectedTemplate(null);
      }
      fetchTemplates();
    } catch (error: any) {
      console.error('Error deleting template:', error);
      toast.error(error.message || 'Failed to delete template');
    }
  };

  const handleSaveTemplate = async () => {
    try {
      const method = editorMode === 'create' ? 'POST' : 'PUT';
      const url = editorMode === 'create'
        ? `${API_BASE}/summary-templates`
        : `${API_BASE}/summary-templates/${editingTemplate.id}`;

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: editingTemplate.name,
          description: editingTemplate.description || '',
          template_schema: editingTemplate.schema || { sections: [] },
          prompt_template: editingTemplate.prompt_template || '',
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to save template');
      }

      toast.success(editorMode === 'create' ? 'Template created' : 'Template updated');
      setIsEditorOpen(false);
      setEditingTemplate({});
      fetchTemplates();
    } catch (error: any) {
      console.error('Error saving template:', error);
      toast.error(error.message || 'Failed to save template');
    }
  };

  const handleDuplicate = (template: Template) => {
    setEditorMode('create');
    setEditingTemplate({
      name: `${template.name} (Copy)`,
      description: template.description,
      schema: JSON.parse(JSON.stringify(template.schema)),
      prompt_template: template.prompt_template,
    });
    setIsEditorOpen(true);
  };

  const handleEdit = (template: Template) => {
    if (template.is_preset === 1) {
      toast.error('Preset templates cannot be edited. Duplicate it to create a custom version.');
      return;
    }
    setEditorMode('edit');
    setEditingTemplate({
      ...template,
      schema: JSON.parse(JSON.stringify(template.schema)),
    });
    setIsEditorOpen(true);
  };

  const handleCreateNew = () => {
    setEditorMode('create');
    setEditingTemplate({
      name: 'New Template',
      description: '',
      schema: {
        sections: [
          { key: 'MeetingName', title: 'Meeting Name', type: 'text' },
          { key: 'Summary', title: 'Summary', type: 'blocks' },
          { key: 'ActionItems', title: 'Action Items', type: 'blocks' },
        ],
      },
      prompt_template: '',
    });
    setIsEditorOpen(true);
  };

  const addSection = () => {
    const sections = editingTemplate.schema?.sections || [];
    const newKey = `Section${sections.length + 1}`;
    setEditingTemplate({
      ...editingTemplate,
      schema: {
        sections: [
          ...sections,
          { key: newKey, title: 'New Section', type: 'blocks' },
        ],
      },
    });
  };

  const updateSection = (index: number, field: keyof TemplateSection, value: string) => {
    const sections = [...(editingTemplate.schema?.sections || [])];
    sections[index] = { ...sections[index], [field]: value };
    setEditingTemplate({
      ...editingTemplate,
      schema: { sections },
    });
  };

  const removeSection = (index: number) => {
    const sections = [...(editingTemplate.schema?.sections || [])];
    sections.splice(index, 1);
    setEditingTemplate({
      ...editingTemplate,
      schema: { sections },
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-center space-y-4">
        <div className="text-red-500">
          <AlertCircle className="w-12 h-12 mx-auto mb-2 opacity-70" />
          <p className="font-medium">Failed to Load Templates</p>
          <p className="text-sm text-gray-500 mt-2 max-w-md">{fetchError}</p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            setLoading(true);
            fetchTemplates();
          }}
          className="gap-2"
        >
          <RefreshCw className="w-4 h-4" />
          Try Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Summary Templates</h3>
          <p className="text-sm text-gray-600 mt-1">
            Choose a template to customize how your meeting summaries are structured.
          </p>
        </div>
        <Button onClick={handleCreateNew} className="flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Create Template
        </Button>
      </div>

      {/* Template Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {templates.map((template) => (
          <div
            key={template.id}
            className={`
              relative p-4 rounded-lg border-2 cursor-pointer transition-all
              ${selectedTemplate?.id === template.id
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300 bg-white'}
              ${template.is_default === 1 ? 'ring-2 ring-amber-200' : ''}
            `}
            onClick={() => setSelectedTemplate(template)}
          >
            {/* Default Badge */}
            {template.is_default === 1 && (
              <div className="absolute -top-2 -right-2 bg-amber-400 text-amber-900 text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1">
                <Star className="w-3 h-3 fill-current" />
                Default
              </div>
            )}

            {/* Preset Badge */}
            {template.is_preset === 1 && (
              <div className="absolute top-2 left-2 bg-gray-100 text-gray-600 text-xs font-medium px-2 py-0.5 rounded">
                Preset
              </div>
            )}

            <div className="flex items-start gap-3 mt-4">
              <div className={`
                p-2 rounded-lg
                ${selectedTemplate?.id === template.id ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'}
              `}>
                {getTemplateIcon(template.name)}
              </div>
              <div className="flex-1 min-w-0">
                <h4 className="font-semibold text-gray-900 truncate">{template.name}</h4>
                <p className="text-sm text-gray-500 mt-1 line-clamp-2">{template.description}</p>
              </div>
            </div>

            {/* Sections Preview */}
            <div className="mt-4 flex flex-wrap gap-1">
              {template.schema?.sections?.slice(0, 4).map((section, idx) => (
                <span key={idx} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {section.title}
                </span>
              ))}
              {(template.schema?.sections?.length || 0) > 4 && (
                <span className="text-xs text-gray-400">
                  +{(template.schema?.sections?.length || 0) - 4} more
                </span>
              )}
            </div>

            {/* Actions */}
            <div className="mt-4 pt-3 border-t border-gray-100 flex items-center gap-2">
              {template.is_default !== 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleSetDefault(template.id);
                  }}
                  className="text-xs"
                >
                  <Star className="w-3 h-3 mr-1" />
                  Set Default
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  handleDuplicate(template);
                }}
                className="text-xs"
              >
                <Copy className="w-3 h-3 mr-1" />
                Duplicate
              </Button>
              {template.is_preset !== 1 && (
                <>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEdit(template);
                    }}
                    className="text-xs"
                  >
                    <Edit3 className="w-3 h-3 mr-1" />
                    Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setTemplateToDelete(template);
                      setIsDeleteDialogOpen(true);
                    }}
                    className="text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Template Editor Dialog */}
      <Dialog open={isEditorOpen} onOpenChange={setIsEditorOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editorMode === 'create' ? 'Create Template' : 'Edit Template'}
            </DialogTitle>
            <DialogDescription>
              Define the sections that will appear in your meeting summaries.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Basic Info */}
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700">Template Name</label>
                <Input
                  value={editingTemplate.name || ''}
                  onChange={(e) => setEditingTemplate({ ...editingTemplate, name: e.target.value })}
                  placeholder="e.g., Weekly Standup"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Description</label>
                <Input
                  value={editingTemplate.description || ''}
                  onChange={(e) => setEditingTemplate({ ...editingTemplate, description: e.target.value })}
                  placeholder="Brief description of when to use this template"
                  className="mt-1"
                />
              </div>
            </div>

            {/* Sections */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-gray-700">Sections</label>
                <Button variant="outline" size="sm" onClick={addSection}>
                  <Plus className="w-3 h-3 mr-1" />
                  Add Section
                </Button>
              </div>

              <div className="space-y-3">
                {editingTemplate.schema?.sections?.map((section, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="flex-1 grid grid-cols-3 gap-3">
                      <Input
                        value={section.key}
                        onChange={(e) => updateSection(idx, 'key', e.target.value)}
                        placeholder="Key"
                        className="text-sm"
                      />
                      <Input
                        value={section.title}
                        onChange={(e) => updateSection(idx, 'title', e.target.value)}
                        placeholder="Display Title"
                        className="text-sm"
                      />
                      <select
                        value={section.type}
                        onChange={(e) => updateSection(idx, 'type', e.target.value as any)}
                        className="text-sm border rounded-md px-3 py-2 bg-white"
                      >
                        <option value="text">Text</option>
                        <option value="blocks">Blocks</option>
                        <option value="list">List</option>
                        <option value="notes">Notes</option>
                      </select>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeSection(idx)}
                      className="text-red-500 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Custom Prompt */}
            <div>
              <label className="text-sm font-medium text-gray-700">Custom Prompt (Optional)</label>
              <p className="text-xs text-gray-500 mt-1 mb-2">
                Add specific instructions for the AI when generating summaries with this template.
              </p>
              <Textarea
                value={editingTemplate.prompt_template || ''}
                onChange={(e) => setEditingTemplate({ ...editingTemplate, prompt_template: e.target.value })}
                placeholder="e.g., Focus on technical decisions and code architecture..."
                rows={3}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditorOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveTemplate}>
              {editorMode === 'create' ? 'Create Template' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Template</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete "{templateToDelete?.name}"? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
