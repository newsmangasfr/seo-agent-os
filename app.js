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
    studio: 'Studio IA — Création de contenu',
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
    if (page === 'studio') loadStudio();
}

// ========== STUDIO IA ==========
function studioPayload() {
    return {
        site_id: parseInt(document.getElementById('studioSite').value),
        topic: document.getElementById('studioTopic').value.trim(),
        keywords: document.getElementById('studioKeywords').value.trim(),
        length: document.getElementById('studioLength').value,
        custom_instructions: document.getElementById('studioCustom').value.trim(),
        research: document.getElementById('studioResearch').checked,
    };
}

async function loadStudio() {
    // peupler le select des sites
    const data = await apiGet('/api/sites');
    if (data.ok) {
        const sel = document.getElementById('studioSite');
        sel.innerHTML = data.sites.map(s =>
            `<option value="${s.id}">${esc(s.name)} — ${esc(s.url)}</option>`).join('');
    }
    // statut providers
    const st = await apiGet('/api/content/status');
    if (st.ok) {
        const or = document.getElementById('openrouterStatus'), bp = document.getElementById('beatapiStatus');
        or.innerHTML = st.openrouter_configured
            ? '<span style="color:var(--accent-green);">● Configuré — ' + st.openrouter_free_models_count + ' modèles gratuits dispo</span>'
            : '<span style="color:var(--accent-orange);">● Non configuré</span>';
        bp.innerHTML = st.beatapi_configured
            ? '<span style="color:var(--accent-green);">● Configuré</span>'
            : '<span style="color:var(--text-muted);">● Non configuré (mode dégradé)</span>';
    }
}

function studioRender(art, extra) {
    const meta = extra || {};
    const p = document.getElementById('studioPreview');
    p.innerHTML = `
        <div class="studio-result">
            <div class="studio-result-head">
                <h3>${esc(art.title)}</h3>
                <div class="studio-badges">
                    <span class="badge success">SEO : ${esc(art.seo_title || '—')}</span>
                    ${meta.model ? `<span class="badge">${esc(meta.model)}</span>` : ''}
                    ${meta.research_used ? '<span class="badge success">🌐 sources web</span>' : ''}
                </div>
            </div>
            <p class="studio-meta-desc"><strong>Meta description :</strong> ${esc(art.meta_description || '')}</p>
            <div class="studio-content">${mdToHtml(art.content || '')}</div>
            <div class="studio-links">
                <strong>Liens internes suggérés :</strong>
                ${(art.internal_links || []).length ? art.internal_links.map(u => `<div class="mono">${esc(u)}</div>`).join('') : '<em>aucun</em>'}
            </div>
        </div>`;
}

function mdToHtml(md) {
    return esc(md)
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/^/, '<p>').replace(/$/, '</p>');
}

function studioBusy(label) {
    document.getElementById('studioPreview').innerHTML =
        `<div class="studio-placeholder"><div class="spinner"></div><p>${label}…</p></div>`;
}

async function studioGenerate() {
    const payload = studioPayload();
    if (!payload.site_id || !payload.topic) { alert('Site et sujet obligatoires'); return; }
    studioBusy('Génération IA en cours (30-90 s selon le modèle)');
    const res = await apiPost('/api/content/generate', payload);
    if (res.ok) {
        studioRender(res.article, { model: res.model, research_used: res.research_used });
    } else {
        document.getElementById('studioPreview').innerHTML =
            `<div class="studio-placeholder" style="color:#ef4444">❌ ${esc(res.error)}</div>`;
    }
}

async function studioDraft() {
    const payload = studioPayload();
    if (!payload.site_id || !payload.topic) { alert('Site et sujet obligatoires'); return; }
    studioBusy('Génération + enregistrement du brouillon…');
    const res = await apiPost('/api/content/draft', payload);
    if (res.ok) {
        studioRender(res.article, { model: res.model });
        alert('✅ Brouillon enregistré (article #' + res.article_id + ')');
    } else {
        document.getElementById('studioPreview').innerHTML =
            `<div class="studio-placeholder" style="color:#ef4444">❌ ${esc(res.error)}</div>`;
    }
}

async function studioPublish(publishNow) {
    if (publishNow && !confirm('Publier EN LIGNE sur WordPress ?')) return;
    const payload = { ...studioPayload(), publish_now: publishNow };
    if (!payload.site_id || !payload.topic) { alert('Site et sujet obligatoires'); return; }
    studioBusy(publishNow ? 'Génération + publication en ligne…' : 'Génération + envoi brouillon WP…');
    const res = await apiPost('/api/content/publish', payload);
    if (res.ok) {
        alert('✅ Publié — ' + (res.wp_link || 'WP #' + res.wp_id));
        document.getElementById('studioPreview').innerHTML =
            `<div class="studio-placeholder" style="color:var(--accent-green)">✅ Publié sur WordPress<br><a href="${esc(res.wp_link)}" target="_blank">${esc(res.wp_link)}</a></div>`;
    } else {
        document.getElementById('studioPreview').innerHTML =
            `<div class="studio-placeholder" style="color:#ef4444">❌ ${esc(res.error)}</div>`;
    }
}

async function configureOpenRouter() {
    const key = prompt('Colle ta clé OpenRouter (sk-or-...) :');
    if (!key) return;
    await apiPost('/api/keys', { openrouter: key });
    loadStudio();
}
async function configureBeatAPI() {
    const key = prompt('Colle ta clé BeatAPI :');
    if (!key) return;
    await apiPost('/api/keys', { beatapi: key });
    loadStudio();
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

// ========== EFFET 3D TILT (rotation souris + glow violet) ==========
function initTilt() {
    document.querySelectorAll('.tilt').forEach(card => {
        if (card._tiltBound) return;
        card._tiltBound = true;
        card.addEventListener('mousemove', e => {
            const r = card.getBoundingClientRect();
            const x = (e.clientX - r.left) / r.width - 0.5;
            const y = (e.clientY - r.top) / r.height - 0.5;
            card.style.transform =
                `perspective(900px) rotateY(${x * 10}deg) rotateX(${-y * 10}deg) ` +
                `translateY(-4px) scale(1.02)`;
            // reflet dynamique
            card.style.background =
                `radial-gradient(600px circle at ${e.clientX - r.left}px ${e.clientY - r.top}px, ` +
                `rgba(239,0,44,0.10), transparent 45%), var(--bg-card)`;
        });
        card.addEventListener('mouseleave', () => {
            card.style.transform = '';
            card.style.background = '';
        });
    });
}

// ========== BOOT ==========
document.addEventListener('DOMContentLoaded', async function () {
    // vérifier la session avant tout
    const me = await apiGet('/api/auth/me');
    if (!me.ok) {
        location.href = '/auth.html';
        return;
    }
    document.getElementById('sidebarUser').textContent =
        (me.user.display_name || me.user.email) + (me.user.is_admin ? ' · admin' : '');
    loadDashboard();
    loadKeyStatus();
    initTilt();
    console.log('Agent OS — Mission Control 3D Flow Violet prêt.');
});

async function logout() {
    if (!confirm('Se déconnecter ?')) return;
    await apiPost('/api/auth/logout', {});
    location.href = '/auth.html';
}
