/**
 * The four stages a document moves through, described once and rendered by
 * `WorkflowRail` (compact) and `WorkflowShowcase` (labelled).
 */
export interface PipelineStep {
  key: PipelineStepKey
  label: string
  icon: string
  description: string
}

export type PipelineStepKey = 'upload' | 'extract' | 'index' | 'ask'

export const PIPELINE_STEPS: PipelineStep[] = [
  {
    key: 'upload',
    label: 'Upload',
    icon: 'upload',
    description: 'PDFs and Word files. Duplicates are detected by content.',
  },
  {
    key: 'extract',
    label: 'Extract',
    icon: 'scan',
    description: 'Headings, paragraphs and tables, kept with their pages.',
  },
  {
    key: 'index',
    label: 'Index',
    icon: 'database',
    description: 'Each section becomes a searchable chunk.',
  },
  {
    key: 'ask',
    label: 'Ask',
    icon: 'chat',
    description: 'Answers come back with the passages behind them.',
  },
]
