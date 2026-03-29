export type InputMode = 'text' | 'file';

export interface UploadResult {
  contract_text: string;
  estimated_tokens: number;
  price_jpy: number;
  quote_mode: string;
  estimate_source: string;
  ocr_required: boolean;
  ocr_confidence?: 'high' | 'medium' | 'low' | null;
  ocr_warnings: string[];
  upload_token?: string | null;
  upload_name?: string | null;
  upload_mime_type?: string | null;
  pii_warnings: Array<{ type: string; text: string; start: number; end: number }>;
}
