// Agent OS — logique d'authentification (login / register)

function showError(msg) {
    const el = document.getElementById('authError');
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 6000);
}

function switchTab(tab) {
    const isLogin = tab === 'login';
    document.getElementById('loginForm').style.display = isLogin ? '' : 'none';
    document.getElementById('registerForm').style.display = isLogin ? 'none' : '';
    document.getElementById('tabLogin').classList.toggle('active', isLogin);
    document.getElementById('tabRegister').classList.toggle('active', !isLogin);
    document.getElementById('authSub').textContent = isLogin
        ? 'Connecte-toi à ton cockpit IA'
        : 'Crée ton compte Agent OS';
    document.getElementById('authError').classList.remove('show');
}

async function doLogin(e) {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPass').value;
    if (!email || !password) { showError('Email et mot de passe requis.'); return; }
    try {
        const r = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const j = await r.json();
        if (j.ok) {
            location.href = '/dashboard.html';
        } else {
            showError(j.error || 'Connexion impossible.');
        }
    } catch (err) {
        showError('Erreur réseau : ' + err.message);
    }
}

async function doRegister(e) {
    e.preventDefault();
    const display_name = document.getElementById('regName').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const password = document.getElementById('regPass').value;
    const password2 = document.getElementById('regPass2').value;
    if (!email || !password) { showError('Email et mot de passe requis.'); return; }
    if (password !== password2) { showError('Les mots de passe ne correspondent pas.'); return; }
    if (password.length < 8) { showError('8 caractères minimum.'); return; }
    try {
        const r = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, display_name }),
        });
        const j = await r.json();
        if (j.ok) {
            location.href = '/dashboard.html';
        } else {
            showError(j.error || 'Inscription impossible.');
        }
    } catch (err) {
        showError('Erreur réseau : ' + err.message);
    }
}

// au chargement : si aucun compte -> forcer l'onglet inscription
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const r = await fetch('/api/auth/setup-needed');
        const j = await r.json();
        if (j.ok && j.setup_needed) {
            document.getElementById('setupBanner').classList.add('show');
            switchTab('register');
        }
    } catch (e) { /* hors ligne : on garde l'onglet login */ }
});
