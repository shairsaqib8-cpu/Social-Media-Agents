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
['thumb-zone', 'video-zone'].forEach(id => {
  const zone = document.getElementById(id);
  if (!zone) return;
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('drag-over');
    const inputId = id === 'thumb-zone' ? 'thumb-file' : 'video-file';
    const input = document.getElementById(inputId);
    if (e.dataTransfer.files.length) {
      const dt = new DataTransfer();
      dt.items.add(e.dataTransfer.files[0]);
      input.files = dt.files;
      if (id === 'thumb-zone') previewThumb(input);
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
  ['score-card','meta-card','thumb-card','content-card','seo-card','competitor-card']
    .forEach(id => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
}

function showResults() {
  document.getElementById('results').style.display = 'flex';
  document.getElementById('results').style.flexDirection = 'column';
  document.getElementById('results').style.gap = '20px';
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
  const labels = {
    hook_strength: 'Hook', title_power: 'Title', seo_strength: 'SEO',
    engagement_signals: 'Engagement', content_depth: 'Depth',
    visual_quality: 'Visual', pacing: 'Pacing',
  };
  Object.entries(breakdown).forEach(([key, val]) => {
    const label = labels[key] || key.replace(/_/g,' ');
    const color = scoreColor(val);
    wrap.innerHTML += `
      <div class="mini-bar">
        <div class="mini-bar-top">
          <span class="mini-bar-label">${label}</span>
          <span class="mini-bar-val" style="color:${color}">${val}</span>
        </div>
        <div class="mini-bar-track">
          <div class="mini-bar-fill" style="width:${val}%;background:${color}"></div>
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

// ── Render: Content Analysis ──────────────────────────────────────────────────
function renderContentAnalysis(data) {
  const card = document.getElementById('content-card');
  card.style.display = 'block';
  const ta = data.title_analysis || {};
  const ha = data.hook_analysis || {};
  let html = '';

  if (ha.verdict || ha.first_line) {
    html += `<div class="sec-title">Hook Analysis</div>
    <div class="hook-card">
      ${ha.first_line ? `<div class="hook-quote">"${ha.first_line}"</div>` : ''}
      ${ha.verdict ? `<div class="hook-verdict">${ha.verdict}</div>` : ''}
      ${ha.rewrite ? `<div class="hook-rewrite">💡 Suggested rewrite: ${ha.rewrite}</div>` : ''}
    </div>`;
  }
  if (ta.issues?.length) {
    html += `<div class="sec-title">Title Issues</div><div class="tip-list">${ta.issues.map(i=>`<div class="tip-item red">⚠️ ${i}</div>`).join('')}</div>`;
  }
  if (ta.alternative_titles?.length) {
    html += `<div class="sec-title">Alternative Titles</div><div class="alt-titles">${ta.alternative_titles.map(t=>`<div class="alt-title">${t}</div>`).join('')}</div>`;
  }
  if (data.optimization_tips?.length) {
    html += `<div class="sec-title">Optimization Tips</div><div class="tip-list">${data.optimization_tips.map(t=>`<div class="tip-item cyan">💡 ${t}</div>`).join('')}</div>`;
  }

  document.getElementById('content-content').innerHTML = html;
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
    html += `<div class="sec-title">Top Competing Videos</div><div class="comp-list">`;
    competitors.forEach((c, i) => {
      html += `<div class="comp-item">
        <div class="comp-num">${i+1}</div>
        ${c.thumbnail ? `<img class="comp-thumb" src="${c.thumbnail}" alt="" />` : ''}
        <div><div class="comp-title">${c.title}</div><div class="comp-channel">📺 ${c.channel}</div></div>
      </div>`;
    });
    html += '</div>';
  }

  document.getElementById('competitor-content').innerHTML = html;
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
    hideLoader(); showResults();
    const ca = data.content_analysis || {};
    renderScoreRing(ca.virality_score, ca.grade, ca.viral_potential, ca.estimated_improvement);
    if (ca.breakdown) renderBreakdown(ca.breakdown);
    if (data.metadata) renderMeta(data.metadata);
    renderContentAnalysis(ca);
    if (ca.seo_recommendations) renderSEO(ca.seo_recommendations);
    renderCompetitors(data.competitor_analysis, data.competitors);
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
    // Clear stale breakdown bars from any previous URL/video analysis
    document.getElementById('breakdown-bars').innerHTML = '';
    renderScoreRing(ta.score, ta.grade, ta.ctr_potential + ' CTR', null);
    renderThumbnailAnalysis(ta);
    // Hide content/competitor cards that don't apply to thumbnail-only
    ['content-card','seo-card','competitor-card','meta-card'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
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
    const va = data.video_analysis;
    renderScoreRing(va.virality_score, va.grade, va.viral_potential, va.estimated_improvement);
    if (va.breakdown) renderBreakdown(va.breakdown);
    renderContentAnalysis(va);
    document.getElementById('score-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
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
    document.getElementById('score-card').scrollIntoView({behavior:'smooth', block:'start'});
  } catch(e) { showError(e.message); }
}
