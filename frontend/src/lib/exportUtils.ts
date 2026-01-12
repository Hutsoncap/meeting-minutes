import { jsPDF } from 'jspdf';
import { Document, Packer, Paragraph, TextRun, HeadingLevel } from 'docx';
import { saveAs } from 'file-saver';

// Flexible summary type that handles multiple formats
interface SummarySection {
  title?: string;
  content?: string | Array<string | { text?: string }>;
  blocks?: Array<{ text?: string }>;
  // BlockNote properties
  id?: string;
  type?: string;
  props?: Record<string, unknown>;
  children?: SummarySection[];
}

export interface Summary {
  markdown?: string;
  summary_json?: SummarySection[];
  [key: string]: unknown;
}

/**
 * Convert summary to plain text/markdown format
 */
export function summaryToMarkdown(summary: Summary, meetingTitle: string): string {
  const lines: string[] = [];

  lines.push(`# ${meetingTitle}`);
  lines.push('');
  lines.push(`*Generated on ${new Date().toLocaleDateString()}*`);
  lines.push('');

  // Handle different summary formats
  if (summary.markdown) {
    lines.push(summary.markdown);
  } else if (summary.summary_json && Array.isArray(summary.summary_json)) {
    for (const section of summary.summary_json) {
      if (section.title) {
        lines.push(`## ${section.title}`);
        lines.push('');
      }

      if (section.content) {
        if (Array.isArray(section.content)) {
          for (const item of section.content) {
            if (typeof item === 'string') {
              lines.push(`- ${item}`);
            } else if (item.text) {
              lines.push(`- ${item.text}`);
            }
          }
        } else if (typeof section.content === 'string') {
          lines.push(section.content);
        }
        lines.push('');
      }

      if (section.blocks && Array.isArray(section.blocks)) {
        for (const block of section.blocks) {
          if (block.text) {
            lines.push(`- ${block.text}`);
          }
        }
        lines.push('');
      }
    }
  } else {
    // Try to extract any text content
    const summaryStr = JSON.stringify(summary, null, 2);
    lines.push('```json');
    lines.push(summaryStr);
    lines.push('```');
  }

  return lines.join('\n');
}

/**
 * Export summary as Markdown file
 */
export function exportAsMarkdown(summary: Summary, meetingTitle: string): void {
  const markdown = summaryToMarkdown(summary, meetingTitle);
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
  const filename = `${sanitizeFilename(meetingTitle)}_summary.md`;
  saveAs(blob, filename);
}

/**
 * Export summary as PDF
 */
export function exportAsPDF(summary: Summary, meetingTitle: string): void {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  const maxWidth = pageWidth - (margin * 2);
  let yPosition = 20;

  // Title
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text(meetingTitle, margin, yPosition);
  yPosition += 10;

  // Date
  doc.setFontSize(10);
  doc.setFont('helvetica', 'italic');
  doc.text(`Generated on ${new Date().toLocaleDateString()}`, margin, yPosition);
  yPosition += 15;

  doc.setFont('helvetica', 'normal');
  doc.setFontSize(11);

  // Helper to add text with word wrap and page breaks
  const addText = (text: string, fontSize: number = 11, isBold: boolean = false) => {
    doc.setFontSize(fontSize);
    doc.setFont('helvetica', isBold ? 'bold' : 'normal');

    const lines = doc.splitTextToSize(text, maxWidth);
    for (const line of lines) {
      if (yPosition > doc.internal.pageSize.getHeight() - 20) {
        doc.addPage();
        yPosition = 20;
      }
      doc.text(line, margin, yPosition);
      yPosition += fontSize * 0.5;
    }
  };

  // Process summary content
  if (summary.markdown) {
    // Simple markdown to text conversion
    const lines = summary.markdown.split('\n');
    for (const line of lines) {
      if (line.startsWith('## ')) {
        yPosition += 5;
        addText(line.replace('## ', ''), 14, true);
        yPosition += 3;
      } else if (line.startsWith('# ')) {
        yPosition += 5;
        addText(line.replace('# ', ''), 16, true);
        yPosition += 3;
      } else if (line.startsWith('- ')) {
        addText(`• ${line.replace('- ', '')}`, 11);
      } else if (line.trim()) {
        addText(line, 11);
      } else {
        yPosition += 3;
      }
    }
  } else if (summary.summary_json && Array.isArray(summary.summary_json)) {
    for (const section of summary.summary_json) {
      if (section.title) {
        yPosition += 5;
        addText(section.title, 14, true);
        yPosition += 3;
      }

      if (section.content) {
        if (Array.isArray(section.content)) {
          for (const item of section.content) {
            const text = typeof item === 'string' ? item : item.text || '';
            if (text) addText(`• ${text}`, 11);
          }
        } else if (typeof section.content === 'string') {
          addText(section.content, 11);
        }
      }

      if (section.blocks && Array.isArray(section.blocks)) {
        for (const block of section.blocks) {
          if (block.text) {
            addText(`• ${block.text}`, 11);
          }
        }
      }
      yPosition += 5;
    }
  }

  const filename = `${sanitizeFilename(meetingTitle)}_summary.pdf`;
  doc.save(filename);
}

/**
 * Export summary as DOCX
 */
export async function exportAsDocx(summary: Summary, meetingTitle: string): Promise<void> {
  const children: Paragraph[] = [];

  // Title
  children.push(
    new Paragraph({
      text: meetingTitle,
      heading: HeadingLevel.TITLE,
    })
  );

  // Date
  children.push(
    new Paragraph({
      children: [
        new TextRun({
          text: `Generated on ${new Date().toLocaleDateString()}`,
          italics: true,
          size: 20,
        }),
      ],
    })
  );

  children.push(new Paragraph({ text: '' })); // Spacer

  // Process summary content
  if (summary.markdown) {
    const lines = summary.markdown.split('\n');
    for (const line of lines) {
      if (line.startsWith('## ')) {
        children.push(
          new Paragraph({
            text: line.replace('## ', ''),
            heading: HeadingLevel.HEADING_2,
          })
        );
      } else if (line.startsWith('# ')) {
        children.push(
          new Paragraph({
            text: line.replace('# ', ''),
            heading: HeadingLevel.HEADING_1,
          })
        );
      } else if (line.startsWith('- ')) {
        children.push(
          new Paragraph({
            text: line.replace('- ', ''),
            bullet: { level: 0 },
          })
        );
      } else if (line.trim()) {
        children.push(new Paragraph({ text: line }));
      }
    }
  } else if (summary.summary_json && Array.isArray(summary.summary_json)) {
    for (const section of summary.summary_json) {
      if (section.title) {
        children.push(
          new Paragraph({
            text: section.title,
            heading: HeadingLevel.HEADING_2,
          })
        );
      }

      if (section.content) {
        if (Array.isArray(section.content)) {
          for (const item of section.content) {
            const text = typeof item === 'string' ? item : item.text || '';
            if (text) {
              children.push(
                new Paragraph({
                  text: text,
                  bullet: { level: 0 },
                })
              );
            }
          }
        } else if (typeof section.content === 'string') {
          children.push(new Paragraph({ text: section.content }));
        }
      }

      if (section.blocks && Array.isArray(section.blocks)) {
        for (const block of section.blocks) {
          if (block.text) {
            children.push(
              new Paragraph({
                text: block.text,
                bullet: { level: 0 },
              })
            );
          }
        }
      }

      children.push(new Paragraph({ text: '' })); // Spacer
    }
  }

  const doc = new Document({
    sections: [
      {
        properties: {},
        children: children,
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  const filename = `${sanitizeFilename(meetingTitle)}_summary.docx`;
  saveAs(blob, filename);
}

/**
 * Sanitize filename by removing invalid characters
 */
function sanitizeFilename(name: string): string {
  return name
    .replace(/[<>:"/\\|?*]/g, '')
    .replace(/\s+/g, '_')
    .slice(0, 100);
}
