import qrcode from 'qrcode-generator';

export interface ShareCardOptions {
  overallRisk: string;
  totalClauses: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
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
const PAD = 72;
const CONTENT_W = W - PAD * 2;

const TEXT_WHITE = '#FFFFFF';
const TEXT_DARK = '#1A1714';
const TEXT_FAINT = '#9A9189';
const BRAND_LIGHT = '#C8D6E8';
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
    while (ctx.measureText(remaining.slice(0, end)).width > maxWidth && end > 1) end--;
    if (end < remaining.length && end > 10) {
      const best = Math.max(
        remaining.lastIndexOf('。', end),
        remaining.lastIndexOf('、', end),
        remaining.lastIndexOf(' ', end),
      );
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

function drawQrCode(ctx: CanvasRenderingContext2D, url: string, cx: number, cy: number, size: number) {
  const qr = qrcode(0, 'M');
  qr.addData(url);
  qr.make();
  const moduleCount = qr.getModuleCount();
  const cellSize = size / moduleCount;
  const x = cx - size / 2;
  const y = cy - size / 2;
  // White background
  drawRoundedRect(ctx, x - 8, y - 8, size + 16, size + 16, 6);
  ctx.fillStyle = '#FFFFFF';
  ctx.fill();
  // Modules
  ctx.fillStyle = '#1B2E4A';
  for (let row = 0; row < moduleCount; row++) {
    for (let col = 0; col < moduleCount; col++) {
      if (qr.isDark(row, col)) {
        ctx.fillRect(x + col * cellSize, y + row * cellSize, cellSize + 0.5, cellSize + 0.5);
      }
    }
  }
}

export async function generateShareCard(options: ShareCardOptions): Promise<Blob> {
  // ── Pre-measure ──
  const measureCanvas = document.createElement('canvas');
  measureCanvas.width = W;
  measureCanvas.height = 100;
  const mc = measureCanvas.getContext('2d')!;

  mc.font = `600 26px ${FONT}`;
  const incentiveLines = wrapText(mc, options.labels.incentiveText, 380, 2);

  // ── Calculate section heights ──
  const headerH = 424;     // brand + risk badge + stat blocks
  const qrSize = 160;
  const bottomH = Math.max(
    44 + 84 + 18 + incentiveLines.length * 34 + 22 + 52 + 8,
    36 + qrSize + 42,
  );
  const H = headerH + 20 + bottomH + 16;

  // ── Create canvas ──
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;

  // ── Background ──
  const bgGrad = ctx.createLinearGradient(0, 0, 0, headerH);
  bgGrad.addColorStop(0, '#152740');
  bgGrad.addColorStop(1, '#1E3958');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, headerH);
  ctx.fillStyle = '#F6F3EC';
  ctx.fillRect(0, headerH, W, H - headerH);

  // Subtle glow
  ctx.fillStyle = 'rgba(255,255,255,0.012)';
  ctx.beginPath();
  ctx.arc(W * 0.82, 100, 220, 0, Math.PI * 2);
  ctx.fill();

  // ── Brand row ──
  let y = 36;
  drawShieldIcon(ctx, PAD + 10, y + 22, 42);
  ctx.font = `700 44px ${FONT}`;
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText('ContractGuard', PAD + 42, y + 20);
  ctx.font = `500 22px ${FONT}`;
  ctx.fillStyle = BRAND_LIGHT;
  ctx.fillText(options.labels.brandSubtitle, PAD + 42, y + 56);
  y += 62;

  // ── Risk hero area ──
  const brandBottom = y;
  const heroTop = brandBottom + 10;
  const leftHeroX = PAD;
  const leftHeroY = heroTop + 38;
  const leftHeroH = 136;

  // Right badge spans the brand-subtitle band and the risk-label band without shrinking the brand area
  const color = riskColor(options.overallRisk);
  const badgeY = 70;
  ctx.font = `800 126px ${FONT}`;
  const badgeText = options.overallRisk;
  const badgeW = Math.max(220, ctx.measureText(badgeText).width + 108);
  const badgeH = 188;
  const badgeX = W - PAD - badgeW;
  drawRoundedRect(ctx, badgeX, badgeY, badgeW, badgeH, 28);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.fillStyle = TEXT_WHITE;
  ctx.textBaseline = 'middle';
  ctx.fillText(badgeText, badgeX + 52, badgeY + badgeH / 2 + 3);

  // Left risk label stays one line and uses the hero block height with vertical centering
  ctx.font = `700 48px ${FONT}`;
  ctx.fillStyle = 'rgba(200,214,232,0.94)';
  ctx.textBaseline = 'middle';
  ctx.fillText(options.labels.overallRiskLabel, leftHeroX, leftHeroY + leftHeroH / 2);

  const heroBottom = Math.max(leftHeroY + leftHeroH, badgeY + badgeH);

  // Thin line now sits below the whole hero block instead of slicing through it
  ctx.strokeStyle = 'rgba(255,255,255,0.06)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(PAD, heroBottom + 16);
  ctx.lineTo(W - PAD, heroBottom + 16);
  ctx.stroke();

  y = heroBottom + 34;

  // ── Risk stat blocks (colored number cards) ──
  const statConfigs = [
    { count: options.highCount, color: DANGER, bg: 'rgba(192,57,43,0.18)', label: 'High' },
    { count: options.mediumCount, color: WARNING, bg: 'rgba(212,136,28,0.18)', label: 'Med' },
    { count: options.lowCount, color: SUCCESS, bg: 'rgba(45,123,98,0.18)', label: 'Low' },
  ];
  const blockGap = 16;
  const blockW = (CONTENT_W - blockGap * 2) / 3;
  const blockH = 72;
  let bx = PAD;
  for (const stat of statConfigs) {
    // Block background
    drawRoundedRect(ctx, bx, y, blockW, blockH, 14);
    ctx.fillStyle = stat.bg;
    ctx.fill();
    // Large count number
    ctx.font = `800 36px ${FONT}`;
    ctx.fillStyle = stat.color;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    ctx.fillText(String(stat.count), bx + 20, y + blockH / 2 - 1);
    // Label
    const numW = ctx.measureText(String(stat.count)).width;
    ctx.font = `600 18px ${FONT}`;
    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.fillText(stat.label, bx + 20 + numW + 10, y + blockH / 2);
    // Total clause count on the rightmost block
    if (stat === statConfigs[statConfigs.length - 1]) {
      ctx.font = `500 17px ${FONT}`;
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.textAlign = 'right';
      ctx.fillText(`/ ${options.totalClauses}`, PAD + CONTENT_W - 16, y + blockH / 2);
      ctx.textAlign = 'left';
    }
    bx += blockW + blockGap;
  }

  // ── Bottom section: ¥ reward (left) | QR (right) ──
  const btmY = headerH + 14;

  // Left side: ¥ amount + text + code
  const leftX = PAD + 8;
  let ly = btmY + 6;

  ctx.font = `800 68px ${FONT}`;
  ctx.fillStyle = '#B07A24';
  ctx.textBaseline = 'top';
  ctx.fillText(`¥${options.discountAmount}`, leftX, ly);
  ly += 84;

  ctx.font = `600 26px ${FONT}`;
  ctx.fillStyle = GOLD_TEXT;
  ctx.textBaseline = 'top';
  incentiveLines.forEach((line, i) => {
    ctx.fillText(line, leftX, ly + i * 34);
  });
  ly += incentiveLines.length * 34 + 22;

  // Referral code inline
  ctx.font = `500 16px ${FONT}`;
  ctx.fillStyle = TEXT_FAINT;
  ctx.fillText(options.labels.referralLabel, leftX, ly);
  ly += 22;
  ctx.font = `700 32px ${FONT}`;
  const codeW = ctx.measureText(options.referralCode).width + 40;
  drawRoundedRect(ctx, leftX, ly, codeW, 52, 26);
  ctx.fillStyle = 'rgba(255,255,255,0.85)';
  ctx.fill();
  ctx.strokeStyle = 'rgba(176,138,74,0.14)';
  ctx.lineWidth = 1;
  drawRoundedRect(ctx, leftX, ly, codeW, 52, 26);
  ctx.stroke();
  ctx.fillStyle = '#B08A4A';
  ctx.textBaseline = 'middle';
  ctx.fillText(options.referralCode, leftX + 20, ly + 27);

  // Right side: QR code + site URL
  const rightCx = W - PAD - 130;
  const qrCy = btmY + 6 + qrSize / 2;
  drawQrCode(ctx, options.shareUrl, rightCx, qrCy, qrSize);

  ctx.textAlign = 'center';
  ctx.font = `600 20px ${FONT}`;
  ctx.fillStyle = TEXT_DARK;
  ctx.textBaseline = 'top';
  ctx.fillText(options.siteUrl.replace(/^https?:\/\//, ''), rightCx, qrCy + qrSize / 2 + 14);
  ctx.textAlign = 'left';

  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error('Canvas toBlob failed'));
    }, 'image/png');
  });
}
