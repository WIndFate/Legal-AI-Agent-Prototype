export function exampleRiskColor(level: string): string {
  if (level === '高') return '#dc2626';
  if (level === '中') return '#f59e0b';
  if (level === '低') return '#16a34a';
  return '#6b7280';
}

export function exampleRiskBg(level: string): string {
  if (level === '高') return '#fef2f2';
  if (level === '中') return '#fffbeb';
  if (level === '低') return '#f0fdf4';
  return '#f9fafb';
}
