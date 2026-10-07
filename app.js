// SEO Agent OS — Mission Control (données réelles via API backend)

// ========== ÉTAT ==========
const state = { sites: [], articles: [], stats: { sites: 0, articles: 0, published: 0 } };

// ========== API ==========
async function apiGet(path) { return (await fetch(path)).json(); }
async function apiPost(path, body, method = 'POST') {
    return (await fetch(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json();
}

// ========== NAVIGATION ==========
const pageTitles = {
    dashboard: 'Mission Control',
    articles: 'Articles',
    sites: 'Sites & Connexions',
    agents: 'Agents',
};
document.querySelectorAll('.nav-item[data-page]').forEach(item => {
    item.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        this.classList.add('active');
        const page = this.dataset.page;
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const target = document.getElementById(page + '-page');
        if (target) target.classList.add('active');
        document.getElementById('page-title').textContent = pageTitles[page] || page;
        refresh(page);
    });
});

function refresh(page) {
    if (page === 'sites') loadSites();
    if (page === 'articles') loadArticles();
    if (page === 'dashboard') loadDashboard();
}

// ========== DASHBOARD ==========
async function loadDashboard() {
    const s = await apiGet('/api/stats');
    if (!s.ok) return;
    state.stats = s;
    document.getElementById('statArticles').textContent = s.articles;
    document.getElementById('statSites').textContent = s.sites;
    document.getElementById('statPublished').textContent = s.published;
    document.getElementById('statDrafts').textContent = s.articles - s.published;

    const data = await apiGet('/api/articles');
    if (!data.ok) return;
    state.articles = data.articles;
    const list = document.getElementById('recentArticles');
    if (!data.articles.length) {
        list.innerHTML = '<p style="color:var(--text-muted); font-size:14px;">Aucun article pour l\'instant. Connectez un site puis créez un article.</p>';
        return;
    }
    list.innerHTML = data.articles.slice(0, 6).map(a => articleCardHTML(a)).join('');
    initTilt();
}

function articleCardHTML(a) {
    const status = a.status === 'publish' ? '<span class="article-status optimized">Publié</span>' : '<span class="article-status in-progress">Brouillon</span>';
    return `
    <div class="article-card tilt">
        ${status}
        <h4>${esc(a.title)}</h4>
        <div class="article-meta">
            <span>📅 ${(a.created_at || '').slice(0, 10)}</span>
            <span>🌐 ${esc(a.site_name || '—')}</span>
            <span>${a.wp_post_id ? '🔗 WP #' + a.wp_post_id : '📝 Local'}</span>
        </div>
        <div class="article-actions">
            ${a.wp_post_id ? `<button class="btn-small" onclick="window.open('${a.site_url}/?p=${a.wp_post_id}')">Voir</button>` : ''}
            <button class="btn-small secondary" onclick="viewArticle(${a.id})">Aperçu</button>
        </div>
    </div>`;
}

async function viewArticle(id) {
    const a = state.articles.find(x => x.id === id);
    if (!a) return;
    const w = window.open('', '_blank');
    w.document.write(`<html><head><title>${esc(a.title)}</title><meta charset="utf-8"><style>body{font-family:Inter,sans-serif;max-width:720px;margin:40px auto;padding:0 20px;color:#111}h1{font-size:26px}h2{margin-top:28px}p{line-height:1.7}</style></head><body><h1>${esc(a.title)}</h1>${a.content.replace(/\n/g, '<br>')}</body></html>`);
    w.document.close();
}

function esc(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ========== ARTICLES PAGE ==========
async function loadArticles() {
    const data = await apiGet('/api/articles');
    if (!data.ok) return;
    state.articles = data.articles;
    renderArticlesTable(state.articles);
}

function renderArticlesTable(articles) {
    const tbody = document.getElementById('articlesBody');
    if (!articles.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted);">Aucun article.</td></tr>';
        return;
    }
    tbody.innerHTML = articles.map(a => `
        <tr>
            <td>${esc(a.title)}</td>
            <td><span class="badge ${a.status === 'publish' ? 'success' : 'warning'}">${a.status === 'publish' ? 'Publié' : 'Brouillon'}</span></td>
            <td>${a.wp_post_id ? '<span class="badge success">#' + a.wp_post_id + '</span>' : '—'}</td>
            <td>${esc(a.site_name || '—')}</td>
            <td>${(a.created_at || '').slice(0, 10)}</td>
            <td>
                ${a.wp_post_id ? `<button class="btn-icon" title="Voir" onclick="window.open('${a.site_url}/?p=${a.wp_post_id}')">👁️</button>` : ''}
                <button class="btn-icon" title="Aperçu" onclick="viewArticle(${a.id})">📄</button>
                <button class="btn-icon" title="Supprimer" onclick="deleteArticle(${a.id})">🗑️</button>
            </td>
        </tr>`).join('');
}

function filterArticles(q) {
    const status = document.getElementById('statusFilter').value;
    const filtered = state.articles.filter(a =>
        (!q || a.title.toLowerCase().includes(q.toLowerCase())) &&
        (!status || a.status === status));
    renderArticlesTable(filtered);
}

async function deleteArticle(id) {
    if (!confirm('Supprimer cet article (local uniquement) ?')) return;
    await apiPost(`/api/articles/${id}`, {}, 'DELETE');
    loadArticles();
}

// ========== SITES PAGE ==========
async function loadSites() {
    const data = await apiGet('/api/sites');
    const grid = document.getElementById('sitesGrid');
    if (!data.ok) { grid.innerHTML = '<p>Erreur de chargement.</p>'; return; }
    state.sites = data.sites;
    if (!data.sites.length) {
        grid.innerHTML = '<p style="color:var(--text-muted);">Aucun site. Cliquez sur « Ajouter un site ».</p>';
        return;
    }
    grid.innerHTML = data.sites.map(s => `
        <div class="site-card tilt">
            <h3>${esc(s.name)}</h3>
            <p style="color:var(--text-muted);font-size:12.5px;">${esc(s.url)}</p>
            <p style="margin-top:10px;">WordPress : <span class="badge ${s.wp_status === 'connected' ? 'success' : 'warning'}">${s.wp_status === 'connected' ? 'Connecté' : s.wp_status === 'no-credentials' ? 'Identifiants manquants' : esc(s.wp_status)}</span></p>
            <p style="font-size:12px;color:var(--text-muted);margin-top:8px;">GSC : ${esc(s.gsc_property || '—')} · Bing : ${esc(s.bing_site || '—')}</p>
            <div style="margin-top:14px; display:flex; gap:8px;">
                <button class="btn-secondary" onclick="testSite(${s.id})">Tester connexion</button>
                <button class="btn-secondary" style="border-color:rgba(239,68,68,.3);color:#ef4444;" onclick="deleteSite(${s.id})">Supprimer</button>
            </div>
        </div>`).join('');
    initTilt();
}

async function addSite() {
    const body = {
        name: document.getElementById('siteName').value,
        url: document.getElementById('siteUrl').value,
        wp_user: document.getElementById('siteUser').value,
        wp_app_password: document.getElementById('sitePass').value,
        gsc_property: document.getElementById('siteGsc').value,
        bing_site: document.getElementById('siteBing').value,
    };
    if (!body.name || !body.url) { alert('Nom et URL obligatoires'); return; }
    await apiPost('/api/sites', body);
    closeModal('addSiteModal');
    loadSites();
}

async function testSite(id) {
    const res = await apiPost(`/api/sites/${id}/test`, {});
    alert(res.ok ? `✅ Connecté en tant que ${res.user}` : `❌ Erreur : ${res.error || res.status}`);
    loadSites();
}

async function deleteSite(id) {
    if (!confirm('Supprimer ce site ?')) return;
    await apiPost(`/api/sites/${id}`, {}, 'DELETE');
    loadSites();
}

// ========== CONNEXIONS API ==========
async function loadKeyStatus() {
    const k = await apiGet('/api/keys');
    if (!k.ok) return;
    const g = document.getElementById('gscStatus'), b = document.getElementById('bingStatus');
    if (g) g.innerHTML = k.gsc_configured ? '<span style="color:var(--accent-green);">● Clé enregistrée</span>' : '<span style="color:var(--accent-orange);">● Non configurée</span>';
    if (b) b.innerHTML = k.bing_configured ? '<span style="color:var(--accent-green);">● Clé enregistrée</span>' : '<span style="color:var(--accent-orange);">● Non configurée</span>';
}

async function importGSCKey(input) {
    const file = input.files[0];
    if (!file) return;
    const text = await file.text();
    try {
        JSON.parse(text); // valider que c'est du JSON
    } catch (e) { alert('Fichier invalide : ce n\'est pas du JSON.'); return; }
    await apiPost('/api/keys', { gsc_service_account: text });
    input.value = '';
    loadKeyStatus();
    alert('✅ Clé GSC enregistrée dans api_keys.json');
}

async function configureGSC() {
    const key = prompt('Collez le contenu JSON de votre clé de compte de service Google :');
    if (!key) return;
    await apiPost('/api/keys', { gsc_service_account: key });
    loadKeyStatus();
}
async function configureBing() {
    const key = prompt('Collez votre clé API Bing Webmaster (ipt_...) :');
    if (!key) return;
    await apiPost('/api/keys', { bing_api_key: key });
    loadKeyStatus();
}

// ========== MODAL ==========
function showAddSiteModal() { document.getElementById('addSiteModal').classList.add('active'); }
function closeModal(id) { document.getElementById(id).classList.remove('active'); }
document.querySelectorAll('.modal').forEach(m => m.addEventListener('click', e => { if (e.target === m) m.classList.remove('active'); }));

// ========== EFFET 3D TILT ==========
function initTilt() {
    document.querySelectorAll('.tilt').forEach(card => {
        if (card._tiltBound) return;
        card._tiltBound = true;
        card.addEventListener('mousemove', e => {
            const r = card.getBoundingClientRect();
            const x = (e.clientX - r.left) / r.width - 0.5;
            const y = (e.clientY - r.top) / r.height - 0.5;
            card.style.transform = `perspective(800px) rotateY(${x * 8}deg) rotateX(${-y * 8}deg) translateY(-3px) scale(1.015)`;
        });
        card.addEventListener('mouseleave', () => { card.style.transform = ''; });
    });
}

// ========== BOOT ==========
document.addEventListener('DOMContentLoaded', async function () {
    loadDashboard();
    loadKeyStatus();
    initTilt();
    initParticles();
    console.log('SEO Agent OS — Mission Control prêt.');
});

// ========== ANIMATIONS « BLOW FLOW » ==========
function initParticles() {
    const canvas = document.createElement('canvas');
    canvas.id = 'bgParticles';
    document.body.prepend(canvas);
    const ctx = canvas.getContext('2d');
    let W, H, particles = [];
    const COLORS = ['139,92,246', '59,130,246', '16,185,129'];

    function resize() { W = canvas.width = innerWidth; H = canvas.height = innerHeight; }
    resize();
    addEventListener('resize', resize);

    for (let i = 0; i < 45; i++) {
        particles.push({
            x: Math.random() * W, y: Math.random() * H,
            r: Math.random() * 2 + 0.6,
            vx: (Math.random() - .5) * .25, vy: (Math.random() - .5) * .25,
            c: COLORS[i % 3], a: Math.random() * .4 + .15,
            pulse: Math.random() * Math.PI * 2,
        });
    }

    (function draw() {
        ctx.clearRect(0, 0, W, H);
        // liaisons entre particules proches
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            p.x += p.vx; p.y += p.vy;
            if (p.x < 0 || p.x > W) p.vx *= -1;
            if (p.y < 0 || p.y > H) p.vy *= -1;
            p.pulse += .02;
            for (let j = i + 1; j < particles.length; j++) {
                const q = particles[j];
                const d = Math.hypot(p.x - q.x, p.y - q.y);
                if (d < 130) {
                    ctx.strokeStyle = `rgba(${p.c},${(1 - d / 130) * .08})`;
                    ctx.lineWidth = 1;
                    ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
                }
            }
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r + Math.sin(p.pulse) * .4, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${p.c},${p.a + Math.sin(p.pulse) * .1})`;
            ctx.fill();
        }
        requestAnimationFrame(draw);
    })();
}
