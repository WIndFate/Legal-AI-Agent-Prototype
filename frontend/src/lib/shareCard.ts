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

function splitClauseStatsText(text: string): string[] {
  const bullet = '·';
  if (!text.includes(bullet)) return [text];

  const parts = text.split(bullet).map((part) => part.trim()).filter(Boolean);
  if (parts.length <= 1) return [text];

  const firstLine = parts[0];
  const secondLine = parts.slice(1).join(` ${bullet} `);
  return [firstLine, secondLine];
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
  const headerH = 420;
  const gradient = ctx.createLinearGradient(0, 0, 0, headerH + 40);
  gradient.addColorStop(0, '#172842');
  gradient.addColorStop(0.7, '#1F3A5C');
  gradient.addColorStop(1, '#264570');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, W, headerH);

  // Light lower zone
  ctx.fillStyle = BG_BOTTOM;
  ctx.fillRect(0, headerH, W, H - headerH);

  // Subtle decorative circles on header
  ctx.fillStyle = 'rgba(255,255,255,0.015)';
  for (let i = 0; i < 4; i++) {
    ctx.beginPath();
    ctx.arc(W * 0.85 - i * 20, 80 + i * 60, 200 - i * 30, 0, Math.PI * 2);
    ctx.fill();
  }

  let y = PAD;

  // ── Brand: shield + name ──
  drawShieldIcon(ctx, PAD + 24, y + 22, 40);
  ctx.font = `700 38px ${FONT}`;
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText('ContractGuard', PAD + 60, y + 20);

  ctx.font = `400 20px ${FONT}`;
  ctx.fillStyle = BRAND_LIGHT;
  ctx.fillText(options.labels.brandSubtitle, PAD + 60, y + 54);
  y += 96;

  // ── Thin separator ──
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(PAD, y);
  ctx.lineTo(W - PAD, y);
  ctx.stroke();
  y += 32;

  // ── Risk level label ──
  ctx.font = `500 22px ${FONT}`;
  ctx.fillStyle = 'rgba(200,214,232,0.7)';
  ctx.textBaseline = 'top';
  ctx.fillText(options.labels.overallRiskLabel, PAD, y);
  y += 36;

  // ── Risk badge ──
  const color = riskColor(options.overallRisk);
  const badgeText = options.overallRisk;
  ctx.font = `800 64px ${FONT}`;
  const badgeW = ctx.measureText(badgeText).width + 60;
  drawRoundedRect(ctx, PAD, y, badgeW, 86, 18);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText(badgeText, PAD + 30, y + 45);

  // ── Clause stats on the same line, right-aligned ──
  const headerStatLines = splitClauseStatsText(options.labels.clauseStats);
  ctx.font = `600 22px ${FONT}`;
  ctx.fillStyle = 'rgba(255,255,255,0.8)';
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'right';
  headerStatLines.forEach((line, index) => {
    ctx.fillText(line, W - PAD, y + 28 + index * 30);
  });
  ctx.textAlign = 'left';

  // ── White content card overlapping header/body boundary ──
  const cardX = PAD;
  const cardY = headerH - 36;
  const cardW = CONTENT_W;

  // Measure finding height
  ctx.font = `400 26px ${FONT}`;
  const findingLines = options.topFinding
    ? wrapText(ctx, options.topFinding, cardW - 80, 4)
    : [];
  const findingBlockH = findingLines.length > 0 ? findingLines.length * 38 + 24 : 0;
  const cardH = findingBlockH + 56;

  // Draw card shadow + fill
  ctx.save();
  ctx.shadowColor = 'rgba(0,0,0,0.06)';
  ctx.shadowBlur = 30;
  ctx.shadowOffsetY = 6;
  drawRoundedRect(ctx, cardX, cardY, cardW, cardH, 20);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.restore();

  // ── Top finding quote ──
  if (findingLines.length > 0) {
    const quoteY = cardY + 28;
    // Left accent bar
    const barColor = riskColor(options.overallRisk);
    drawRoundedRect(ctx, cardX + 28, quoteY, 4, findingLines.length * 38, 2);
    ctx.fillStyle = barColor;
    ctx.fill();

    ctx.font = `400 26px ${FONT}`;
    ctx.fillStyle = TEXT_DARK;
    ctx.textBaseline = 'top';
    findingLines.forEach((line, i) => {
      ctx.fillText(line, cardX + 48, quoteY + i * 38);
    });
  }

  // ── Lower info panel ──
  const panelX = PAD;
  const panelY = cardY + cardH + 30;
  const panelW = CONTENT_W;
  const panelH = H - panelY - PAD;
  drawRoundedRect(ctx, panelX, panelY, panelW, panelH, 28);
  ctx.fillStyle = 'rgba(255, 250, 243, 0.92)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(176,138,74,0.1)';
  ctx.lineWidth = 1.5;
  drawRoundedRect(ctx, panelX, panelY, panelW, panelH, 28);
  ctx.stroke();

  const rewardX = panelX + 44;
  const rewardY = panelY + 40;
  const qrCardW = 270;
  const qrCardX = panelX + panelW - qrCardW - 38;
  const qrCardY = panelY + 30;
  const qrCardH = panelH - 60;
  const qrSize = 170;
  const rewardW = qrCardX - rewardX - 40;

  // ¥ amount
  ctx.font = `800 76px ${FONT}`;
  ctx.fillStyle = '#B07A24';
  ctx.textBaseline = 'top';
  ctx.fillText(`¥${options.discountAmount}`, rewardX, rewardY);

  // Incentive text
  ctx.font = `600 28px ${FONT}`;
  ctx.fillStyle = GOLD_TEXT;
  const rewardLines = wrapText(ctx, options.labels.incentiveText, rewardW, 2);
  rewardLines.forEach((line, index) => {
    ctx.fillText(line, rewardX, rewardY + 100 + index * 38);
  });

  // Referral code label
  ctx.font = `500 17px ${FONT}`;
  ctx.fillStyle = TEXT_FAINT;
  ctx.fillText(options.labels.referralLabel, rewardX, rewardY + 196);

  // Referral code pill
  const codeY = rewardY + 226;
  ctx.font = `700 36px ${FONT}`;
  const codeW = ctx.measureText(options.referralCode).width + 48;
  drawRoundedRect(ctx, rewardX, codeY, codeW, 66, 33);
  ctx.fillStyle = 'rgba(255,255,255,0.88)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(176,138,74,0.15)';
  ctx.lineWidth = 1;
  drawRoundedRect(ctx, rewardX, codeY, codeW, 66, 33);
  ctx.stroke();
  ctx.fillStyle = '#B08A4A';
  ctx.textBaseline = 'middle';
  ctx.fillText(options.referralCode, rewardX + 24, codeY + 34);

  // Vertical divider
  ctx.strokeStyle = 'rgba(176,138,74,0.12)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(qrCardX - 22, panelY + 36);
  ctx.lineTo(qrCardX - 22, panelY + panelH - 36);
  ctx.stroke();

  // QR code card
  drawRoundedRect(ctx, qrCardX, qrCardY, qrCardW, qrCardH, 22);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  ctx.strokeStyle = 'rgba(31,58,95,0.06)';
  ctx.lineWidth = 1;
  drawRoundedRect(ctx, qrCardX, qrCardY, qrCardW, qrCardH, 22);
  ctx.stroke();

  const qrX = qrCardX + (qrCardW - qrSize) / 2;
  const qrY = qrCardY + 26;
  drawQrCode(ctx, options.shareUrl, qrX, qrY, qrSize);

  ctx.textAlign = 'center';
  ctx.font = `600 22px ${FONT}`;
  ctx.fillStyle = TEXT_DARK;
  ctx.textBaseline = 'top';
  ctx.fillText(options.siteUrl.replace(/^https?:\/\//, ''), qrCardX + qrCardW / 2, qrY + qrSize + 22);

  ctx.font = `400 16px ${FONT}`;
  ctx.fillStyle = TEXT_FAINT;
  ctx.fillText(`${options.labels.referralLabel}: ${options.referralCode}`, qrCardX + qrCardW / 2, qrY + qrSize + 52);

  ctx.textAlign = 'left';

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('Canvas toBlob failed'));
    }, 'image/png');
  });
}
