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
  shareUrl: string;
  discountAmount: number;
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
const TEXT_SOFT = '#5F5852';
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

  // ── Dark header zone ──
  const headerH = 470;
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

  let y = PAD - 2;

  // ── Brand: shield + name ──
  drawShieldIcon(ctx, PAD + 26, y + 26, 44);
  ctx.font = `700 42px ${FONT}`;
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText('ContractGuard', PAD + 64, y + 24);

  ctx.font = `400 22px ${FONT}`;
  ctx.fillStyle = BRAND_LIGHT;
  ctx.fillText(options.labels.brandSubtitle, PAD + 64, y + 62);
  y += 108;

  // ── Risk level label ──
  ctx.font = `500 26px ${FONT}`;
  ctx.fillStyle = BRAND_LIGHT;
  ctx.textBaseline = 'top';
  ctx.fillText(options.labels.overallRiskLabel, PAD, y);
  y += 38;

  // ── Risk badge (large) ──
  const color = riskColor(options.overallRisk);
  const badgeText = options.overallRisk;
  ctx.font = `800 72px ${FONT}`;
  const badgeW = ctx.measureText(badgeText).width + 72;
  drawRoundedRect(ctx, PAD, y, badgeW, 96, 20);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.font = `800 72px ${FONT}`;
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText(badgeText, PAD + 36, y + 50);
  const headerStatsX = W - PAD - 360;
  const headerStatsY = y + 10;
  ctx.font = `700 26px ${FONT}`;
  ctx.fillStyle = 'rgba(255,255,255,0.88)';
  ctx.textBaseline = 'top';
  ctx.textAlign = 'right';
  const headerStatLines = wrapText(ctx, options.labels.clauseStats, 360, 2);
  headerStatLines.forEach((line, index) => {
    ctx.fillText(line, W - PAD, headerStatsY + index * 34);
  });
  ctx.textAlign = 'left';

  // ── White content card overlapping header/body boundary ──
  const cardX = PAD;
  const cardY = headerH - 48;
  const cardW = CONTENT_W;

  // Measure finding height
  ctx.font = `400 28px ${FONT}`;
  const findingLines = options.topFinding
    ? wrapText(ctx, options.topFinding, cardW - 96, 4)
    : [];
  const findingBlockH = findingLines.length > 0 ? 72 + findingLines.length * 42 + 26 : 0;
  const cardH = findingBlockH + 118;

  // Draw card
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.08)';
  ctx.shadowBlur = 40;
  ctx.shadowOffsetY = 8;
  drawRoundedRect(ctx, cardX, cardY, cardW, cardH, 24);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.restore();

  let cy = cardY + 34;

  // ── Top finding quote ──
  if (findingLines.length > 0) {
    // Left accent bar
    const barColor = riskColor(options.overallRisk);
    drawRoundedRect(ctx, cardX + 30, cy, 4, findingLines.length * 42 + 4, 2);
    ctx.fillStyle = barColor;
    ctx.fill();

    ctx.font = `400 26px ${FONT}`;
    ctx.fillStyle = TEXT_DARK;
    ctx.textBaseline = 'top';
    findingLines.forEach((line, i) => {
      ctx.fillText(line, cardX + 56, cy + i * 40);
    });
    cy += findingLines.length * 40 + 34;
  }

  // ── Incentive line inside card ──
  drawRoundedRect(ctx, cardX + 28, cy, cardW - 56, 68, 16);
  ctx.fillStyle = 'rgba(250,241,222,0.7)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(176,138,74,0.2)';
  ctx.lineWidth = 1;
  drawRoundedRect(ctx, cardX + 28, cy, cardW - 56, 68, 16);
  ctx.stroke();

  ctx.font = `600 24px ${FONT}`;
  ctx.fillStyle = GOLD_TEXT;
  ctx.textBaseline = 'middle';
  ctx.fillText(options.labels.incentiveText, cardX + 56, cy + 34);

  // ── Lower info panel ──
  const panelX = PAD;
  const panelY = cardY + cardH + 38;
  const panelW = CONTENT_W;
  const panelH = H - panelY - PAD;
  drawRoundedRect(ctx, panelX, panelY, panelW, panelH, 30);
  ctx.fillStyle = 'rgba(255, 250, 243, 0.9)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(176,138,74,0.12)';
  ctx.lineWidth = 2;
  ctx.stroke();

  const rewardX = panelX + 48;
  const rewardY = panelY + 44;
  const rewardW = 430;
  const qrCardW = 286;
  const qrCardX = panelX + panelW - qrCardW - 42;
  const qrCardY = panelY + 34;
  const qrCardH = panelH - 68;
  const qrSize = 182;

  ctx.font = `800 82px ${FONT}`;
  ctx.fillStyle = '#B07A24';
  ctx.textBaseline = 'top';
  ctx.fillText(`¥${options.discountAmount}`, rewardX, rewardY);

  ctx.font = `600 32px ${FONT}`;
  ctx.fillStyle = GOLD_TEXT;
  const rewardLines = wrapText(ctx, options.labels.incentiveText, rewardW - 12, 2);
  rewardLines.forEach((line, index) => {
    ctx.fillText(line, rewardX, rewardY + 106 + index * 42);
  });

  ctx.font = `500 18px ${FONT}`;
  ctx.fillStyle = TEXT_FAINT;
  ctx.fillText(options.labels.referralLabel, rewardX, rewardY + 206);

  const codeY = rewardY + 238;
  drawRoundedRect(ctx, rewardX, codeY, 236, 78, 39);
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.fill();
  ctx.font = `700 40px ${FONT}`;
  ctx.fillStyle = '#B08A4A';
  ctx.textBaseline = 'middle';
  ctx.fillText(options.referralCode, rewardX + 28, codeY + 39);

  ctx.font = `500 22px ${FONT}`;
  ctx.fillStyle = TEXT_SOFT;
  ctx.textBaseline = 'top';

  ctx.strokeStyle = 'rgba(176,138,74,0.14)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(qrCardX - 26, panelY + 42);
  ctx.lineTo(qrCardX - 26, panelY + panelH - 42);
  ctx.stroke();

  drawRoundedRect(ctx, qrCardX, qrCardY, qrCardW, qrCardH, 24);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.strokeStyle = 'rgba(31,58,95,0.08)';
  ctx.lineWidth = 2;
  ctx.stroke();

  const qrX = qrCardX + (qrCardW - qrSize) / 2;
  const qrY = qrCardY + 28;
  drawQrCode(ctx, options.shareUrl, qrX, qrY, qrSize);

  ctx.textAlign = 'center';
  ctx.font = `600 24px ${FONT}`;
  ctx.fillStyle = TEXT_DARK;
  ctx.textBaseline = 'top';
  ctx.fillText(options.siteUrl.replace(/^https?:\/\//, ''), qrCardX + qrCardW / 2, qrY + qrSize + 24);

  ctx.font = `400 18px ${FONT}`;
  ctx.fillStyle = TEXT_FAINT;
  ctx.fillText(`${options.labels.referralLabel}: ${options.referralCode}`, qrCardX + qrCardW / 2, qrY + qrSize + 58);

  ctx.textAlign = 'left';

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('Canvas toBlob failed'));
    }, 'image/png');
  });
}
