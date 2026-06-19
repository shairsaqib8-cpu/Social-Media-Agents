// Script Optimizer Agent — Frontend

let lastResult = null;

// ── Analyze ────────────────────────────────────────────────────────────────
async function analyze() {
  const script   = document.getElementById('script-input').value.trim();
  const title    = document.getElementById('title-input').value.trim();
  const audience = document.getElementById('audience-input').value.trim();
  const niche    = document.getElementById('niche-input').value.trim();

  if (script.length < 30) { showToast('Please paste your script first.', '#ef4444'); return; }

  document.getElementById('btn-analyze').disabled = true;
  document.getElementById('results').style.display = 'none';
  showLoader(true);

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 90000);
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script, title, audience, niche }),
      signal: controller.signal
    });
    clearTimeout(timer);
    const data = await res.json();
    if (data.error) { showToast('Error: ' + data.error, '#ef4444'); return; }
    lastResult = data;
    renderResults(data);
  } catch (e) {
    if (e.name === 'AbortError') {
      showToast('Analysis timed out — Groq rate limit may be active. Try again in 1 minute.', '#f59e0b');
    } else {
      showToast('Failed to connect to analyzer. Is the server running?', '#ef4444');
    }
  } finally {
    showLoader(false);
    document.getElementById('btn-analyze').disabled = false;
  }
}

// ── Loader ─────────────────────────────────────────────────────────────────
const LOADER_MSGS = [
  ['📡 Parsing script structure…', '🧠 Analyzing hook & storytelling…', '🔍 Scoring 12 dimensions…', '✨ Building your report…'],
];
let loaderTimer;
function showLoader(on) {
  const el = document.getElementById('loader');
  el.classList.toggle('active', on);
  if (on) {
    const steps = ['step-1','step-2','step-3','step-4'];
    let i = 0;
    steps.forEach(s => document.getElementById(s).classList.remove('active'));
    document.getElementById(steps[0]).classList.add('active');
    loaderTimer = setInterval(() => {
      i = Math.min(i + 1, steps.length - 1);
      steps.forEach(s => document.getElementById(s).classList.remove('active'));
      document.getElementById(steps[i]).classList.add('active');
    }, 4000);
  } else {
    clearInterval(loaderTimer);
  }
}

// ── Render all ─────────────────────────────────────────────────────────────
function renderResults(d) {
  renderHero(d);
  renderStats(d);
  renderHook(d);
  renderStory(d);
  renderConnectivity(d);
  renderStyle(d);
  renderEmotional(d);
  renderCritical(d);
  renderRewrite(d);
  renderTitles(d);
  renderVerdict(d);
  document.getElementById('results').style.display = 'block';
  window.scrollTo({ top: document.getElementById('results').offsetTop - 20, behavior: 'smooth' });
}

// ── Score hero ─────────────────────────────────────────────────────────────
function scoreColor(v) {
  if (v >= 75) return '#10b981';
  if (v >= 55) return '#f59e0b';
  if (v >= 35) return '#f97316';
  return '#ef4444';
}
function gradeLabel(v) {
  if (v >= 85) return ['S', '#10b981'];
  if (v >= 70) return ['A', '#10b981'];
  if (v >= 55) return ['B', '#f59e0b'];
  if (v >= 40) return ['C', '#f97316'];
  return ['D', '#ef4444'];
}

const DIM_LABELS = {
  hook_speed:         'Hook Speed',
  second_person:      'Second-Person Voice',
  specificity:        'Specificity',
  sentence_variance:  'Sentence Variety',
  active_voice:       'Active Voice',
  pattern_interrupts: 'Pattern Interrupts',
  open_loops:         'Open Loops',
  power_words:        'Power Words',
  readability:        'Readability',
  callbacks:          'Callbacks',
  cta_quality:        'CTA Quality',
  clarity:            'Clarity',
};

function renderHero(d) {
  const overall = d.overall || 0;
  const color   = scoreColor(overall);
  const [grade, gc] = gradeLabel(overall);
  const circ = 2 * Math.PI * 58;
  const dash  = circ * (1 - overall / 100);

  document.getElementById('ring-fill').style.strokeDasharray  = circ;
  document.getElementById('ring-fill').style.strokeDashoffset = dash;
  document.getElementById('ring-fill').style.stroke           = color;
  document.getElementById('ring-glow').style.strokeDasharray  = circ;
  document.getElementById('ring-glow').style.strokeDashoffset = dash;
  document.getElementById('ring-glow').style.stroke           = color;
  document.getElementById('score-num').textContent  = overall;
  document.getElementById('score-num').style.color  = color;
  const gb = document.getElementById('score-grade');
  gb.textContent = grade; gb.style.background = gc + '22'; gb.style.color = gc;

  const tagEl = document.getElementById('score-tag');
  if (overall >= 75) tagEl.textContent = '🚀 Ready to Perform';
  else if (overall >= 55) tagEl.textContent = '⚠️ Needs Work';
  else tagEl.textContent = '🔴 Major Fixes Required';

  // Breakdown bars
  const grid = document.getElementById('breakdown-grid');
  grid.innerHTML = '';
  const scores = d.scores || {};
  for (const [key, val] of Object.entries(scores)) {
    const pct  = val * 10;
    const col  = scoreColor(pct);
    const label = DIM_LABELS[key] || key;
    grid.innerHTML += `
      <div class="dim-row">
        <div class="dim-label">${label}<span style="color:${col}">${val}/10</span></div>
        <div class="dim-bar-bg"><div class="dim-bar" style="width:${pct}%;background:${col}"></div></div>
      </div>`;
  }
}

// ── Stats strip ─────────────────────────────────────────────────────────────
function renderStats(d) {
  document.getElementById('stat-words').textContent   = d.word_count || '—';
  document.getElementById('stat-duration').textContent = (d.est_duration_min || '—') + ' min';
  document.getElementById('stat-hook').textContent    = d.hook_type || '—';
  document.getElementById('stat-framework').textContent = d.storytelling_framework || '—';
}

// ── Hook ────────────────────────────────────────────────────────────────────
function renderHook(d) {
  const v = document.getElementById('hook-verdict');
  v.textContent = d.hook_verdict || '';
  v.className   = 'verdict-box ' + verdictClass(d.hook_verdict || '');

  // Alternatives
  const types = ['Bold Claim','Question','Scenario','Shocking Statistic','Cold Open'];
  const alts  = d.hook_alternatives || [];
  const list  = document.getElementById('hook-alts');
  list.innerHTML = alts.map((h, i) => `
    <div class="hook-alt" onclick="copyText(this, '${escQ(h)}')">
      <span class="hook-type-label">${types[i] || 'Style ' + (i+1)}</span>
      ${escHtml(h)}
      <span class="copy-tip">click to copy</span>
    </div>`).join('');

  // Rewritten hook
  document.getElementById('hook-rewrite').textContent = d.hook_rewrite || '';
}

// ── Storytelling ────────────────────────────────────────────────────────────
function renderStory(d) {
  const arc = d.arc_breakdown || {};
  const phases = [
    { label:'Setup',      key:'setup',      icon:'🎬', color:'var(--cyan)' },
    { label:'Tension',    key:'tension',    icon:'⚡', color:'var(--orange)' },
    { label:'Resolution', key:'resolution', icon:'🏆', color:'var(--green)' },
  ];
  document.getElementById('arc-row').innerHTML = phases.map(p => `
    <div class="arc-phase">
      <div class="arc-phase-label" style="color:${p.color}">${p.icon} ${p.label}</div>
      <div class="arc-phase-text">${escHtml(arc[p.key] || '—')}</div>
    </div>`).join('');

  document.getElementById('story-verdict').textContent = d.storytelling_verdict || '';
  document.getElementById('emotional-journey').textContent = arc.emotional_journey || '—';
  document.getElementById('arc-fix').textContent = arc.arc_fix || '—';
}

// ── Connectivity ────────────────────────────────────────────────────────────
function renderConnectivity(d) {
  document.getElementById('conn-verdict').textContent = d.connectivity_verdict || '';

  // Weak transitions
  const wt = d.weak_transitions || [];
  const wtEl = document.getElementById('weak-transitions');
  if (wt.length) {
    wtEl.innerHTML = `<table class="compare-table">
      <tr><th class="bad-h">❌ Weak Transition</th><th class="good-h">✅ Replacement</th></tr>
      ${wt.map(r => `<tr><td class="bad">${escHtml(r.location||'')}</td><td class="good">${escHtml(r.fix||'')}</td></tr>`).join('')}
    </table>`;
  } else {
    wtEl.innerHTML = '<p style="color:var(--green);font-size:.85rem;">No weak transitions found.</p>';
  }

  // Open loops
  const loops = d.open_loops_found || [];
  document.getElementById('open-loops-found').innerHTML = loops.length
    ? loops.map(l => `<div class="chip green">${escHtml(l)}</div>`).join('')
    : '<span style="color:var(--muted);font-size:.83rem;">None detected</span>';
  document.getElementById('missing-loop').textContent = d.missing_open_loop || '—';

  // Pattern interrupts
  const pi = d.pattern_interrupts_found || [];
  document.getElementById('pi-found').innerHTML = pi.length
    ? pi.map(p => `<div class="chip cyan">${escHtml(p)}</div>`).join('')
    : '<span style="color:var(--muted);font-size:.83rem;">None detected</span>';
  document.getElementById('missing-pi').textContent = d.missing_interrupt || '—';

  // Re-hook
  const hasReHook = d.re_hook_exists;
  const reHookEl = document.getElementById('rehook-status');
  reHookEl.innerHTML = hasReHook
    ? `<span class="inline-badge badge-green">✓ Present</span>`
    : `<span class="inline-badge badge-red">✗ Missing</span>`;
  document.getElementById('rehook-location').textContent = d.re_hook_location || '—';
  document.getElementById('rehook-fix').textContent      = d.re_hook_fix || '—';
}

// ── Style ───────────────────────────────────────────────────────────────────
function renderStyle(d) {
  document.getElementById('style-verdict').textContent = d.style_verdict || '';
  const issues = d.style_issues || [];
  const el = document.getElementById('style-issues');
  if (issues.length) {
    el.innerHTML = `<table class="compare-table">
      <tr><th class="bad-h">❌ Current</th><th class="good-h">✅ Improved</th></tr>
      ${issues.map(r => `<tr><td class="bad">${escHtml(r.bad||'')}</td><td class="good">${escHtml(r.good||'')}</td></tr>`).join('')}
    </table>`;
  } else {
    el.textContent = 'No major style issues found.';
  }
  document.getElementById('pacing-verdict').textContent = d.pacing_verdict || '';
  const pf = d.pacing_fixes || [];
  document.getElementById('pacing-fixes').innerHTML = pf.map(f => `<div class="bullet-item"><span class="bullet-icon">⚡</span>${escHtml(f)}</div>`).join('');

  const pw = d.power_words_used || [];
  const pm = d.power_words_missing || [];
  document.getElementById('power-used').innerHTML    = pw.map(w => `<span class="chip">${escHtml(w)}</span>`).join('');
  document.getElementById('power-missing').innerHTML = pm.map(w => `<span class="chip yellow">${escHtml(w)}</span>`).join('');

  const specIssues = d.specificity_issues || [];
  const specEl = document.getElementById('spec-issues');
  if (specIssues.length) {
    specEl.innerHTML = `<table class="compare-table">
      <tr><th class="bad-h">❌ Vague</th><th class="good-h">✅ Specific</th></tr>
      ${specIssues.map(r => `<tr><td class="bad">${escHtml(r.vague||'')}</td><td class="good">${escHtml(r.specific||'')}</td></tr>`).join('')}
    </table>`;
  } else {
    specEl.innerHTML = '<p style="color:var(--green);font-size:.85rem;">Good specificity throughout.</p>';
  }
}

// ── Emotional ───────────────────────────────────────────────────────────────
function renderEmotional(d) {
  const score = d.emotional_arc_score || 'Low';
  const badge = { High:'badge-green', Medium:'badge-yellow', Low:'badge-red' }[score] || 'badge-red';
  document.getElementById('emo-score').innerHTML = `<span class="inline-badge ${badge}">${score}</span>`;
  document.getElementById('emo-verdict').textContent = d.emotional_arc_verdict || '';

  const stakes = d.stakes_clarity || 'Missing';
  const sb = { Clear:'badge-green', Weak:'badge-yellow', Missing:'badge-red' }[stakes] || 'badge-red';
  document.getElementById('stakes-badge').innerHTML = `<span class="inline-badge ${sb}">${stakes}</span>`;
  document.getElementById('stakes-fix').textContent = d.stakes_fix || '—';
  document.getElementById('cta-verdict').textContent = d.cta_verdict || '';
  document.getElementById('cta-fix').textContent = d.cta_fix || '—';
}

// ── Critical issues & quick wins ────────────────────────────────────────────
function renderCritical(d) {
  const ci = d.critical_issues || [];
  document.getElementById('critical-list').innerHTML = ci.map(c =>
    `<div class="bullet-item"><span class="bullet-icon">🔴</span>${escHtml(c)}</div>`).join('') || '<p style="color:var(--green)">No critical issues found.</p>';

  const qw = d.quick_wins || [];
  document.getElementById('quickwins-list').innerHTML = qw.map(q =>
    `<div class="bullet-item"><span class="bullet-icon">⚡</span>${escHtml(q)}</div>`).join('');
}

// ── Rewritten script ─────────────────────────────────────────────────────────
function renderRewrite(d) {
  const raw = d.full_rewritten_script || '';
  // Highlight [visual cues] in cyan
  const highlighted = escHtml(raw).replace(/\[([^\]]+)\]/g, '<span class="visual-cue">[$1]</span>');
  document.getElementById('rewrite-content').innerHTML = highlighted;
}

// ── Titles ──────────────────────────────────────────────────────────────────
function renderTitles(d) {
  const titles = d.title_suggestions || [];
  const types  = ['Number/Power Word','Curiosity Gap','Negative Framing','Result-First','Controversy'];
  document.getElementById('titles-list').innerHTML = titles.map((t, i) => `
    <div class="title-item" onclick="copyText(this, '${escQ(t)}')">
      <span class="title-num">${types[i] || i+1}</span>
      <span style="flex:1">${escHtml(t)}</span>
      <span style="font-size:.72rem;color:var(--muted2)">copy</span>
    </div>`).join('');
}

// ── Overall verdict ──────────────────────────────────────────────────────────
function renderVerdict(d) {
  document.getElementById('overall-verdict').textContent = d.overall_verdict || '';
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function verdictClass(text) {
  const t = text.toLowerCase();
  if (t.includes('strong') || t.includes('excellent') || t.includes('great') || t.includes('good')) return 'green';
  if (t.includes('weak') || t.includes('missing') || t.includes('poor') || t.includes('fail')) return 'red';
  return 'yellow';
}

function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escQ(s) {
  return String(s).replace(/'/g, "\\'").replace(/\n/g,' ');
}

function copyText(el, text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('Copied to clipboard!', '#10b981');
  });
}

function showToast(msg, color) {
  const t = document.getElementById('copy-toast');
  t.textContent = msg;
  t.style.color = color || '#10b981';
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2200);
}

// ── Word count ────────────────────────────────────────────────────────────────
document.getElementById('script-input').addEventListener('input', function() {
  const words = this.value.trim().split(/\s+/).filter(Boolean).length;
  const est = Math.round(words / 140 * 10) / 10;
  document.getElementById('char-count').textContent = `${words} words — ~${est} min video`;
});

// ── Animated background ───────────────────────────────────────────────────────
const cv = document.getElementById('bg'), cx = cv.getContext('2d');
let W, H;
const resize = () => { W = cv.width = innerWidth; H = cv.height = innerHeight; };
resize(); addEventListener('resize', resize);
const C = ['#a855f7','#7c3aed','#06b6d4','#10b981'];
const P = Array.from({length:50}, () => ({
  x: Math.random()*2e3, y: Math.random()*1200,
  vx: (Math.random()-.5)*.2, vy: (Math.random()-.5)*.2,
  r: Math.random()*1.6+.6, c: C[Math.floor(Math.random()*C.length)]
}));
(function draw() {
  cx.clearRect(0,0,W,H);
  for (const p of P) {
    p.x = (p.x+p.vx+W)%W; p.y = (p.y+p.vy+H)%H;
    cx.beginPath(); cx.arc(p.x,p.y,p.r,0,Math.PI*2); cx.fillStyle=p.c; cx.fill();
  }
  for (let i=0;i<P.length;i++) for (let j=i+1;j<P.length;j++) {
    const d=Math.hypot(P[i].x-P[j].x,P[i].y-P[j].y);
    if (d<110) { cx.beginPath(); cx.moveTo(P[i].x,P[i].y); cx.lineTo(P[j].x,P[j].y); cx.strokeStyle=`rgba(168,85,247,${.1*(1-d/110)})`; cx.lineWidth=.5; cx.stroke(); }
  }
  requestAnimationFrame(draw);
})();
