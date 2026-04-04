import qrcode from 'qrcode-generator';

export interface ShareCardOptions {
  overallRisk: string;
  totalClauses: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  topFinding: string;
  referralCode: string;
  siteUrl: string;
  // Translated strings (caller resolves i18n)
  labels: {
    brandSubtitle: string;
    overallRiskLabel: string;
    clauseStats: string;       // e.g. "全9条項 · 高リスク1 · 中リスク3 · 低リスク5"
    incentiveText: string;     // e.g. "友だちも自分も次回¥100オフ"
    referralLabel: string;     // e.g. "紹介コード"
  };
}

const W = 1080;
const H = 1350;
const PAD = 80;
const CONTENT_W = W - PAD * 2;

const BG_TOP = '#1B2E4A';
const BG_BOTTOM = '#F7F4EE';
const BRAND_LIGHT = '#C8D6E8';
const TEXT_WHITE = '#FFFFFF';
const TEXT_DARK = '#1A1714';
const TEXT_FAINT = '#9A9189';
const SUCCESS = '#2D7B62';
const DANGER = '#C0392B';
const WARNING = '#D4881C';
const GOLD_TEXT = '#7D5D2D';

const FONT = '"Noto Sans JP", "Noto Sans SC", "Noto Sans KR", "Helvetica Neue", Arial, sans-serif';

function riskColor(level: string): string {
  if (['高', 'High', '높음', 'Alto', 'Tinggi', 'Cao', 'उच्च'].some(k => level.includes(k))) return DANGER;
  if (['中', 'Medium', '중간', 'Médio', 'Sedang', 'Trung bình', 'मध्यम'].some(k => level.includes(k))) return WARNING;
  return SUCCESS;
}

function wrapText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number, maxLines: number): string[] {
  const lines: string[] = [];
  let remaining = text;

  while (remaining.length > 0 && lines.length < maxLines) {
    let end = remaining.length;
    while (ctx.measureText(remaining.slice(0, end)).width > maxWidth && end > 1) {
      end--;
    }
    if (end < remaining.length && end > 10) {
      const breakIdx = remaining.lastIndexOf('。', end);
      const commaIdx = remaining.lastIndexOf('、', end);
      const spaceIdx = remaining.lastIndexOf(' ', end);
      const best = Math.max(breakIdx, commaIdx, spaceIdx);
      if (best > end * 0.4) end = best + 1;
    }
    let line = remaining.slice(0, end);
    remaining = remaining.slice(end);
    if (lines.length === maxLines - 1 && remaining.length > 0) {
      line = line.trimEnd().replace(/[。、，,.]+$/, '') + '…';
      remaining = '';
    }
    lines.push(line);
  }
  return lines;
}

function drawRoundedRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawShieldIcon(ctx: CanvasRenderingContext2D, cx: number, cy: number, size: number) {
  ctx.save();
  ctx.translate(cx, cy);
  const s = size / 40;
  ctx.beginPath();
  ctx.moveTo(0, -18 * s);
  ctx.lineTo(16 * s, -10 * s);
  ctx.lineTo(16 * s, 4 * s);
  ctx.quadraticCurveTo(16 * s, 16 * s, 0, 20 * s);
  ctx.quadraticCurveTo(-16 * s, 16 * s, -16 * s, 4 * s);
  ctx.lineTo(-16 * s, -10 * s);
  ctx.closePath();

  ctx.fillStyle = 'rgba(255,255,255,0.15)';
  ctx.fill();

  // Checkmark
  ctx.strokeStyle = TEXT_WHITE;
  ctx.lineWidth = 3 * s;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();
  ctx.moveTo(-6 * s, 1 * s);
  ctx.lineTo(-1 * s, 6 * s);
  ctx.lineTo(8 * s, -4 * s);
  ctx.stroke();
  ctx.restore();
}

function drawQrCode(ctx: CanvasRenderingContext2D, url: string, x: number, y: number, size: number) {
  const qr = qrcode(0, 'M');
  qr.addData(url);
  qr.make();

  const moduleCount = qr.getModuleCount();
  const cellSize = size / moduleCount;

  // White background
  ctx.save();
  drawRoundedRect(ctx, x - 10, y - 10, size + 20, size + 20, 8);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.restore();

  // Draw modules
  ctx.fillStyle = BG_TOP;
  for (let row = 0; row < moduleCount; row++) {
    for (let col = 0; col < moduleCount; col++) {
      if (qr.isDark(row, col)) {
        ctx.fillRect(x + col * cellSize, y + row * cellSize, cellSize + 0.5, cellSize + 0.5);
      }
    }
  }
}

export async function generateShareCard(options: ShareCardOptions): Promise<Blob> {
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;

  // ── Dark header zone (top 38%) ──
  const headerH = 520;
  const gradient = ctx.createLinearGradient(0, 0, 0, headerH);
  gradient.addColorStop(0, '#1A2D48');
  gradient.addColorStop(1, '#243B5C');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, W, headerH);

  // Light lower zone
  ctx.fillStyle = BG_BOTTOM;
  ctx.fillRect(0, headerH, W, H - headerH);

  // Subtle pattern overlay on header
  ctx.fillStyle = 'rgba(255,255,255,0.02)';
  for (let i = 0; i < 6; i++) {
    ctx.beginPath();
    ctx.arc(W * 0.8 + i * 40, 120 + i * 30, 180 - i * 20, 0, Math.PI * 2);
    ctx.fill();
  }

  let y = PAD;

  // ── Brand: shield + name ──
  drawShieldIcon(ctx, PAD + 26, y + 26, 44);
  ctx.font = `700 42px ${FONT}`;
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText('ContractGuard', PAD + 64, y + 24);

  ctx.font = `400 22px ${FONT}`;
  ctx.fillStyle = BRAND_LIGHT;
  ctx.fillText(options.labels.brandSubtitle, PAD + 64, y + 62);
  y += 120;

  // ── Risk level label ──
  ctx.font = `500 26px ${FONT}`;
  ctx.fillStyle = BRAND_LIGHT;
  ctx.textBaseline = 'top';
  ctx.fillText(options.labels.overallRiskLabel, PAD, y);
  y += 48;

  // ── Risk badge (large) ──
  const color = riskColor(options.overallRisk);
  const badgeText = options.overallRisk;
  ctx.font = `800 72px ${FONT}`;
  const badgeW = ctx.measureText(badgeText).width + 72;
  drawRoundedRect(ctx, PAD, y, badgeW, 100, 20);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.font = `800 72px ${FONT}`;
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText(badgeText, PAD + 36, y + 52);
  y += 130;

  // ── Clause stats with colored dots ──
  ctx.font = `500 28px ${FONT}`;
  ctx.fillStyle = 'rgba(255,255,255,0.85)';
  ctx.textBaseline = 'top';
  ctx.fillText(options.labels.clauseStats, PAD, y);
  y += 52;

  // Stat pills
  const pillConfigs = [
    { count: options.highCount, color: DANGER, bg: 'rgba(192,57,43,0.25)' },
    { count: options.mediumCount, color: WARNING, bg: 'rgba(212,136,28,0.25)' },
    { count: options.lowCount, color: SUCCESS, bg: 'rgba(45,123,98,0.25)' },
  ];
  let px = PAD;
  for (const pill of pillConfigs) {
    if (pill.count <= 0) continue;
    const pillW = 72;
    drawRoundedRect(ctx, px, y, pillW, 40, 20);
    ctx.fillStyle = pill.bg;
    ctx.fill();
    ctx.fillStyle = pill.color;
    ctx.font = `700 12px ${FONT}`;
    ctx.textBaseline = 'middle';
    // Circle dot
    ctx.beginPath();
    ctx.arc(px + 18, y + 20, 5, 0, Math.PI * 2);
    ctx.fill();
    // Count
    ctx.font = `700 22px ${FONT}`;
    ctx.fillText(String(pill.count), px + 30, y + 21);
    px += pillW + 12;
  }
  // y is now at bottom of header zone — move into content zone

  // ── White content card overlapping header/body boundary ──
  const cardX = PAD;
  const cardY = headerH - 20;
  const cardW = CONTENT_W;

  // Measure finding height
  ctx.font = `400 28px ${FONT}`;
  const findingLines = options.topFinding
    ? wrapText(ctx, options.topFinding, cardW - 80, 3)
    : [];
  const findingBlockH = findingLines.length > 0 ? 56 + findingLines.length * 42 + 24 : 0;
  const cardH = findingBlockH + 130; // incentive + padding

  // Draw card
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.08)';
  ctx.shadowBlur = 40;
  ctx.shadowOffsetY = 8;
  drawRoundedRect(ctx, cardX, cardY, cardW, cardH, 24);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.restore();

  let cy = cardY + 36;

  // ── Top finding quote ──
  if (findingLines.length > 0) {
    // Left accent bar
    const barColor = riskColor(options.overallRisk);
    drawRoundedRect(ctx, cardX + 28, cy, 4, findingLines.length * 42 + 4, 2);
    ctx.fillStyle = barColor;
    ctx.fill();

    ctx.font = `400 28px ${FONT}`;
    ctx.fillStyle = TEXT_DARK;
    ctx.textBaseline = 'top';
    findingLines.forEach((line, i) => {
      ctx.fillText(line, cardX + 48, cy + i * 42);
    });
    cy += findingLines.length * 42 + 32;
  }

  // ── Incentive line inside card ──
  drawRoundedRect(ctx, cardX + 28, cy, cardW - 56, 64, 14);
  ctx.fillStyle = 'rgba(250,241,222,0.7)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(176,138,74,0.2)';
  ctx.lineWidth = 1;
  drawRoundedRect(ctx, cardX + 28, cy, cardW - 56, 64, 14);
  ctx.stroke();

  ctx.font = `600 24px ${FONT}`;
  ctx.fillStyle = GOLD_TEXT;
  ctx.textBaseline = 'middle';
  ctx.fillText(options.labels.incentiveText, cardX + 56, cy + 32);

  // ── QR + URL section (below the card) ──
  const qrSectionY = cardY + cardH + 48;
  const qrSize = 180;
  const qrUrl = `${options.siteUrl}?ref=${options.referralCode}`;
  const qrX = W / 2 - qrSize / 2;
  drawQrCode(ctx, qrUrl, qrX, qrSectionY, qrSize);

  const textY = qrSectionY + qrSize + 28;
  ctx.textAlign = 'center';
  ctx.font = `600 28px ${FONT}`;
  ctx.fillStyle = TEXT_DARK;
  ctx.textBaseline = 'top';
  ctx.fillText(options.siteUrl.replace('https://', ''), W / 2, textY);

  ctx.font = `400 20px ${FONT}`;
  ctx.fillStyle = TEXT_FAINT;
  ctx.fillText(`${options.labels.referralLabel}: ${options.referralCode}`, W / 2, textY + 40);

  ctx.textAlign = 'left';

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('Canvas toBlob failed'));
    }, 'image/png');
  });
}
