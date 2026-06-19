// ── Animated background canvas ───────────────────────────────────────────────
(function () {
  const canvas = document.getElementById('bg-canvas');
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function initParticles() {
    particles = Array.from({length: 55}, () => ({
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 1.5 + 0.3,
      vx: (Math.random() - .5) * .25,
      vy: (Math.random() - .5) * .25,
      alpha: Math.random() * .35 + .05,
      color: Math.random() > .5 ? '108,99,255' : '168,85,247',
    }));
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);

    // gradient orbs
    const orbs = [
      {x: W*.15, y: H*.2, r: 350, c: 'rgba(108,99,255,.07)'},
      {x: W*.85, y: H*.6, r: 280, c: 'rgba(168,85,247,.06)'},
      {x: W*.5, y: H*.9, r: 300, c: 'rgba(255,101,132,.04)'},
    ];
    orbs.forEach(o => {
      const g = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, o.r);
      g.addColorStop(0, o.c);
      g.addColorStop(1, 'transparent');
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(o.x, o.y, o.r, 0, Math.PI * 2);
      ctx.fill();
    });

    // particles + connections
    particles.forEach((p, i) => {
      p.x += p.vx; p.y += p.vy;
      if (p.x < 0) p.x = W; if (p.x > W) p.x = 0;
      if (p.y < 0) p.y = H; if (p.y > H) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${p.color},${p.alpha})`;
      ctx.fill();

      for (let j = i + 1; j < particles.length; j++) {
        const q = particles[j];
        const d = Math.hypot(p.x - q.x, p.y - q.y);
        if (d < 120) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = `rgba(108,99,255,${.06 * (1 - d/120)})`;
          ctx.lineWidth = .5;
          ctx.stroke();
        }
      }
    });
    requestAnimationFrame(draw);
  }

  window.addEventListener('resize', () => { resize(); initParticles(); });
  resize(); initParticles(); draw();
})();

// ── Tab switching ─────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    hideResults();
  });
});

// ── Drag & drop ───────────────────────────────────────────────────────────────
['thumb-zone', 'video-zone', 'post-zone'].forEach(id => {
  const zone = document.getElementById(id);
  if (!zone) return;
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    const inputId = id === 'thumb-zone' ? 'thumb-file' : id === 'post-zone' ? 'post-file' : 'video-file';
    const input = document.getElementById(inputId);
    if (e.dataTransfer.files.length) {
      const dt = new DataTransfer();
      dt.items.add(e.dataTransfer.files[0]);
      input.files = dt.files;
      if (id === 'thumb-zone') previewThumb(input);
      else if (id === 'post-zone') previewPost(input);
      else updateVideoZone(input);
    }
  });
});

function previewThumb(input) {
  const file = input.files[0];
  if (!file) return;
  const img = document.getElementById('thumb-preview');
  img.src = URL.createObjectURL(file);
  document.getElementById('thumb-preview-wrap').style.display = 'flex';
  document.querySelector('#thumb-zone p').textContent = file.name;
}

function updateVideoZone(input) {
  const file = input.files[0];
  if (!file) return;
  document.querySelector('#video-zone p').textContent = '✅ ' + file.name;
}

function previewPost(input) {
  const file = input.files[0];
  if (!file) return;
  const img = document.getElementById('post-preview');
  img.src = URL.createObjectURL(file);
  document.getElementById('post-preview-wrap').style.display = 'flex';
  document.querySelector('#post-zone p').textContent = file.name;
}

// ── Loader ────────────────────────────────────────────────────────────────────
let stepInterval = null;
function showLoader(msg = 'Analyzing your content…') {
  document.getElementById('loader').style.display = 'block';
  document.getElementById('loader-text').textContent = msg;
  document.getElementById('results').style.display = 'none';
  ['step-1','step-2','step-3','step-4'].forEach((id,i) => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('active', i === 0);
  });
  let step = 0;
  stepInterval = setInterval(() => {
    step = (step + 1) % 4;
    ['step-1','step-2','step-3','step-4'].forEach((id, i) => {
      const el = document.getElementById(id);
      if (el) el.classList.toggle('active', i <= step);
    });
  }, 1800);
}

function hideLoader() {
  document.getElementById('loader').style.display = 'none';
  if (stepInterval) { clearInterval(stepInterval); stepInterval = null; }
}

function hideResults() {
  document.getElementById('results').style.display = 'none';
  ['score-card','meta-card','thumb-card','content-card','seo-card','competitor-card','post-card']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
}

function showResults() {
  document.getElementById('results').style.display = 'flex';
  document.getElementById('results').style.flexDirection = 'column';
  document.getElementById('results').style.gap = '20px';
}

// ── Download DOCX report ──────────────────────────────────────────────────────
let _lastAnalysisData = null;

async function downloadReport() {
  if (!_lastAnalysisData) return showError('Run an analysis first.');
  const btn = document.getElementById('download-btn');
  if (btn) { btn.textContent = '⏳ Generating…'; btn.disabled = true; }
  try {
    const res = await fetch('/api/report', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_lastAnalysisData),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Report generation failed');
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const cd = res.headers.get('Content-Disposition') || '';
    const match = cd.match(/filename="?([^"]+)"?/);
    a.download = match ? match[1] : 'virality_report.docx';
    a.href = url;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch(e) { showError(e.message); }
  finally {
    if (btn) { btn.textContent = '📄 Download Report'; btn.disabled = false; }
  }
}

// ── Error toast ───────────────────────────────────────────────────────────────
function showError(msg) {
  hideLoader();
  const toast = document.getElementById('error-toast');
  toast.textContent = '⚠️ ' + msg;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 5000);
}

// ── Score color ───────────────────────────────────────────────────────────────
function scoreColor(s) {
  if (s >= 80) return '#43e97b';
  if (s >= 60) return '#6c63ff';
  if (s >= 40) return '#f9ca24';
  return '#ff4757';
}

function gradeClass(g) {
  const map = {A:'a',B:'b',C:'c',D:'d',F:'f'};
  return map[g?.toUpperCase()] || 'c';
}

function potentialClass(p) {
  if (!p) return 'medium';
  const l = p.toLowerCase();
  if (l.includes('very')) return 'very-high';
  if (l.includes('high')) return 'high';
  if (l.includes('low')) return 'low';
  return 'medium';
}

// ── Render: Score Hero ────────────────────────────────────────────────────────
function renderScoreRing(score, grade, potential, improvement) {
  const card = document.getElementById('score-card');
  card.style.display = 'grid';

  const circumference = 2 * Math.PI * 65; // r=65 → ~408
  const offset = circumference - (score / 100) * circumference;
  const color = scoreColor(score);

  const fill = document.getElementById('ring-fill');
  const glow = document.getElementById('ring-glow');
  fill.style.strokeDasharray = circumference;
  fill.style.strokeDashoffset = offset;
  fill.style.stroke = color;
  glow.style.strokeDasharray = circumference;
  glow.style.strokeDashoffset = offset;
  glow.style.stroke = color;

  document.getElementById('score-num').textContent = score;
  document.getElementById('score-num').style.color = color;

  const gradeEl = document.getElementById('score-grade');
  gradeEl.textContent = 'Grade ' + (grade || '–');
  gradeEl.className = 'score-grade-badge badge ' + gradeClass(grade);

  const vbadge = document.getElementById('viral-badge');
  vbadge.textContent = '🔥 ' + (potential || 'Unknown');
  vbadge.className = 'viral-badge badge ' + potentialClass(potential);

  document.getElementById('improve-text').textContent =
    improvement ? '📈 Est. +' + improvement + ' with optimizations' : '';
}

function renderBreakdown(breakdown) {
  const wrap = document.getElementById('breakdown-bars');
  wrap.innerHTML = '';
  const meta = {
    hook:      { label: 'Hook',      icon: '🎣' },
    story:     { label: 'Story',     icon: '📖' },
    script:    { label: 'Script',    icon: '✍️' },
    audio:     { label: 'Audio',     icon: '🎙️' },
    visual:    { label: 'Visual',    icon: '🎨' },
    editing:   { label: 'Editing',   icon: '✂️' },
    retention: { label: 'Retention', icon: '📈' },
    thumbnail: { label: 'Thumbnail', icon: '🖼️' },
    title:     { label: 'Title',     icon: '📝' },
    virality:  { label: 'Virality',  icon: '🚀' },
    // legacy keys
    hook_strength: { label: 'Hook', icon: '🎣' },
    title_power: { label: 'Title', icon: '📝' },
    seo_strength: { label: 'SEO', icon: '🔍' },
    engagement_signals: { label: 'Engagement', icon: '💬' },
    content_depth: { label: 'Depth', icon: '🧠' },
    visual_quality: { label: 'Visual', icon: '🎨' },
    pacing: { label: 'Pacing', icon: '⚡' },
  };
  Object.entries(breakdown).forEach(([key, val]) => {
    const m = meta[key] || { label: key.replace(/_/g,' '), icon: '📊' };
    if (val === null || val === undefined) {
      // N/A dimension (e.g. thumbnail when no thumbnail uploaded)
      wrap.innerHTML += `
        <div class="mini-bar">
          <div class="mini-bar-top">
            <span class="mini-bar-label">${m.icon} ${m.label}</span>
            <span class="mini-bar-val" style="color:rgba(240,240,255,.3)">N/A</span>
          </div>
          <div class="mini-bar-track">
            <div class="mini-bar-fill" style="width:0%;background:rgba(255,255,255,.1);"></div>
          </div>
          <div style="font-size:.65rem;color:rgba(240,240,255,.3);margin-top:2px;">Not uploaded</div>
        </div>`;
      return;
    }
    // Values are /10 — convert to % for display
    const pct = Math.min(100, Math.max(0, val * 10));
    const color = scoreColor(pct);
    const display = Number.isInteger(val) ? `${val}/10` : val;
    wrap.innerHTML += `
      <div class="mini-bar">
        <div class="mini-bar-top">
          <span class="mini-bar-label">${m.icon} ${m.label}</span>
          <span class="mini-bar-val" style="color:${color}">${display}</span>
        </div>
        <div class="mini-bar-track">
          <div class="mini-bar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
      </div>`;
  });
}

// ── Render: Metadata ──────────────────────────────────────────────────────────
function renderMeta(meta) {
  const card = document.getElementById('meta-card');
  card.style.display = 'block';
  const fmt = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n);

  document.getElementById('meta-content').innerHTML = `
    <div class="video-meta-header">
      ${meta.thumbnail_url ? `<img class="video-thumb" src="${meta.thumbnail_url}" alt="" />` : ''}
      <div class="video-info">
        <div class="video-title">${meta.title}</div>
        <div class="video-channel">📺 ${meta.channel}</div>
      </div>
    </div>
    <div class="stats-grid">
      <div class="stat-chip"><div class="s-val">${fmt(meta.view_count)}</div><div class="s-lbl">Views</div></div>
      <div class="stat-chip"><div class="s-val">${fmt(meta.like_count)}</div><div class="s-lbl">Likes</div></div>
      <div class="stat-chip"><div class="s-val">${fmt(meta.comment_count)}</div><div class="s-lbl">Comments</div></div>
    </div>
    ${meta.tags?.length ? `<div class="tags-cloud">${meta.tags.slice(0,18).map(t=>`<span class="tag">${t}</span>`).join('')}</div>` : ''}
  `;
}

// ── Render: Thumbnail Analysis ────────────────────────────────────────────────
function renderThumbnailAnalysis(data) {
  const card = document.getElementById('thumb-card');
  card.style.display = 'block';
  const el = data.elements || {};
  const checks = [
    ['has_face','Face Visible'],['has_text','Text Present'],['text_readable','Text Readable'],
    ['contrast_strong','Strong Contrast'],['emotion_visible','Emotion Visible'],['brand_consistent','Branded'],
  ];
  const checksHtml = checks.map(([k,label]) =>
    `<div class="check-chip ${el[k]?'pass':'fail'}">${el[k]?'✅':'❌'} ${label}</div>`
  ).join('');

  document.getElementById('thumb-content').innerHTML = `
    <div class="thumb-score-row">
      <div class="thumb-score-num" style="color:${scoreColor(data.score)}">${data.score}</div>
      <div>
        <div style="font-size:1rem;font-weight:700;margin-bottom:6px;">Grade ${data.grade} &nbsp;<span class="badge ${potentialClass(data.ctr_potential)}">${data.ctr_potential} CTR</span></div>
        <div style="font-size:.82rem;color:var(--muted);">Thumbnail score out of 100</div>
      </div>
    </div>
    <div class="checklist-grid">${checksHtml}</div>
    ${data.strengths?.length ? `<div class="sec-title">Strengths</div><div class="tip-list">${data.strengths.map(s=>`<div class="tip-item green">✅ ${s}</div>`).join('')}</div>` : ''}
    ${data.weaknesses?.length ? `<div class="sec-title">Weaknesses</div><div class="tip-list">${data.weaknesses.map(s=>`<div class="tip-item red">⚠️ ${s}</div>`).join('')}</div>` : ''}
    ${data.improvements?.length ? `<div class="sec-title">Improvements</div><div class="tip-list">${data.improvements.map(s=>`<div class="tip-item yellow">💡 ${s}</div>`).join('')}</div>` : ''}
  `;
}

// ── Render: Video Stats Bar ────────────────────────────────────────────────────
function renderVideoStats(stats) {
  if (!stats) return;
  const card = document.getElementById('content-card');
  const existing = document.getElementById('video-stats-bar');
  if (existing) existing.remove();
  const bar = document.createElement('div');
  bar.id = 'video-stats-bar';
  bar.style.cssText = 'display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;padding:14px 16px;background:rgba(108,99,255,.08);border:1px solid rgba(108,99,255,.2);border-radius:12px;';
  const chips = [
    ['🎬', 'Duration', `${stats.duration_sec}s`],
    ['🔍', 'Frames analyzed', stats.frames_analyzed],
    ['✂️', 'Scene cuts', stats.scene_cuts],
    ['⚡', 'Cuts/min', stats.cuts_per_min],
  ];
  bar.innerHTML = chips.map(([ico, lbl, val]) =>
    `<div style="text-align:center;min-width:80px">
       <div style="font-size:1.1rem">${ico}</div>
       <div style="font-size:.95rem;font-weight:700;color:#6c63ff">${val}</div>
       <div style="font-size:.72rem;color:#888;margin-top:2px">${lbl}</div>
     </div>`
  ).join('');
  if (stats.high_risk_moments?.length) {
    bar.innerHTML += `<div style="flex:1;min-width:200px;font-size:.78rem;color:#ff4757;margin-top:4px">
      ⚠️ <b>Drop-off risk:</b> ${stats.high_risk_moments.join(' · ')}
    </div>`;
  }
  card.insertBefore(bar, card.querySelector('#content-content'));
}

// ── Render: Video Watch Report ─────────────────────────────────────────────────
function renderWatchReport(report) {
  if (!report) return '';
  let html = '<div class="sec-title">🎥 Frame-by-Frame Watch Report</div>';

  if (report.av_sync_verdict) {
    const syncColor = report.av_sync_verdict.toLowerCase().includes('poor') ? '#ff4757'
                    : report.av_sync_verdict.toLowerCase().includes('inconsistent') ? '#f9ca24' : '#43e97b';
    html += `<div style="padding:10px 14px;background:rgba(0,0,0,.25);border-left:3px solid ${syncColor};border-radius:8px;margin-bottom:12px;font-size:.83rem">
      <b>Audio-Visual Sync:</b> ${report.av_sync_verdict}
    </div>`;
  }
  if (report.edit_pacing_verdict) {
    html += `<div style="font-size:.83rem;color:#aaa;margin-bottom:12px">✂️ <b>Edit Pacing:</b> ${report.edit_pacing_verdict}</div>`;
  }
  if (report.retention_curve) {
    html += `<div style="font-size:.83rem;color:#f9ca24;margin-bottom:12px">📉 <b>Retention Forecast:</b> ${report.retention_curve}</div>`;
  }
  if (report.segment_verdicts?.length) {
    html += `<div style="font-size:.78rem;color:#888;margin-bottom:6px">SEGMENT ISSUES</div>
    <div class="tip-list">${report.segment_verdicts.map(s =>
      `<div class="tip-item red">🔴 <b>${s.label}:</b> ${s.problem}</div>`
    ).join('')}</div>`;
  }
  return html;
}

// ── Render: Content Analysis ──────────────────────────────────────────────────
function renderContentAnalysis(data) {
  const card = document.getElementById('content-card');
  card.style.display = 'block';
  const ta = data.title_analysis || {};
  const ha = data.hook_analysis || {};
  let html = '';

  // Video stats bar (upload mode only)
  if (data.video_stats) renderVideoStats(data.video_stats);

  // Frame-by-frame watch report
  if (data.video_watch_report) html += renderWatchReport(data.video_watch_report);

  // Executive summary
  if (data.executive_summary) {
    html += `<div class="sec-title">📋 Executive Summary</div>
    <div class="hook-card"><div class="hook-verdict">${data.executive_summary}</div></div>`;
  }

  // Confidence level
  if (data.confidence_level) {
    const cl = data.confidence_level;
    const clr = cl==='High'?'#43e97b':cl==='Medium'?'#f9ca24':'#ff4757';
    html += `<div style="font-size:.8rem;margin-bottom:8px">Confidence: <b style="color:${clr}">${cl}</b></div>`;
  }

  if (data.first_impression) {
    html += `<div class="sec-title">First Impression (0-3 seconds)</div>
    <div class="hook-card"><div class="hook-verdict">${data.first_impression}</div></div>`;
  }

  if (ha.verdict || ha.rewritten_opening) {
    html += `<div class="sec-title">Hook Analysis</div>
    <div class="hook-card">
      ${ha.verdict ? `<div class="hook-verdict">${ha.verdict}</div>` : ''}
      ${ha.what_top_creators_do_instead ? `<div style="font-size:.8rem;color:#888;margin-top:8px">💡 Top creators: ${ha.what_top_creators_do_instead}</div>` : ''}
      ${ha.rewritten_opening ? `<div class="hook-rewrite">📝 Rewritten hook: ${ha.rewritten_opening}</div>` : ''}
    </div>`;
  }

  if (data.audio_analysis) {
    const aa = data.audio_analysis;
    html += `<div class="sec-title">Audio Analysis</div><div class="tip-list">`;
    if (aa.verdict)            html += `<div class="tip-item ${aa.verdict?.toLowerCase().includes('amateur') ? 'red':'cyan'}">🎙️ ${aa.verdict}</div>`;
    if (aa.pacing_verdict)     html += `<div class="tip-item yellow">⚡ ${aa.pacing_verdict}</div>`;
    if (aa.filler_word_problem) html += `<div class="tip-item red">🚨 ${aa.filler_word_problem}</div>`;
    if (aa.audio_visual_sync)  html += `<div class="tip-item ${aa.audio_visual_sync?.toLowerCase().includes('poor') ? 'red':'cyan'}">🔗 Sync: ${aa.audio_visual_sync}</div>`;
    if (aa.script_quality)     html += `<div class="tip-item yellow">📄 ${aa.script_quality}</div>`;
    html += `</div>`;
  }

  // Critical issues with timestamps
  if (data.critical_issues?.length) {
    html += `<div class="sec-title">🚨 Critical Issues</div>`;
    data.critical_issues.forEach(ci => {
      html += `<div style="background:rgba(255,71,87,.08);border:1px solid rgba(255,71,87,.3);border-radius:10px;padding:12px 14px;margin-bottom:10px;">
        <div style="font-weight:700;color:#ff4757;margin-bottom:4px">${ci.issue || ci} ${ci.timestamp ? `<span style="font-size:.75rem;color:#888">@ ${ci.timestamp}</span>` : ''}</div>
        ${ci.why_it_hurts ? `<div style="font-size:.8rem;color:#aaa;margin-bottom:4px">📉 ${ci.why_it_hurts}</div>` : ''}
        ${ci.fix ? `<div style="font-size:.8rem;color:#43e97b">✅ Fix: ${ci.fix}</div>` : ''}
        ${ci.expected_impact ? `<div style="font-size:.78rem;color:#6c63ff;margin-top:3px">📈 Impact: ${ci.expected_impact}</div>` : ''}
      </div>`;
    });
  }

  // Timestamped observations
  if (data.timestamped_observations?.length) {
    html += `<div class="sec-title">⏱ Timestamped Observations</div><div class="tip-list">`;
    data.timestamped_observations.forEach(o => {
      const sev = o.severity || 'ok';
      const clr = sev==='critical'?'red':sev==='warning'?'yellow':'cyan';
      const ico = sev==='critical'?'🔴':sev==='warning'?'🟡':'🟢';
      html += `<div class="tip-item ${clr}">${ico} <b>${o.time||''}:</b> ${o.observation||o}</div>`;
    });
    html += `</div>`;
  }

  // Predictions row
  if (data.ctr_prediction || data.retention_prediction || data.virality_prediction) {
    html += `<div class="sec-title">📊 Predictions</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:12px">`;
    if (data.ctr_prediction) html += `<div style="background:rgba(108,99,255,.1);border:1px solid rgba(108,99,255,.25);border-radius:10px;padding:10px"><div style="font-size:.72rem;color:#888;margin-bottom:4px">CTR PREDICTION</div><div style="font-size:.85rem">${data.ctr_prediction}</div></div>`;
    if (data.retention_prediction) html += `<div style="background:rgba(249,202,36,.08);border:1px solid rgba(249,202,36,.25);border-radius:10px;padding:10px"><div style="font-size:.72rem;color:#888;margin-bottom:4px">RETENTION</div><div style="font-size:.85rem">${data.retention_prediction}</div></div>`;
    if (data.virality_prediction) html += `<div style="background:rgba(67,233,123,.08);border:1px solid rgba(67,233,123,.25);border-radius:10px;padding:10px"><div style="font-size:.72rem;color:#888;margin-bottom:4px">VIRALITY</div><div style="font-size:.85rem">${data.virality_prediction}</div></div>`;
    html += `</div>`;
  }

  if (data.production_issues?.length) {
    html += `<div class="sec-title">Production Issues</div><div class="tip-list">${data.production_issues.map(i=>`<div class="tip-item red">⚠️ ${i}</div>`).join('')}</div>`;
  }

  // Quick wins
  if (data.quick_wins?.length) {
    html += `<div class="sec-title">⚡ Quick Wins</div><div class="tip-list">${data.quick_wins.map(t=>`<div class="tip-item green">✅ ${t}</div>`).join('')}</div>`;
  }

  // High priority fixes
  if (data.high_priority_fixes?.length) {
    html += `<div class="sec-title">🔧 High Priority Fixes</div><div class="tip-list">${data.high_priority_fixes.map(t=>`<div class="tip-item red">🔴 ${t}</div>`).join('')}</div>`;
  }

  // Rewritten hook
  if (data.rewritten_hook) {
    html += `<div class="sec-title">✍️ Rewritten Hook Script</div>
    <div class="hook-card" style="border-color:rgba(67,233,123,.4)">
      <div style="font-size:.75rem;color:#43e97b;font-weight:700;margin-bottom:6px">WORD-FOR-WORD REPLACEMENT</div>
      <div style="font-size:.88rem;line-height:1.6;color:#e0e0e0">${data.rewritten_hook}</div>
    </div>`;
  }

  if (ta.issues?.length) {
    html += `<div class="sec-title">Title Issues</div><div class="tip-list">${ta.issues.map(i=>`<div class="tip-item red">⚠️ ${i}</div>`).join('')}</div>`;
  }

  // 10 Improved Titles
  if (data.ten_improved_titles?.length) {
    html += `<div class="sec-title">🏆 10 Improved Titles</div><div class="alt-titles">`;
    data.ten_improved_titles.forEach((t,i) => {
      html += `<div class="alt-title"><span style="color:#6c63ff;font-weight:700;margin-right:8px">${i+1}.</span>${t}</div>`;
    });
    html += `</div>`;
  } else if (ta.alternative_titles?.length) {
    html += `<div class="sec-title">Alternative Titles</div><div class="alt-titles">${ta.alternative_titles.map(t=>`<div class="alt-title">${t}</div>`).join('')}</div>`;
  }

  // 5 Thumbnail Concepts
  if (data.five_thumbnail_concepts?.length) {
    html += `<div class="sec-title">🖼️ 5 Thumbnail Concepts</div><div class="tip-list">`;
    data.five_thumbnail_concepts.forEach((c,i) => {
      html += `<div class="tip-item cyan" style="padding:10px 14px;margin-bottom:6px"><b style="color:#6c63ff">Concept ${i+1}:</b> ${c}</div>`;
    });
    html += `</div>`;
  }

  // Content team checklist
  if (data.content_team_checklist?.length) {
    html += `<div class="sec-title">📋 Content Team Checklist</div><div class="tip-list">`;
    data.content_team_checklist.forEach(item => {
      html += `<div style="display:flex;align-items:flex-start;gap:10px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05)">
        <input type="checkbox" style="margin-top:3px;accent-color:#6c63ff;flex-shrink:0">
        <span style="font-size:.85rem">${item}</span>
      </div>`;
    });
    html += `</div>`;
  }

  if (data.optimization_tips?.length) {
    html += `<div class="sec-title">Optimization Tips</div><div class="tip-list">${data.optimization_tips.map(t=>`<div class="tip-item cyan">💡 ${t}</div>`).join('')}</div>`;
  }

  // Script line-by-line rewrite table
  if (data.script_line_by_line?.length) {
    html += `<div class="sec-title">✍️ Script Line-by-Line Fixes</div>
    <table class="script-compare-table">
      <thead><tr><th>Original Line</th><th>Problem</th><th>Rewrite</th></tr></thead>
      <tbody>`;
    data.script_line_by_line.forEach(row => {
      html += `<tr>
        <td>${row.original || '—'}</td>
        <td>${row.problem || '—'}</td>
        <td>${row.rewrite || '—'}</td>
      </tr>`;
    });
    html += `</tbody></table>`;
  }

  // Full 60-second rewritten script
  if (data.full_60s_script) {
    html += `<div class="sec-title">🎬 Full 60-Second Rewritten Script</div>
    <button class="copy-script-btn" onclick="copyScript(this)">📋 Copy Script</button>
    <div class="script-60s-box" id="full-script-box">${data.full_60s_script}</div>`;
  }

  // Story Arc visualization
  if (data.story_arc) {
    const arc = data.story_arc;
    const verdictColor = arc.arc_verdict === 'Strong' ? '#43e97b' : arc.arc_verdict === 'Weak' ? '#f9ca24' : '#ff4757';
    html += `<div class="sec-title">📖 Story Arc Analysis &nbsp;<span style="font-size:.78rem;font-weight:700;padding:3px 10px;border-radius:99px;background:rgba(0,0,0,.3);color:${verdictColor};border:1px solid ${verdictColor}40">${arc.arc_verdict || 'Unknown'}</span></div>
    <div class="arc-row">
      <div class="arc-phase setup">
        <div class="arc-phase-label">① Setup (first 20%)</div>
        <div>${arc.phase_1_setup || '—'}</div>
      </div>
      <div class="arc-arrow">→</div>
      <div class="arc-phase tension">
        <div class="arc-phase-label">② Tension</div>
        <div>${arc.phase_2_tension || '—'}</div>
      </div>
      <div class="arc-arrow">→</div>
      <div class="arc-phase resolution">
        <div class="arc-phase-label">③ Resolution</div>
        <div>${arc.phase_3_resolution || '—'}</div>
      </div>
    </div>`;
    if (arc.emotional_peaks?.length) {
      html += `<div style="margin-top:8px;font-size:.8rem;color:var(--muted)">⚡ <b style="color:var(--yellow)">Emotional peaks:</b> ${arc.emotional_peaks.join(' · ')}</div>`;
    }
    if (arc.storytelling_fix) {
      html += `<div style="margin-top:8px;padding:10px 14px;background:rgba(108,99,255,.08);border-left:3px solid var(--primary);border-radius:0 8px 8px 0;font-size:.83rem">
        🔧 <b>Fix:</b> ${arc.storytelling_fix}
      </div>`;
    }
  }

  // Upload Strategy
  if (data.upload_strategy) {
    const us = data.upload_strategy;
    const allDays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
    const bestDays = us.best_days || [];
    html += `<div class="sec-title">📅 Upload Strategy & Metadata</div>
    <div class="upload-strategy-card">
      <div style="margin-bottom:14px">
        <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px">Best Days to Post</div>
        <div class="day-grid">
          ${allDays.map(d => `<div class="day-chip${bestDays.includes(d) ? ' active' : ''}">${d.slice(0,3)}</div>`).join('')}
        </div>
      </div>`;
    if (us.best_time_utc) {
      html += `<div style="margin-bottom:14px">
        <div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px">Best Time (UTC)</div>
        <span class="time-badge">🕐 ${us.best_time_utc} UTC</span>
      </div>`;
    }
    if (us.reasoning) {
      html += `<div style="font-size:.82rem;color:var(--muted);margin-bottom:14px;line-height:1.6">💡 ${us.reasoning}</div>`;
    }
    if (us.metadata_fixes) {
      const mf = us.metadata_fixes;
      html += `<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px">Metadata Fixes</div>`;
      if (mf.title_rewrite) {
        html += `<div style="font-size:.78rem;color:var(--muted);margin-bottom:3px">📝 Rewritten Title:</div>
        <div class="metadata-copyable" title="Click to select all">${mf.title_rewrite}</div>`;
      }
      if (mf.description_first_line) {
        html += `<div style="font-size:.78rem;color:var(--muted);margin-bottom:3px">📄 Description Opening:</div>
        <div class="metadata-copyable" title="Click to select all">${mf.description_first_line}</div>`;
      }
      if (mf.must_add_tags?.length) {
        html += `<div style="font-size:.78rem;color:var(--muted);margin-bottom:6px">🏷 Must-Add Tags:</div>
        <div class="seo-tags">${mf.must_add_tags.map(t=>`<span class="seo-tag">#${t}</span>`).join('')}</div>`;
      }
    }
    if (us.chapter_timestamps?.length) {
      html += `<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:14px 0 8px">Chapter Timestamps</div>
      <div class="chapter-list">
        ${us.chapter_timestamps.map((ch,i) => `<div class="chapter-item">${i+1}. ${ch}</div>`).join('')}
      </div>`;
    }
    html += `</div>`;
  }

  // Final verdict
  if (data.final_verdict) {
    html += `<div class="sec-title">⚖️ Final Verdict</div>
    <div style="background:rgba(255,71,87,.06);border:2px solid rgba(255,71,87,.3);border-radius:12px;padding:16px;font-size:.88rem;line-height:1.6;color:#e0e0e0">${data.final_verdict}</div>`;
  }

  document.getElementById('content-content').innerHTML = html;
}

// ── Copy Script helper ─────────────────────────────────────────────────────────
function copyScript(btn) {
  const box = document.getElementById('full-script-box');
  if (!box) return;
  navigator.clipboard.writeText(box.textContent).then(() => {
    btn.textContent = '✅ Copied!';
    setTimeout(() => { btn.textContent = '📋 Copy Script'; }, 2000);
  }).catch(() => {
    // Fallback: select text
    const range = document.createRange();
    range.selectNodeContents(box);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);
  });
}

// ── Render: SEO ───────────────────────────────────────────────────────────────
function renderSEO(seo) {
  if (!seo) return;
  const card = document.getElementById('seo-card');
  card.style.display = 'block';
  let html = '';

  if (seo.suggested_tags?.length) {
    html += `<div class="sec-title">Suggested Tags</div><div class="seo-tags">${seo.suggested_tags.map(t=>`<span class="seo-tag">#${t}</span>`).join('')}</div>`;
  }
  if (seo.description_tips?.length) {
    html += `<div class="sec-title">Description Tips</div><div class="tip-list">${seo.description_tips.map(t=>`<div class="tip-item">📝 ${t}</div>`).join('')}</div>`;
  }
  if (seo.chapter_suggestion?.length) {
    html += `<div class="sec-title">Chapter Timestamps</div><div class="tip-list">${seo.chapter_suggestion.map(t=>`<div class="tip-item cyan">🕐 ${t}</div>`).join('')}</div>`;
  }

  document.getElementById('seo-content').innerHTML = html;
}

// ── Render: Competitors ───────────────────────────────────────────────────────
function renderCompetitors(analysis, competitors) {
  if (!analysis && !competitors?.length) return;
  const card = document.getElementById('competitor-card');
  card.style.display = 'block';
  let html = '';

  if (analysis?.summary) {
    html += `<div class="insight-box">${analysis.summary}</div>`;
  }
  if (analysis?.insights?.length) {
    html += `<div class="sec-title">Key Insights</div><div class="tip-list">${analysis.insights.map(i=>`<div class="tip-item">🔍 ${i}</div>`).join('')}</div>`;
  }
  if (analysis?.gaps_to_exploit?.length) {
    html += `<div class="sec-title">Gaps to Exploit</div><div class="tip-list">${analysis.gaps_to_exploit.map(g=>`<div class="tip-item green">🎯 ${g}</div>`).join('')}</div>`;
  }
  if (analysis?.positioning_advice) {
    html += `<div class="sec-title">Positioning Strategy</div><div class="positioning-box">🧭 ${analysis.positioning_advice}</div>`;
  }
  if (competitors?.length) {
    html += `<div class="sec-title">Top Competing Videos This Week</div><div class="comp-list">`;
    competitors.forEach((c, i) => {
      const fmt = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n||0);
      const pubDate = c.published_at ? new Date(c.published_at).toLocaleDateString() : '';
      html += `<div class="comp-item">
        <div class="comp-num">${i+1}</div>
        ${c.thumbnail ? `<img class="comp-thumb" src="${c.thumbnail}" alt="" />` : ''}
        <div style="min-width:0;flex:1">
          <div class="comp-title">${c.title}</div>
          <div class="comp-channel">📺 ${c.channel}</div>
          ${c.view_count ? `<div class="comp-views">👁 ${fmt(c.view_count)} views${pubDate ? ' · ' + pubDate : ''}</div>` : ''}
          ${c.youtube_url ? `<a class="comp-watch-link" href="${c.youtube_url}" target="_blank" rel="noopener noreferrer">▶ Watch on YouTube</a>` : ''}
        </div>
      </div>`;
    });
    html += '</div>';
  }

  document.getElementById('competitor-content').innerHTML = html;
}

// ── Show download button ───────────────────────────────────────────────────────
function showDownloadBtn() {
  const bar = document.getElementById('download-bar');
  if (bar) bar.style.display = 'block';
  const btn = document.getElementById('download-btn');
  if (btn) { btn.textContent = '📄 Download Full Report (DOCX)'; btn.disabled = false; }
}

// ── API calls ─────────────────────────────────────────────────────────────────
async function analyzeURL() {
  const url = document.getElementById('yt-url').value.trim();
  if (!url) return showError('Please enter a YouTube URL.');
  showLoader('Fetching YouTube data…');
  try {
    const res = await fetch('/api/analyze-url', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url}),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Analysis failed');
    _lastAnalysisData = data;
    hideLoader(); showResults();
    const ca = data.content_analysis || {};
    renderScoreRing(ca.virality_score, ca.grade, ca.viral_potential, ca.estimated_improvement);
    if (ca.breakdown) renderBreakdown(ca.breakdown);
    if (data.metadata) renderMeta(data.metadata);
    renderContentAnalysis(ca);
    if (ca.seo_recommendations) renderSEO(ca.seo_recommendations);
    renderCompetitors(data.competitor_analysis, data.competitors);
    showDownloadBtn();
    document.getElementById('score-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
}

async function analyzeThumbnail() {
  const file = document.getElementById('thumb-file').files[0];
  if (!file) return showError('Please select a thumbnail image first.');
  showLoader('Analyzing thumbnail with Vision AI…');
  try {
    const fd = new FormData(); fd.append('file', file);
    const res = await fetch('/api/analyze-thumbnail', {method:'POST', body:fd});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Thumbnail analysis failed');
    hideLoader(); showResults();
    const ta = data.thumbnail_analysis;
    _lastAnalysisData = data;
    // Clear stale breakdown bars from any previous URL/video analysis
    document.getElementById('breakdown-bars').innerHTML = '';
    renderScoreRing(ta.score, ta.grade, ta.ctr_potential + ' CTR', null);
    renderThumbnailAnalysis(ta);
    // Hide content/competitor cards that don't apply to thumbnail-only
    ['content-card','seo-card','competitor-card','meta-card'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
    showDownloadBtn();
    document.getElementById('score-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
}

async function analyzeVideo() {
  const file = document.getElementById('video-file').files[0];
  if (!file) return showError('Please select a video file first.');
  showLoader('Uploading & extracting hook frame…');
  try {
    const fd = new FormData(); fd.append('file', file);
    const res = await fetch('/api/analyze-video', {method:'POST', body:fd});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Video analysis failed');
    hideLoader(); showResults();
    _lastAnalysisData = data;
    const va = data.video_analysis;
    renderScoreRing(va.virality_score, va.grade, va.viral_potential, va.estimated_improvement);
    if (va.breakdown) renderBreakdown(va.breakdown);
    renderContentAnalysis(va);
    showDownloadBtn();
    document.getElementById('score-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
}

async function analyzePostTiming() {
  const file = document.getElementById('post-file').files[0];
  if (!file) return showError('Please select an Analytics screenshot first.');
  showLoader('Reading your YouTube Analytics screenshot…');
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/analyze-post-timing', {method:'POST', body:fd});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Post timing analysis failed');
    _lastAnalysisData = data;
    hideLoader(); showResults();
    // Hide cards not relevant to post timing
    ['score-card','meta-card','thumb-card','content-card','seo-card','competitor-card']
      .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
    renderPostTiming(data.timing_analysis);
    showDownloadBtn();
    document.getElementById('post-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
}

function renderPostTiming(data) {
  if (!data) return;
  const card = document.getElementById('post-card');
  card.style.display = 'block';

  const allDays = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  const bestDays = data.best_days || [];
  const bestTimes = data.best_times_utc || [];

  let html = `
    <div class="sec-title">📅 Best Days to Post</div>
    <div class="day-grid">
      ${allDays.map(d => `<div class="day-chip${bestDays.includes(d) ? ' active' : ''}">${d.slice(0,3)}</div>`).join('')}
    </div>`;

  if (bestTimes.length) {
    html += `<div class="sec-title">🕐 Best Times (UTC)</div>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:14px">
      ${bestTimes.map(t => `<span class="time-badge">🕐 ${t} UTC</span>`).join('')}
    </div>`;
  }

  if (data.audience_peak_hours) {
    html += `<div class="sec-title">📊 What Your Analytics Shows</div>
    <div class="hook-card"><div class="hook-verdict">${data.audience_peak_hours}</div></div>`;
  }

  if (data.reasoning) {
    html += `<div class="sec-title">💡 Why These Times</div>
    <div style="font-size:.88rem;line-height:1.65;color:rgba(240,240,255,.8);padding:12px 16px;background:rgba(108,99,255,.06);border-radius:10px;border:1px solid rgba(108,99,255,.15)">${data.reasoning}</div>`;
  }

  if (data.posting_plan) {
    html += `<div class="sec-title">📋 Posting Plan</div>
    <div style="font-size:.88rem;line-height:1.7;color:rgba(240,240,255,.85);padding:14px 18px;background:rgba(0,0,0,.25);border-radius:10px;border:1px solid var(--border);white-space:pre-wrap">${data.posting_plan}</div>`;
  }

  if (data.title_tips) {
    html += `<div class="sec-title">📝 Title Tips for Your Niche</div>
    <div class="tip-item cyan" style="margin-bottom:8px">💡 ${data.title_tips}</div>`;
  }

  if (data.description_tips) {
    html += `<div class="sec-title">📄 Description SEO Tips</div>
    <div class="tip-item green">✅ ${data.description_tips}</div>`;
  }

  if (data.tag_suggestions?.length) {
    html += `<div class="sec-title">🏷 Suggested Tags</div>
    <div class="seo-tags">${data.tag_suggestions.map(t => `<span class="seo-tag">#${t}</span>`).join('')}</div>`;
  }

  card.querySelector('#post-content').innerHTML = html;
}

async function analyzeFull() {
  const url = document.getElementById('full-url').value.trim();
  const thumbFile = document.getElementById('full-thumb').files[0];
  if (!url && !thumbFile) return showError('Provide a YouTube URL or a thumbnail.');
  showLoader('Running full analysis…');
  try {
    const fd = new FormData();
    if (url) fd.append('url', url);
    if (thumbFile) fd.append('thumbnail', thumbFile);
    const res = await fetch('/api/analyze-full', {method:'POST', body:fd});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Full analysis failed');
    _lastAnalysisData = data;
    hideLoader(); showResults();
    const ca = data.content_analysis || {};
    if (ca.virality_score != null)
      renderScoreRing(ca.virality_score, ca.grade, ca.viral_potential, ca.estimated_improvement);
    if (ca.breakdown) renderBreakdown(ca.breakdown);
    if (data.metadata) renderMeta(data.metadata);
    if (data.thumbnail_analysis) renderThumbnailAnalysis(data.thumbnail_analysis);
    if (Object.keys(ca).length) renderContentAnalysis(ca);
    if (ca.seo_recommendations) renderSEO(ca.seo_recommendations);
    renderCompetitors(data.competitor_analysis, data.competitors);
    showDownloadBtn();
    document.getElementById('score-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
}
