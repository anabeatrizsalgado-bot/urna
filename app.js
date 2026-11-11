let eleitores = {}, candidatos = [], cargos = [];
let eleitorAtual = null, cargoIndex = 0, votosSessao = [];
let chartAdmin = null, chartPublico = null;

async function carregarDados() {
    const res = await fetch('/api/dados');
    const data = await res.json();
    eleitores = data.eleitores;
    candidatos = data.candidatos;
    cargos = [...new Set(candidatos.map(c => c.cargo))];
}
carregarDados();

function mostrarTela(id) {
    document.querySelectorAll('.tela').forEach(t => t.classList.remove('ativa'));
    document.getElementById(id).classList.add('ativa');
    if(id === 'tela-admin') renderizarAdmin();
    if(id === 'tela-publico') renderizarPublico();
}

// ================= VOTAÇÃO =================
function autenticar() {
    const eid = document.getElementById('input-eleitor').value.trim();
    const msg = document.getElementById('msg-erro');
    if (!eleitores[eid]) { msg.innerText = "ACESSO NEGADO. ID INVÁLIDO."; return; }
    
    eleitorAtual = eid; cargoIndex = 0; votosSessao = []; msg.innerText = "";
    renderizarVotacao();
    mostrarTela('tela-voto');
}

function renderizarVotacao() {
    if (cargoIndex >= cargos.length) return finalizarVoto();
    
    const cargoAtual = cargos[cargoIndex];
    document.getElementById('cargo-atual').innerText = cargoAtual.toUpperCase();
    document.getElementById('progresso').innerText = `${cargoIndex + 1} / ${cargos.length}`;
    limparDisplay();

    const lista = document.getElementById('lista-candidatos');
    lista.innerHTML = '';
    candidatos.filter(c => c.cargo === cargoAtual).forEach(c => {
        lista.innerHTML += `
            <div class="cand-item">
                <span class="num">${c.numero}</span>
                <span class="nome">${c.nome}</span>
                <span class="partido">${c.partido}</span>
            </div>`;
    });
}

function digitar(n) { const d = document.getElementById('display-numero'); if (d.innerText.length < 6) d.innerText += n; }
function limparDisplay() { document.getElementById('display-numero').innerText = ''; }

function confirmarVoto() {
    const num = document.getElementById('display-numero').innerText;
    const validos = candidatos.filter(c => c.cargo === cargos[cargoIndex]).map(c => c.numero);
    if (!validos.includes(num)) { alert("NÚMERO INVÁLIDO!"); return; }
    
    votosSessao.push({ numero: num, cargo: cargos[cargoIndex] });
    cargoIndex++; renderizarVotacao();
}

function votarBranco() {
    votosSessao.push({ numero: "BRANCO", cargo: cargos[cargoIndex] });
    cargoIndex++; renderizarVotacao();
}

async function finalizarVoto() {
    await fetch('/api/votar', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ eid: eleitorAtual, votos: votosSessao })
    });
    mostrarTela('tela-fim');
}

function voltarInicio() { document.getElementById('input-eleitor').value = ''; mostrarTela('tela-login'); }

// ================= DASHBOARD E FUNÇÕES EXTRAS =================
async function renderizarAdmin() {
    const res = await fetch('/api/resultados');
    const data = await res.json();
    
    const st = document.getElementById('stats-container');
    st.innerHTML = `
        <div class="stat-item"><span class="val">${data.stats.total}</span><span class="lbl">APTOS</span></div>
        <div class="stat-item" style="border-color: var(--green)"><span class="val">${data.stats.compareceram}</span><span class="lbl">VOTARAM</span></div>
        <div class="stat-item" style="border-color: var(--red)"><span class="val">${data.stats.abstencoes}</span><span class="lbl">AUSENTES</span></div>
    `;
    renderizarGrafico(data, 'chart-votos', chartAdmin, true);
}

async function renderizarPublico() {
    const res = await fetch('/api/resultados');
    const data = await res.json();
    
    const st = document.getElementById('stats-publico');
    st.innerHTML = `
        <div class="stat-item"><span class="val">${data.stats.compareceram}</span><span class="lbl">VOTOS TOTAIS</span></div>
        <div class="stat-item"><span class="val">${(data.stats.compareceram / data.stats.total * 100 || 0).toFixed(1)}%</span><span class="lbl">COMPARECIMENTO</span></div>
    `;
    renderizarGrafico(data, 'chart-publico', chartPublico, false);
}

function renderizarGrafico(data, canvasId, chartInstance, mostrarPartidos) {
    let labels = [], votosData = [];
    
    if (mostrarPartidos && data.partidos) {
        data.partidos.forEach(p => { labels.push(p.partido); votosData.push(p.votos); });
    } else {
        for (const [cargo, cands] of Object.entries(data.resultados)) {
            cands.forEach(c => { labels.push(`${c.nome}`); votosData.push(c.votos); });
        }
    }

    if (chartInstance) chartInstance.destroy();
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    const newChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: votosData,
                backgroundColor: 'rgba(0, 255, 255, 0.2)',
                borderColor: '#0ff', borderWidth: 2, borderRadius: 5,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#6688cc' } },
                x: { grid: { display: false }, ticks: { color: '#6688cc' } }
            }
        }
    });

    if (canvasId === 'chart-votos') chartAdmin = newChart;
    else chartPublico = newChart;
}

async function gerarBoletim() {
    const res = await fetch('/api/gerar_bu', { method: 'POST' });
    const data = await res.json();
    alert(`✅ ${data.msg}\nO arquivo "boletim.txt" foi criado na pasta do projeto.`);
}

async function auditarUrna() {
    const res = await fetch('/api/auditar');
    const data = await res.json();
    if (data.integridade) {
        alert("🛡️ AUDITORIA CONCLUÍDA:\n\nA Hash Chain está 100% ÍNTEGRA. Nenhum voto foi adulterado.");
    } else {
        alert("🚨 ALERTA CRÍTICO:\n\nA Hash Chain foi QUEBRADA! O arquivo votos.dat foi modificado manualmente.");
    }
}