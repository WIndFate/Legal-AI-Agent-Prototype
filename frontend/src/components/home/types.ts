export type InputMode = 'text' | 'file';

export interface UploadResult {
  contract_text: string;
  estimated_tokens: number;
  price_jpy: number;
  quote_mode: string;
  estimate_source: string;
  quote_token?: string | null;
  ocr_required: boolean;
  ocr_confidence?: 'high' | 'medium' | 'low' | null;
  ocr_warnings: string[];
  clause_preview?: Array<{ number: string; title: string }> | null;
  clause_count?: number | null;
  is_contract?: boolean | null;
  upload_token?: string | null;
  upload_name?: string | null;
  upload_mime_type?: string | null;
  pii_warnings: Array<{ type: string; text: string; start: number; end: number }>;
}
