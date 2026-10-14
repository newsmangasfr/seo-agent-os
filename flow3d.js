/* ============================================================
   FLOW 3D — moteur visuel violet (canvas 2D pseudo-3D, 0 dépendance)
   Grille perspective en mouvement + particules en flux + néons
   ============================================================ */
'use strict';

const Flow3D = (() => {

    const COLORS = [
        [239, 0, 44],     // rouge vif (accent sceneai)
        [255, 85, 125],   // rose
        [255, 87, 196],   // pink
        [255, 145, 0],    // orange (accent secondaire)
    ];

    let canvas, ctx, W, H, dpr;
    let particles = [], gridOffset = 0;
    let mouseX = 0.5, mouseY = 0.5;
    let raf = null, running = false;
    const PARTICLE_COUNT = 70;
    const GRID_LINES = 14;

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        W = window.innerWidth; H = window.innerHeight;
        canvas.width = W * dpr; canvas.height = H * dpr;
        canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function spawn() {
        const c = COLORS[Math.floor(Math.random() * COLORS.length)];
        const depth = Math.random();                    // 0 = loin, 1 = près
        return {
            x: Math.random() * W,
            y: Math.random() * H,
            z: depth,
            r: 0.8 + depth * 2.6,
            vx: (Math.random() - 0.5) * (0.25 + depth * 0.7),
            vy: (Math.random() - 0.5) * (0.25 + depth * 0.7),
            c,
            a: 0.15 + depth * 0.45,
            pulse: Math.random() * Math.PI * 2,
            pulseSpeed: 0.015 + Math.random() * 0.03,
        };
    }

    function initParticles() {
        particles = [];
        for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(spawn());
    }

    // ---- grille perspective au sol ----
    function drawGrid(t) {
        const horizon = H * 0.62;
        const cx = W / 2;
        ctx.save();

        // lignes horizontales fuyantes (défilement)
        const lineCount = GRID_LINES;
        for (let i = 0; i < lineCount; i++) {
            // perspective : les lignes se resserrent vers l'horizon
            let p = ((i / lineCount) + gridOffset) % 1;
            const y = horizon + Math.pow(p, 2.4) * (H - horizon) * 1.6;
            if (y > H + 20) continue;
            const alpha = 0.05 + p * 0.1;
            const grad = ctx.createLinearGradient(0, y, W, y);
            grad.addColorStop(0, 'rgba(239,0,44,0)');
            grad.addColorStop(0.5, `rgba(239,0,44,${alpha})`);
            grad.addColorStop(1, 'rgba(239,0,44,0)');
            ctx.strokeStyle = grad;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(W, y);
            ctx.stroke();
        }

        // lignes verticales fuyant vers un point de fuite
        const vpx = cx + (mouseX - 0.5) * W * 0.12;   // point de fuite suit la souris
        for (let i = -8; i <= 8; i++) {
            const xBottom = cx + i * (W / 7);
            const alpha = 0.04 + (1 - Math.abs(i) / 8) * 0.07;
            ctx.strokeStyle = `rgba(255,87,196,${alpha})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(xBottom, H);
            ctx.lineTo(vpx, horizon);
            ctx.stroke();
        }

        // halo d'horizon
        const halo = ctx.createLinearGradient(0, horizon - 60, 0, horizon + 10);
        halo.addColorStop(0, 'rgba(239,0,44,0)');
        halo.addColorStop(1, 'rgba(239,0,44,0.06)');
        ctx.fillStyle = halo;
        ctx.fillRect(0, horizon - 60, W, 70);

        ctx.restore();
    }

    // ---- flux de particules ----
    function drawParticles(t) {
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            p.x += p.vx; p.y += p.vy;
            p.pulse += p.pulseSpeed;

            // recycle aux bords
            if (p.x < -20) p.x = W + 20;
            if (p.x > W + 20) p.x = -20;
            if (p.y < -20) p.y = H + 20;
            if (p.y > H + 20) p.y = -20;

            const twinkle = p.a + Math.sin(p.pulse) * 0.18;
            const [r, g, b] = p.c;

            // halo
            const haloR = p.r * 5;
            const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, haloR);
            grad.addColorStop(0, `rgba(${r},${g},${b},${Math.max(0, twinkle) * 0.5})`);
            grad.addColorStop(1, `rgba(${r},${g},${b},0)`);
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(p.x, p.y, haloR, 0, Math.PI * 2);
            ctx.fill();

            // coeur
            ctx.fillStyle = `rgba(${r},${g},${b},${Math.max(0.05, twinkle)})`;
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fill();

            // liaisons entre particules proches
            for (let j = i + 1; j < particles.length; j++) {
                const q = particles[j];
                const dx = p.x - q.x, dy = p.y - q.y;
                const d2 = dx * dx + dy * dy;
                if (d2 < 15000) {
                    const d = Math.sqrt(d2);
                    const alpha = (1 - d / 122) * 0.09;
                    ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
                    ctx.lineWidth = 0.7;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(q.x, q.y);
                    ctx.stroke();
                }
            }
        }
    }

    // ---- orbes de lumière flottantes (gros flous violets) ----
    function drawOrbs(t) {
        const orbs = [
            { x: W * 0.82, y: H * 0.18, r: 220, c: '239,0,44', sp: 0.00012 },
            { x: W * 0.15, y: H * 0.75, r: 260, c: '255,87,196', sp: 0.00009 },
            { x: W * 0.55, y: H * 0.45, r: 180, c: '217,70,239', sp: 0.00015 },
        ];
        for (const o of orbs) {
            const ox = o.x + Math.sin(t * o.sp + o.r) * 40;
            const oy = o.y + Math.cos(t * o.sp * 1.3 + o.r) * 30;
            const grad = ctx.createRadialGradient(ox, oy, 0, ox, oy, o.r);
            grad.addColorStop(0, `rgba(${o.c},0.10)`);
            grad.addColorStop(0.6, `rgba(${o.c},0.03)`);
            grad.addColorStop(1, `rgba(${o.c},0)`);
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(ox, oy, o.r, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    function frame(t) {
        if (!running) return;
        ctx.clearRect(0, 0, W, H);

        // fond dégradé profond
        const bg = ctx.createLinearGradient(0, 0, 0, H);
        bg.addColorStop(0, '#0a0a0b');
        bg.addColorStop(0.6, '#08080a');
        bg.addColorStop(1, '#0a0a0b');
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, W, H);

        gridOffset = (gridOffset + 0.0012) % 1;

        drawOrbs(t);
        drawGrid(t);
        drawParticles(t);

        raf = requestAnimationFrame(frame);
    }

    function start() {
        if (running) return;
        canvas = document.getElementById('flow3d');
        if (!canvas) return;
        ctx = canvas.getContext('2d');
        resize();
        initParticles();
        running = true;
        window.addEventListener('resize', () => { resize(); initParticles(); });
        window.addEventListener('mousemove', e => {
            mouseX = e.clientX / W;
            mouseY = e.clientY / H;
        });
        raf = requestAnimationFrame(frame);
    }

    function stop() {
        running = false;
        if (raf) cancelAnimationFrame(raf);
    }

    return { start, stop };
})();

document.addEventListener('DOMContentLoaded', () => Flow3D.start());
