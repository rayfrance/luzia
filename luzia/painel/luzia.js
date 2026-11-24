// Luzia · painel local. Modelo de luz (docs/luzia-ux.md, docs/specs/2026-11-18-centelhas-conversao.md):
// cada prisma (skill) tem as centelhas da meta; o progresso é o lm das próprias sobre o total. O loop central é
// converter luz refletida (o agente aplicou) em luz própria (você explicou), com a Luzia guiando e o seu sim no fim.
// Visual: direção "Lume" (design/v2). Laranja = luz própria e o ato de acender; lilás = refletida; o estado sempre
// tem rótulo escrito. Dados: /api/estado, /api/entrega e as ações POST. Nada fica guardado no navegador.
const I = {
  hoje: '<path d="M12 8a4 4 0 1 0 0 8a4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  trajetoria: '<path d="M12 3l9 17H3z"/>',
  centelhas: '<path d="M12 2l2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4z"/>',
  entregas: '<path d="M4 7h16v12H4zM9 7V5h6v2"/>',
  ajustes: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M16 4a2 2 0 1 0 0 4a2 2 0 0 0 0-4zM10 10a2 2 0 1 0 0 4a2 2 0 0 0 0-4zM18 16a2 2 0 1 0 0 4a2 2 0 0 0 0-4z"/>',
  copiar: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  olho: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  raio: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/>',
  enviar: '<path d="M4 12l16-8-6 16-3-7z"/>',
  fechar: '<path d="M6 6l12 12M18 6L6 18"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.01"/>',
  agente: '<rect x="4" y="7" width="16" height="12" rx="3"/><path d="M12 3v4M9 13h.01M15 13h.01"/>',
  restaurar: '<path d="M4 12a8 8 0 1 0 2.3-5.7M4 4v4h4"/>',
  relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  seta: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  baixo: '<path d="M6 9l6 6 6-6"/>',
};
const ic = (n, c = '') => `<svg class="ic ${c}" viewBox="0 0 24 24" aria-hidden="true">${I[n] || ''}</svg>`;

const TELAS = [['hoje', 'Hoje'], ['trajetoria', 'Trajetória'], ['centelhas', 'Centelhas'], ['entregas', 'Entregas'], ['ajustes', 'Ajustes']];
const ROTULO = { propria: 'Luz própria', convertendo: 'Convertendo', refletida: 'Luz refletida', apagada: 'Por acender', descartada: 'Descartada' };
const CURTO = { propria: 'própria', convertendo: 'convertendo', refletida: 'refletida', apagada: 'por acender', descartada: 'descartada' };
const ORDEM = { convertendo: 0, refletida: 1, apagada: 2, propria: 3, descartada: 4 };
const ORIGEM = { triagem: 'da triagem', chat: 'do chat', sessao: 'do chat', lampejo: 'do chat', acender: 'acesa por você', entrega: 'da entrega', pedido: 'do pedido' };
const SEGMENTOS = [['converter', 'Para converter'], ['propria', 'Próprias'], ['apagada', 'Por acender'], ['todas', 'Todas']];
const TIPOS = ['praticar', 'explicar', 'estudar', 'explorar'];
// [ícone, nome curto, descrição, dica do selo]
const MODOS = {
  ativo: ['raio', 'Em foco', 'Coleta centelhas e propõe conversões no chat', 'Com centelhas da sessão no chat'],
  passivo: ['olho', 'Em silêncio', 'Coleta centelhas sem interromper', 'Coleta centelhas sem interromper o chat'],
  sob_demanda: ['chat', 'Fora de foco', 'Só age quando você chama', 'Só age quando você chama um comando'],
};
const AGENTES = {
  'claude-code': ['Claude Code', 'Fila, comandos e foco automático'],
  codex: ['Codex', 'Fila e comandos via AGENTS.md'],
  cursor: ['Cursor', 'Fila e comandos via User Rules'],
  antigravity: ['Antigravity', 'Fila e comandos via GEMINI.md'],
  outro: ['Outro', 'Qualquer agente com terminal'],
};
const TIPO_PEDIDO_NOME = { incluir: 'Incluir', mudar_meta: 'Mudar meta de', arquivar: 'Arquivar', reativar: 'Reativar', dividir: 'Dividir', propor_meta: 'Meta de' };
const NOME_DIM = { P1: 'Direção no prompt', P2: 'Coesão', P3: 'Aplicação de conceito', P4: 'Decisão de arquitetura' };
const FALTA_DIM = { P1: 'Sem base ainda.', P2: 'Sem base ainda.', P3: 'Falta você explicar.', P4: 'Falta você defender.' };
const FONTES = { agente: 'o agente aplicou', prompt: 'você dirigiu', acesa: 'centelha acesa', conversao: 'luz convertida', feixe: 'centelha acesa' };
const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

let E = null;
let filtroEstado = 'converter';
let filtroPrisma = 'todos';
let filtroTipo = 'todos';
let mostrarFormPedido = false;
let tipoPedidoForm = 'incluir';
let conquista = null;                // { id, fase: 'pronta' | 'virou', r } enquanto a sobreposição está aberta
const entregasAbertas = new Set();   // detalhes de entrega abertos: sobrevivem ao render() do polling

const $ = (s, r = document) => r.querySelector(s);
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const centelhas = () => E?.centelhas || [];
const cPorId = (id) => centelhas().find((c) => c.id === id);
const aPorId = (id) => (E?.avancos || []).find((a) => a.id === id);
const prismasLuz = () => E?.luz?.prismas || [];
const pLuz = (nome) => prismasLuz().find((p) => p.nome === nome);
const nomeAgente = () => AGENTES[E?.agente]?.[0] || 'seu agente';
const plural = (n, um, varios) => `${n} ${Number(n) === 1 ? um : (varios || um + 's')}`;
const numero = (n) => Number(n || 0).toLocaleString('pt-BR');
const cap = (s) => String(s || '').charAt(0).toUpperCase() + String(s || '').slice(1);
const truncar = (t, n = 120) => {
  const s = String(t || '').trim();
  return s.length <= n ? s : s.slice(0, n - 1).replace(/\s+\S*$/, '') + '…';
};

// Nome curto do prisma: o do servidor (nome_curto) quando o prisma está no estado; senão a mesma regra.
function nomeCurto(nome) {
  const n = String(nome || '').replace(/\s+/g, ' ').trim();
  const doServidor = (E?.prismas || []).find((p) => p.nome === n)?.nome_curto;
  if (doServidor) return doServidor;
  const m = /^(.*?)\s*\(([^()]+)\)\s*$/.exec(n);
  if (m && /^[\wÀ-ÿ.#+-]{2,10}$/.test(m[2].trim())) return m[2].trim();
  const base = (m ? m[1] : n).trim();
  if (base.length <= 20) return base;
  const ultimo = base.split(/\s+\/\s+/).pop().trim();
  if (ultimo !== base && ultimo.length >= 2 && ultimo.length <= 20) return ultimo;
  return base.slice(0, 18).trim() + '…';
}
const curto = (s) => esc(nomeCurto(s));
function dataCurta(iso, comAno = false) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''));
  if (!m) return '';
  const ano = comAno || m[1] !== String(new Date().getFullYear()) ? ` ${m[1]}` : '';
  return `${Number(m[3])} ${MESES[Number(m[2]) - 1]}${ano}`;
}
function periodoCurto(inicio, fim) {
  const a = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(inicio || ''));
  const b = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(fim || inicio || ''));
  if (!a || !b) return '';
  if (a[0] === b[0]) return dataCurta(inicio);
  return `${dataCurta(inicio)} – ${dataCurta(fim)}`;
}

// `auto`: pedido que a página faz sozinha (polling, leituras automáticas); o servidor confere a sessão sem renová-la.
async function api(caminho, dados, auto = false) {
  try {
    const headers = auto ? { 'X-Luzia-Auto': '1' } : {};
    if (dados) headers['Content-Type'] = 'application/json';
    const r = await fetch(caminho, dados ? { method: 'POST', headers, body: JSON.stringify(dados) } : { headers });
    const j = await r.json().catch(() => ({}));
    if (r.status === 401 && j.login) {  // sessão ausente, vencida ou derrubada: volta à entrada e para o polling
      acessoAoIniciar();
      return { erro: j.erro || 'abra o painel pelo seu agente', login: true };
    }
    return r.ok ? j : { ...j, erro: j.erro || `erro ${r.status}` };
  } catch {
    return { erro: 'Luzia desligada. Rode /luzia:career-map no chat.', offline: true };
  }
}

// Toast = resultado, não instrução. `acao` opcional: um botão (ex.: Desfazer) com os mesmos data-* dos botões da tela.
function toast(texto, classe = '', acao = null) {
  const el = $('#toast');
  el.className = 'toast ' + classe;
  const bt = acao ? `<button class="btn link mini" ${Object.entries(acao.dados || {}).map(([k, v]) => `data-${k}="${esc(v)}"`).join(' ')}>${esc(acao.rotulo)}</button>` : '';
  el.innerHTML = `<span>${esc(texto)}</span>${bt}`;
  el.hidden = false;
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (el.hidden = true), acao ? 6000 : 3200);
}

// ------------------------------------------------------------------ peças de luz
const orbe = (estado, extra = '') => `<i class="orbe ${esc(estado)} ${extra}" aria-hidden="true"></i>`;
// Barra segmentada: cada centelha é um segmento proporcional ao lm. `foco`: id da centelha em destaque.
function segs(lista, { foco = '', classe = '', rotulo = '' } = {}) {
  const partes = lista.filter((x) => x.lm > 0).map((x) => `<i class="${esc(x.estado)} ${x.id && x.id === foco ? 'foco' : ''}" style="flex:${x.lm} 1 0" title="${esc(x.titulo ? `${ROTULO[x.estado] || x.estado}: ${x.titulo} · ${x.lm} lm` : `${ROTULO[x.estado] || x.estado} · ${x.lm} lm`)}"></i>`).join('');
  return `<span class="segs ${classe}" ${rotulo ? `role="img" aria-label="${esc(rotulo)}"` : 'aria-hidden="true"'}>${partes}</span>`;
}
const segsTotal = (classe = '') => {
  const pe = E.luz?.por_estado || {};
  return segs(['propria', 'convertendo', 'refletida', 'apagada'].map((k) => ({ estado: k, lm: pe[k] || 0 })), { classe });
};
const ariaPrisma = (p) => `${p.nome}: ${p.propria} de ${p.tot} lúmens em luz própria, ${p.refletida} refletidos para converter`;
const tri = (p, g = false) => `<span class="tri ${g ? 'g' : ''}" aria-hidden="true" style="--p:${p.pct || 0};--r:${Math.min(100, (p.pct || 0) + (p.pct_refletida || 0))};filter:${p.pct ? `drop-shadow(0 0 ${6 + Math.round(p.pct / 8)}px rgba(240,138,60,.5))` : 'none'}"><span></span></span>`;
function resumoPrisma(p) {
  if (p.na_meta) return 'Na meta · tudo é luz própria';
  if (!p.n) return 'Nenhuma centelha ainda';
  return [p.n_converter ? `${p.n_converter} para converter · ${p.refletida} lm` : '', p.n_apagada ? `${p.n_apagada} por acender` : '']
    .filter(Boolean).join(' · ') || `${p.n_propria} de ${p.n} centelhas são suas`;
}
const pctDepois = (p, c) => (p && p.tot ? Math.round((100 * (p.propria + (c.estado === 'propria' ? 0 : c.lm))) / p.tot) : 0);
const origemTxt = (c) => (c.entrega_id ? 'da entrega' : ORIGEM[String(c.origem || '').toLowerCase()] || '');
const rotuloEstado = (c) => (c.estado === 'convertendo' && c.confirmada ? 'Convertendo · confirmada' : ROTULO[c.estado] || c.estado);
function rotuloAcao(c) {
  if (c.na_fila && c.estado !== 'propria') return `Na fila do ${nomeAgente()}`;
  if (c.estado === 'convertendo') return `Continuar no ${nomeAgente()}`;
  if (c.estado === 'refletida') return 'Converter com a Luzia';
  return `Acender no ${nomeAgente()}`;
}

// Cartão de centelha (tela Centelhas): estado e origem, título, onde apareceu, tipo · prisma · min e lúmens.
function cartaoCentelha(c) {
  const linha = c.onde ? `Apareceu em ${c.onde}` : (c.desc || truncar(c.porque, 90));
  const rot = `${c.titulo}, ${rotuloEstado(c)}, ${nomeCurto(c.prisma)}, ${c.lm} lúmens`;
  return `<button class="centelha ${esc(c.estado)}" data-centelha="${esc(c.id)}" aria-label="${esc(rot)}">
    <span class="topo"><span class="cor-${esc(c.estado)}">${orbe(c.estado)}${esc(rotuloEstado(c))}</span><small>${esc(origemTxt(c))}</small></span>
    <b class="t">${esc(c.titulo)}</b>
    <span class="linha">${esc(linha)}</span>
    <span class="pe"><span>${esc(cap(c.tipo || 'praticar'))} · ${curto(c.prisma)}${c.min ? ` · ${c.min} min` : ''}</span><b class="cor-${esc(c.estado)}">${c.lm} lm</b></span>
  </button>`;
}

// Cartão curto (Hoje · Luz refletida para converter).
function cartaoConverter(c) {
  return `<button class="centelha ${esc(c.estado)}" data-centelha="${esc(c.id)}">
    <span class="topo"><span class="cor-${esc(c.estado)}">${orbe(c.estado)}${curto(c.prisma)}</span><b>${c.lm} lm</b></span>
    <b class="t">${esc(c.titulo)}</b>
    <span class="linha">${esc(c.onde ? `Apareceu em ${c.onde}` : truncar(c.porque, 80))}</span>
    <span class="cta">${c.estado === 'convertendo' ? 'Continuar' : 'Converter'} →</span>
  </button>`;
}

function itemLista(item) {
  const c = cPorId(item.id) || item;
  return `<li><button data-centelha="${esc(c.id)}">${orbe(c.estado)}
    <span class="tt"><b class="${c.estado === 'apagada' ? 'lacuna' : ''}">${esc(c.titulo)}</b>${c.desc || c.onde ? `<span>${esc(c.desc || `Apareceu em ${c.onde}`)}</span>` : ''}</span>
    <span class="est cor-${esc(c.estado)}">${esc(CURTO[c.estado] || c.estado)}</span><b class="lm">${c.lm} lm</b></button></li>`;
}

// Banner único das análises vencidas (as automáticas de leiturasAutomaticas continuam).
function bannerLeituras() {
  const n = E?.leituras_vencidas || 0;
  if (!n || !E.modelo_pronto) return '';
  return `<div class="aviso fino" role="status">${ic('info', 'p')}<span>${plural(n, 'análise desatualizada', 'análises desatualizadas')}</span>
    <button class="btn link mini" data-gerar-leituras="1">Atualizar</button></div>`;
}

function resumoBaseLeitura(leitura, fallbackFatos = '') {
  if (leitura && leitura.base && typeof leitura.base === 'object') {
    const b = leitura.base;
    if (leitura.alvo_tipo === 'prisma') {
      const l = b.luz || b.lumens || {};
      if (l.tot != null || l.propria != null) return `${l.propria ?? 0} de ${l.tot ?? 0} lm em luz própria, ${plural(b.n ?? l.n ?? 0, 'centelha')}`;
      return fallbackFatos || 'centelhas e lúmens do prisma';
    }
    if (leitura.alvo_tipo === 'entrega') {
      const f = b.fatos || {};
      return `${plural(f.commits ?? 0, 'commit')}, ${plural(f.arquivos ?? 0, 'arquivo')}, ${plural(f.linhas ?? 0, 'linha')}, ${plural((b.prismas || []).length, 'prisma')}`;
    }
    if (leitura.alvo_tipo === 'pedido') return `o pedido (${TIPO_PEDIDO_NOME[b.tipo] || b.tipo || ''} ${nomeCurto(b.prisma || '')}) e a trajetória atual`;
  }
  return fallbackFatos || 'fatos medidos pela Luzia';
}

// Análise da Luzia: texto primeiro; abaixo "Análise da Luzia · 12 nov · base e modelo" (popover focável).
function blocoLeitura(leitura, fallbackFatos = '', json = false, indisponivel = '') {
  if (!leitura || !leitura.texto || !leitura.modelo) {
    let txt = indisponivel ? `Sem análise: ${esc(indisponivel)}` : 'Sem análise ainda.';
    let bt = '';
    if (!indisponivel && E && !E.modelo_pronto) {
      txt = 'Sem análise: falta configurar o modelo.';
      bt = '<button class="btn link mini" data-ir="ajustes">Configurar</button>';
    } else if (!indisponivel && E && E.modelo_pronto) {
      bt = '<button class="btn link mini" data-gerar-leituras="1">Gerar análise</button>';
    }
    return `<div class="leitura vazia"><span>${txt}</span> ${bt}</div>`;
  }
  const base = resumoBaseLeitura(leitura, fallbackFatos);
  const data = dataCurta(leitura.criado_em) || 'data desconhecida';
  const dica = `Base: ${base} · Modelo: ${leitura.modelo} · ${dataCurta(leitura.criado_em, true) || 'data desconhecida'}`;
  const vencida = leitura.vencida ? ' <span class="pilula">desatualizada</span><button class="btn link mini" data-gerar-leituras="1">Atualizar</button>' : '';
  const verJson = json && leitura.base
    ? `<details class="base-json"><summary>Ver base (JSON)</summary><pre>${esc(JSON.stringify(leitura.base, null, 2))}</pre></details>` : '';
  return `<div class="leitura">
    <p class="leitura-texto">${esc(leitura.texto)}</p>
    <div class="assin">Análise da Luzia · ${esc(data)} ·
      <span class="info-base" tabindex="0" role="img" aria-label="${esc(dica)}" data-dica="${esc(dica)}">base e modelo</span>${vencida}
    </div>${verJson}
  </div>`;
}

// ------------------------------------------------------------------ Hoje
function cabecalho() {
  const botoes = TELAS.map(([id, nome]) => `<button data-tela="${id}">${ic(id)}${nome}</button>`).join('');
  $('#nav').innerHTML = botoes;
  $('#nav-baixo').innerHTML = botoes;
}
function seloFoco() {
  const m = MODOS[E.modo];
  return `<span class="selo" title="${esc(m?.[3] || '')}"><span class="ponto ${esc(E.modo)}"></span>${esc(m?.[1] || E.modo_nome || E.modo)}</span>`;
}
function linhaTrajetoria() {
  const c = E.carreira || {};
  const t = E.luz || {};
  return `<div class="linha-traj">
    <button data-ir="trajetoria" aria-label="${esc(`${c.de || 'Hoje'} para ${c.para || 'a meta'}: ${t.pct || 0}% em luz própria, ${t.refletida || 0} lúmens refletidos para converter. Ver trajetória.`)}">
      <span class="rot">${esc(c.de || 'Hoje')} → ${esc(c.para || 'Meta')}</span>${segsTotal('fina')}<b>${t.pct || 0}% seu</b>
    </button>${seloFoco()}</div>`;
}
function avisoConfirmada() {
  const c = centelhas().find((x) => x.estado === 'convertendo' && x.confirmada && x.id !== E.hero);
  if (!c) return '';
  return `<div class="aviso confirmada" role="status">${orbe('convertendo')}
    <span class="txt"><b>A Luzia confirmou seu entendimento</b><span>${esc(c.titulo)} · ${curto(c.prisma)} · +${c.lm} lm</span></span>
    <button class="btn acender" data-confirmar="${esc(c.id)}">Acender luz própria</button></div>`;
}
function destaqueHoje() {
  const h = cPorId(E.hero);
  if (!h) {
    const ap = centelhas().filter((c) => c.estado === 'apagada').sort((a, b) => b.lm - a.lm)[0];
    if (ap) return destaque(ap, 'Próximo passo');
    if (!centelhas().some((c) => !c.descartada)) {
      const p = prismasLuz()[0];
      return `<div class="vazio-destaque"><span class="sobre-linha">Começo</span><h1>Sua trajetória ainda não tem centelhas</h1>
        <p class="lacuna">Acenda as primeiras de um prisma. A Luzia propõe; você faz no seu agente.</p>
        ${p ? `<button class="btn acender" data-acender="${esc(p.nome)}">Acender 3 centelhas de ${curto(p.nome)}</button>` : ''}</div>`;
    }
    return `<div class="vazio-destaque"><span class="sobre-linha">Tudo convertido</span><h1>Toda a luz da meta é sua</h1>
      <p class="lacuna">Peça uma mudança na trajetória para ir além.</p><button class="btn neutro" data-ir="trajetoria">Ver trajetória</button></div>`;
  }
  if (h.confirmada) return destaque(h, 'A Luzia confirmou seu entendimento');
  return destaque(h, h.estado === 'convertendo' ? 'Continue a conversão' : 'Converta esta luz');
}
function destaque(c, chamada) {
  const p = pLuz(c.prisma) || { pct: 0, tot: 0, propria: 0, lista: [] };
  const depois = pctDepois(p, c);
  const tipoTxt = `${c.tipo || 'praticar'}${c.min ? ` · ${c.min} min` : ''}`;
  const de = c.estado === 'apagada' ? 'apagada' : 'refletida';
  return `<div class="destaque">
    <div class="texto">
      <span class="sobre-linha">${orbe(c.estado)}${esc(chamada)}</span>
      <h1><button data-centelha="${esc(c.id)}">${esc(c.titulo)}</button></h1>
      <p class="porque">${esc(truncar(c.porque, 220))}</p>
      <p class="onde">${c.onde ? `Apareceu em <b>${esc(c.onde)}</b> · ` : ''}${esc(tipoTxt)}</p>
      <div class="acoes-bt">
        ${c.confirmada ? `<button class="btn acender" data-confirmar="${esc(c.id)}">Acender luz própria</button>`
          : `<button class="btn acender" data-enviar="${esc(c.id)}" ${c.na_fila ? 'disabled' : ''}>${esc(rotuloAcao(c))}</button>
        <button class="btn sec" data-copiar="${esc(c.id)}">${ic('copiar', 'p')}Copiar prompt</button>`}
      </div>
    </div>
    <button class="conversao" data-centelha="${esc(c.id)}" aria-label="${esc(`Converter rende ${c.lm} lúmens de luz própria em ${c.prisma}: de ${p.pct}% para ${depois}%. Ver detalhes.`)}">
      <span class="orbes">
        <span class="cor-${de}">${orbe(de, 'g')}${de === 'apagada' ? 'por acender' : 'refletida'}</span>
        <svg viewBox="0 0 40 12" width="40" height="12" aria-hidden="true"><path d="M0 6h34M29 1l6 5-6 5" fill="none" stroke="#bdb2ca" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span class="cor-propria">${orbe('propria', 'g')}própria</span>
        <span class="ganho"><b>+${c.lm}</b><span>lm de luz própria</span></span>
      </span>
      <span class="pr"><b>${curto(c.prisma)}</b><span>${p.pct}% → <b class="cor-propria">${depois}%</b> seu</span></span>
      ${segs(p.lista || [], { foco: c.id })}
      <span class="discreto conta-link">Por que ${c.lm} lm</span>
    </button>
  </div>`;
}
function telaHoje() {
  const conv = centelhas().filter((c) => ['convertendo', 'refletida'].includes(c.estado))
    .sort((a, b) => ORDEM[a.estado] - ORDEM[b.estado] || b.lm - a.lm);
  const outras = conv.filter((c) => c.id !== E.hero).slice(0, 4);
  const lmConv = conv.reduce((s, c) => s + c.lm, 0);
  const hoje = centelhas().filter((c) => c.hoje && !c.descartada).slice(0, 5);
  $('#hoje').innerHTML = `
    ${linhaTrajetoria()}
    ${avisoConfirmada()}
    ${destaqueHoje()}
    ${outras.length ? `<h3 class="secao"><span>Luz refletida para converter <small>· ${plural(conv.length, 'centelha')} · ${lmConv} lm</small></span>
      <button class="btn link mini" data-filtro-ir="converter">Ver todas</button></h3>
      <div class="grade">${outras.map(cartaoConverter).join('')}</div>` : ''}
    <h3 class="secao">Seus prismas</h3>
    <div class="grade">${prismasLuz().map((p) => `<button class="prisma-cartao" data-prisma="${esc(p.nome)}">
      <span class="cab">${tri(p)}<span><b title="${esc(p.nome)}">${curto(p.nome)}</b><small>${p.n_propria} de ${p.n} centelhas são suas</small></span><b class="pct">${p.pct}%</b></span>
      ${segs(p.lista || [], { rotulo: ariaPrisma(p) })}
      <span class="resumo ${p.n_converter ? 'converter' : ''}">${esc(resumoPrisma(p))}</span>
    </button>`).join('') || '<p class="vazio">Nenhum prisma na trajetória.</p>'}</div>
    ${hoje.length ? `<div class="chips"><span class="discreto">Coletadas hoje</span>${hoje.map((c) => `<button class="chip ${esc(c.estado)}" data-centelha="${esc(c.id)}">${orbe(c.estado)}<b>${c.lm} lm</b> ${curto(c.prisma)} · ${esc(CURTO[c.estado])}</button>`).join('')}</div>` : ''}
    ${(E.lumens || []).length ? `<div class="chips"><span class="discreto">Luz recente</span>${(E.lumens || []).slice(-3).reverse().map((l, i) => `<button class="chip ${l.luz === 'refletida' ? 'refletida' : 'propria'}" data-lumen="${(E.lumens.length - 1) - i}">+${l.lm} ${curto(l.skill)} · ${esc(FONTES[l.fonte] || 'luz')}</button>`).join('')}</div>` : ''}`;
}

// ------------------------------------------------------------------ Trajetória
function renderFormPedido() {
  if (!mostrarFormPedido) return '';
  const seletorExistente = ['arquivar', 'reativar'].includes(tipoPedidoForm);
  const nomes = (E.prismas || []).filter((p) => (tipoPedidoForm === 'reativar' ? p.estado === 'arquivado' : p.estado !== 'arquivado')).map((p) => p.nome);
  const opcao = (v, rot) => `<option value="${v}" ${tipoPedidoForm === v ? 'selected' : ''}>${rot}</option>`;
  return `<div class="form-pedido">
    <div class="pedido-cab"><b>Mudar trajetória</b><button class="btn link mini" data-abrir-pedido-form="0">Fechar</button></div>
    <div class="campos">
      <label>O que mudar<select id="ped-tipo">${opcao('incluir', 'Incluir prisma')}${opcao('arquivar', 'Arquivar prisma')}${opcao('reativar', 'Reativar prisma')}</select></label>
      ${seletorExistente
        ? `<label>Prisma<select id="ped-prisma">${nomes.map((n) => `<option value="${esc(n)}">${curto(n)}</option>`).join('')}</select></label>`
        : '<label>Nome do prisma<input id="ped-prisma" placeholder="ex.: Mensageria"></label>'}
      <label>Por quê?<input id="ped-motivo" placeholder="ex.: o time vai adotar filas"></label>
    </div>
    <div class="acoes-bt" style="margin-top:18px"><button class="btn neutro" id="ped-enviar">Pedir proposta</button>
      <span class="discreto">A Luzia propõe as centelhas da meta; você decide.</span></div>
  </div>`;
}
const pilulaPedido = (p, aberto) => `<span class="pilula ${aberto ? 'proposta' : ''}">${aberto ? 'Proposta' : esc(p.estado)}</span>`;
function renderCardDividir(p, prop, aberto) {
  const partes = prop.partes || [];
  const nomes = partes.map((x) => x.nome);
  const avs = prop.avancos || [];
  const opcoes = (atual) => nomes.map((n) => `<option value="${esc(n)}" ${n === atual ? 'selected' : ''}>${esc(n)}</option>`).join('');
  return `<div class="pedido-card ${esc(p.estado)}">
    <div class="pedido-cab"><span><b title="${esc(p.prisma)}">Dividir ${curto(p.prisma)}</b> <small class="discreto">#${p.id} · ${esc(dataCurta(p.criado_em))}</small></span>${pilulaPedido(p, aberto)}</div>
    <p class="lacuna">Um prisma é uma habilidade só. As centelhas se dividem, e nenhuma luz se perde.</p>
    <div class="campos" style="margin-top:12px">${partes.map((x, i) => aberto
      ? `<label>Habilidade ${i + 1}<input data-div-parte="${p.id}" value="${esc(x.nome)}"></label>`
      : `<span class="tag luz">${esc(x.nome)}</span>`).join('')}</div>
    ${avs.length ? `<ul class="lista-simples">${avs.map((a) => `<li>${esc(a.titulo)} → ${aberto
      ? `<select data-div-mover="${p.id}" data-avanco-id="${esc(a.id)}" aria-label="Para qual habilidade">${opcoes(a.para)}</select>`
      : `<b>${esc(a.para)}</b>`}</li>`).join('')}</ul>` : ''}
    ${aberto ? `<div class="pedido-ajuste"><button class="btn neutro mini" data-pedido-aceitar="${p.id}">Aceitar</button>
      <button class="btn link mini" data-pedido-dividir-ajustar="${p.id}">Ajustar</button>
      <button class="btn link mini" data-pedido-recusar="${p.id}">Recusar</button></div>` : ''}
  </div>`;
}
function renderCardPedido(p) {
  const prop = p.proposta || {};
  const aberto = ['aberto', 'proposto'].includes(p.estado);
  if (p.tipo === 'dividir') return renderCardDividir(p, prop, aberto);
  const acoes = prop.acoes || prop.centelhas || [];
  return `<div class="pedido-card ${esc(p.estado)}">
    <div class="pedido-cab"><span><b title="${esc(p.prisma)}">${esc(TIPO_PEDIDO_NOME[p.tipo] || p.tipo)} ${curto(p.prisma)}</b> <small class="discreto">#${p.id} · ${esc(dataCurta(p.criado_em))}</small></span>${pilulaPedido(p, aberto)}</div>
    ${p.motivo ? `<p class="lacuna">${esc(p.motivo)}</p>` : ''}
    ${acoes.length ? `<div class="tags">${acoes.map((a) => `<span class="tag">${esc(a.titulo || a)}</span>`).join('')}</div>
      <p class="discreto">${plural(acoes.length, 'centelha nova', 'centelhas novas')} para a meta, por acender</p>` : ''}
    ${['incluir', 'mudar_meta', 'propor_meta'].includes(p.tipo) ? blocoLeitura(p.leitura, `pedido #${p.id} · ${nomeCurto(p.prisma)}`, false, prop.leitura_indisponivel) : ''}
    ${aberto ? `<div class="pedido-ajuste"><button class="btn neutro mini" data-pedido-aceitar="${p.id}">Aceitar</button>
      <button class="btn link mini" data-pedido-recusar="${p.id}">Recusar</button>
      <span class="discreto">Para ajustar, diga no chat: /luzia:trajetoria</span></div>` : ''}
  </div>`;
}
function telaTrajetoria() {
  const versoes = (E.trajetoria?.versoes || []).slice().reverse();
  const c = E.carreira || {};
  const t = E.luz || {};
  const pe = t.por_estado || {};
  const arquivados = (E.prismas || []).filter((p) => p.estado === 'arquivado');
  const pedidos = E.pedidos || [];
  const r = E.ritmo || {};
  $('#trajetoria').innerHTML = `
    <div class="cab-tela"><div><h2>Trajetória</h2><p>v${E.trajetoria?.versao_atual || 1} · ${esc(c.de || 'Hoje')} → ${esc(c.para || 'Meta')}</p>
      ${r.lm_faltam ? `<p class="discreto">${plural(r.feixes_semana || 1, 'centelha')} por semana leva até ${esc(c.para || 'a meta')} em ~${r.meses || 12} meses</p>` : ''}</div>
      <div class="acoes-bt">${(E.prismas || []).some((p) => p.estado !== 'arquivado' && (p.divisao || []).length) ? '<button class="btn sec mini" data-dividir-todos="1">Separar prismas compostos</button>' : ''}
        <button class="btn sec" data-abrir-pedido-form="1">Mudar trajetória</button></div></div>
    ${bannerLeituras()}
    <div class="bloco traj-total">
      <div class="linha1"><b>${t.pct || 0}%</b><span class="lacuna">do caminho até ${esc(c.para || 'a meta')} já é luz própria</span><small>${t.propria || 0} de ${t.tot || 0} lm</small></div>
      ${segs(['propria', 'convertendo', 'refletida', 'apagada'].map((k) => ({ estado: k, lm: pe[k] || 0 })), { classe: 'grossa', rotulo: `${t.pct || 0}% em luz própria, ${t.refletida || 0} lúmens refletidos para converter` })}
      <div class="legenda">${['propria', 'convertendo', 'refletida', 'apagada'].map((k) => `<span>${orbe(k)}${ROTULO[k]} <b>${pe[k] || 0} lm</b></span>`).join('')}</div>
    </div>
    <div style="margin-top:20px">${renderFormPedido()}${pedidos.filter((p) => ['aberto', 'proposto'].includes(p.estado)).map(renderCardPedido).join('')}</div>
    <div class="pilha">${prismasLuz().map((p) => {
      const base = (E.prismas || []).find((x) => x.nome === p.nome) || {};
      return `<section class="prisma-secao">
        <div class="cab">${tri(p, true)}<span><h2 title="${esc(p.nome)}">${curto(p.nome)}</h2><small>${p.propria} de ${p.tot} lm · ${p.n_propria} de ${p.n} centelhas são suas</small></span><b class="pct">${p.pct}%</b></div>
        ${segs(p.lista || [], { classe: '', rotulo: ariaPrisma(p) })}
        <h4>Centelhas da meta</h4>
        ${(p.lista || []).length ? `<ul class="lista-c">${p.lista.map(itemLista).join('')}</ul>` : '<p class="vazio">Nenhuma centelha ainda.</p>'}
        <div class="acoes-bt" style="margin-top:14px">${p.na_meta ? '' : `<button class="btn sec mini" data-acender="${esc(p.nome)}">${ic('raio', 'p')}Acender 3 centelhas</button>`}
          <button class="btn link mini" data-prisma="${esc(p.nome)}">Análise e detalhes</button></div>
        ${(base.divisao || []).length ? `<div class="composto">Junta assuntos: ${base.divisao.map(esc).join(', ')}.<button class="btn sec mini" data-dividir-prisma="${esc(p.nome)}">Separar em habilidades</button></div>` : ''}
      </section>`;
    }).join('')}</div>
    ${arquivados.length ? `<details class="recolhido"><summary>${ic('baixo', 'p')}Arquivados (${arquivados.length}) · a luz fica guardada</summary>
      <ul class="lista-simples">${arquivados.map((s) => `<li>${curto(s.nome)} · ${pedidos.some((p) => p.tipo === 'dividir' && p.estado === 'aceito' && p.prisma === s.nome)
        ? 'dividido em habilidades' : `<button class="btn link mini" data-reativar-prisma="${esc(s.nome)}">Reativar</button>`}</li>`).join('')}</ul></details>` : ''}
    ${pedidos.some((p) => !['aberto', 'proposto'].includes(p.estado)) ? `<details class="recolhido"><summary>${ic('baixo', 'p')}Pedidos decididos</summary>
      ${pedidos.filter((p) => !['aberto', 'proposto'].includes(p.estado)).map(renderCardPedido).join('')}</details>` : ''}
    <details class="recolhido"><summary>${ic('baixo', 'p')}Versões (${versoes.length})</summary>
      <div class="versoes">${versoes.map((v) => `v${v.numero} · ${v.pedido_id ? `pedido #${esc(v.pedido_id)}` : esc(v.origem)} · ${esc(dataCurta(v.criada_em))}`).join('<br>')}</div></details>`;
}

// ------------------------------------------------------------------ Centelhas
const passaEstado = (c, f) => (f === 'todas' ? !c.descartada : f === 'converter' ? ['refletida', 'convertendo'].includes(c.estado) : c.estado === f);
const passaPrisma = (c) => filtroPrisma === 'todos' || c.prisma === filtroPrisma;
const passaTipo = (c) => filtroTipo === 'todos' || String(c.tipo || '').toLowerCase() === filtroTipo;
function telaCentelhas() {
  const todas = centelhas();
  const outros = (c) => passaPrisma(c) && passaTipo(c);
  const lista = todas.filter((c) => passaEstado(c, filtroEstado) && outros(c)).sort((a, b) => ORDEM[a.estado] - ORDEM[b.estado] || b.lm - a.lm);
  const segmentos = [...SEGMENTOS, ...(todas.some((c) => c.descartada) ? [['descartada', 'Descartadas']] : [])];
  $('#centelhas').innerHTML = `
    <div class="filtros">
      <h2 style="font-size:26px;margin-right:14px">Centelhas</h2>
      <div class="seg" role="group" aria-label="Estado">${segmentos.map(([k, nome]) => `<button data-filtro-estado="${k}" aria-pressed="${filtroEstado === k}">${nome}<small>${todas.filter((c) => passaEstado(c, k) && outros(c)).length}</small></button>`).join('')}</div>
      <label class="menu primeiro">Prisma:<select data-filtro-select="prisma" aria-label="Filtrar por prisma"><option value="todos">todos</option>
        ${(E.prismas || []).map((p) => `<option value="${esc(p.nome)}" ${filtroPrisma === p.nome ? 'selected' : ''}>${curto(p.nome)}</option>`).join('')}</select></label>
      <label class="menu">Tipo:<select data-filtro-select="tipo" aria-label="Filtrar por tipo"><option value="todos">todos</option>
        ${TIPOS.map((t) => `<option value="${t}" ${filtroTipo === t ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    </div>
    ${lista.length ? `<div class="grade largo">${lista.map(cartaoCentelha).join('')}</div>`
      : '<div class="vazio-bloco"><span>Nada com esses filtros.</span><button class="btn sec" data-limpar-filtros="1">Limpar filtros</button></div>'}`;
}

// ------------------------------------------------------------------ Entregas
function baseHumana(k, d) {
  if (k !== 'P2' || !d.base) return d.base || '';
  const pen = [...String(d.base).matchAll(/−\s*(\d+)\s*\(([^)]+)\)/g)].filter((m) => Number(m[1]) > 0).map((m) => m[2]);
  return pen.length ? `${pen.join(' e ')} reduzem a nota.` : 'Entrega focada.';
}
function dimsMedidas(e) {
  const ks = ['P1', 'P2', 'P3', 'P4'].filter((k) => (e.dimensoes || {})[k]);
  const faltam = ['P1', 'P2', 'P3', 'P4'].filter((k) => !(e.dimensoes || {})[k]);
  const lista = (xs) => (xs.length === 1 ? xs[0] : `${xs.slice(0, -1).join(', ')} e ${xs[xs.length - 1]}`);
  if (!ks.length) return 'ainda sem medida';
  return `medido em ${ks.length === 4 ? 'P1 a P4' : lista(ks)}${faltam.length ? ` · faltam ${lista(faltam)}` : ''}`;
}
const daEntrega = (id) => centelhas().filter((c) => String(c.entrega_id) === String(id) && !c.descartada);
function botaoAcenderEntrega(e) {
  const conv = daEntrega(e.id).filter((c) => ['refletida', 'convertendo'].includes(c.estado)).sort((a, b) => b.lm - a.lm);
  if (conv.length) {
    return `<button class="btn acender" data-centelha="${esc(conv[0].id)}">Converter a luz desta entrega</button>
      <p class="dica">${plural(conv.length, 'centelha refletida apareceu aqui', 'centelhas refletidas apareceram aqui')} · ${conv.reduce((s, c) => s + c.lm, 0)} lm</p>`;
  }
  const lacunas = ['P3', 'P4'].filter((d) => !(e.dimensoes || {})[d]);
  if (!e.id || !lacunas.length) return '';
  return `<button class="btn sec" data-acender-entrega="${esc(e.id)}" title="Acende 2 centelhas curtas ligadas a esta entrega">${ic('raio', 'p')}Provar ${lacunas.join(' e ')}</button>`;
}
function cartaoEntrega(e) {
  const f = e.fatos || {};
  const aberta = entregasAbertas.has(String(e.id));
  const prismas = (e.prismas || []).map((p) => (typeof p === 'string' ? p : p.prisma)).map(nomeCurto);
  const ind = e.indice;
  const fatos = [plural(f.duracao_dias || 1, 'dia'), plural(f.commits ?? 1, 'commit'), plural(f.arquivos ?? 0, 'arquivo'), `+${numero(f.linhas ?? 0)} linhas`, prismas.join(', ')].filter(Boolean).join(' · ');
  const dims = ['P1', 'P2', 'P3', 'P4'].map((k) => {
    const d = (e.dimensoes || {})[k];
    if (!d) return `<div class="dim sem"><span class="n">${k} ${NOME_DIM[k]}</span><span class="v">—</span><span class="b">${FALTA_DIM[k]}</span></div>`;
    return `<div class="dim" title="${esc(`${d.tipo || ''}${d.base ? ` · ${d.base}` : ''}`)}"><span class="n">${k} ${NOME_DIM[k]}</span><span class="v">${d.nota}</span><span class="b">${esc(baseHumana(k, d))}</span></div>`;
  }).join('');
  return `<details class="entrega" data-entrega-id="${esc(e.id)}" ${aberta ? 'open' : ''}>
    <summary>
      <span class="er"><h3>${esc(e.titulo || e.tarefa)}</h3><p>${esc(fatos)}</p></span>
      <span class="prop">
        <span class="l1"><b>${ind == null ? '—' : `${ind}% seu`}</b><span><span class="abre">Ver detalhe ▾</span><span class="fecha">Fechar ▴</span></span></span>
        <span class="luz-barra" role="img" aria-label="${ind == null ? 'propriedade sem medida' : `${ind}% seu, ${100 - ind}% do agente`}">${ind == null ? '' : `<span class="p" style="width:${ind}%"></span><span class="r"></span>`}</span>
        <span class="medido">${esc(dimsMedidas(e))}</span>
      </span>
    </summary>
    <div class="detalhe">
      <div class="dims">${dims}</div>
      <div>
        ${blocoLeitura(e.leitura, `${plural(f.commits ?? 1, 'commit')}, ${plural(f.arquivos ?? 0, 'arquivo')}, ${plural(f.linhas ?? 0, 'linha')}`)}
        <div style="margin-top:20px">${botaoAcenderEntrega(e)}</div>
        <p class="discreto" style="margin-top:14px">${f.inicio ? `${esc(periodoCurto(f.inicio, f.fim))} · ` : ''}<button class="btn link mini" data-entrega-detalhe="${esc(e.id)}">Ver tudo</button></p>
      </div>
    </div>
  </details>`;
}
function semEntregas() {
  const d = E.entregas_diagnostico || {};
  const ids = (d.identidades || []).map(esc).join(', ') || 'nenhum';
  const janela = d.janela_desde ? `desde ${esc(dataCurta(d.janela_desde))} · ${plural(d.commits_seus ?? 0, 'commit seu', 'commits seus')}` : 'ainda não lida';
  return `<div class="vazio-bloco" style="text-align:left;align-items:flex-start">
    <b>Nenhuma entrega encontrada</b>
    <ul class="lista-simples"><li>Repositório: ${d.repo_configurado ? 'configurado' : 'não configurado (rode /luzia:triage)'}</li><li>E-mails do git: ${ids}</li><li>Janela: ${janela}</li></ul>
    <div class="acoes-bt"><button class="btn sec mini" data-ampliar-entregas="180">${ic('relogio', 'p')}Buscar 180 dias</button></div>
    <details class="recolhido"><summary>Adicionar e-mail do git</summary>
      <div class="pedido-ajuste"><label class="campos" style="display:block">Nome ou e-mail do git <input type="text" id="ent-identidade" maxlength="120" autocomplete="off"></label>
        <button class="btn sec mini" id="ent-identidade-salvar">Adicionar</button></div></details>
  </div>`;
}
function telaEntregas() {
  const lista = (E.entregas || []).map(cartaoEntrega).join('');
  $('#entregas').innerHTML = `
    <div class="cab-tela"><div><h2>Entregas</h2><p>Quanto de cada entrega é seu</p></div></div>
    ${bannerLeituras()}
    <details class="recolhido" style="margin:0 0 20px"><summary class="conta-link">Como medimos</summary>
      <div class="versoes">${(E.como_e_medido || []).map(esc).join('<br>')}<br>P3 e P4 só contam quando você explica ou defende a entrega, e isso converte as centelhas refletidas dela.</div></details>
    ${lista ? `${lista}<div style="text-align:center;margin-top:8px"><button class="btn sec mini" data-ampliar-entregas="180">${ic('relogio', 'p')}Buscar mais antigas</button></div>` : semEntregas()}`;
}

// ------------------------------------------------------------------ Ajustes
let provEscolhido = null;
function secaoModelo() {
  const m = E.modelo;
  if (!m) return '';
  const prov = provEscolhido || m.provedor;
  const info = m.provedores[prov];
  const atual = prov === m.provedor;
  const valor = atual ? m.modelo : (info.sugestoes[0] || '');
  const conhecido = info.sugestoes.includes(valor);
  return `<section><div class="titulo-sec"><h2>Modelo</h2><span>Em uso: ${esc(m.modelo)}</span></div>
    <div class="bloco"><div class="campos">
      <label>Provedor<select id="m-prov">${Object.entries(m.provedores).map(([k, v]) => `<option value="${k}" ${prov === k ? 'selected' : ''}>${esc(v.nome)} · ${v.chave_configurada ? 'com chave' : 'sem chave'}</option>`).join('')}</select></label>
      <label>Modelo<select id="m-select">${info.sugestoes.map((s) => `<option value="${esc(s)}" ${s === valor ? 'selected' : ''}>${esc(s)}</option>`).join('')}<option value="__outro" ${conhecido ? '' : 'selected'}>Outro…</option></select></label>
      <label ${conhecido ? 'hidden' : ''} id="m-outro-l">Nome exato<input id="m-outro" value="${conhecido ? '' : esc(valor)}" placeholder="nome exato do modelo"></label>
      ${info.base_url ? `<label>URL da API<input id="m-base" value="${esc(atual ? m.base_url : '')}" placeholder="ex.: http://localhost:11434/v1"></label>` : ''}
      <label>API key<input id="m-chave" type="password" autocomplete="off" placeholder="${info.chave_configurada ? 'Já salva. Deixe vazio para manter.' : 'Cole a chave'}"></label>
    </div>
    <div class="acoes-bt" style="margin-top:16px"><button class="btn neutro" id="m-salvar">Salvar</button><button class="btn sec" id="m-testar">Testar</button>
      <span class="discreto">Fica só nesta máquina, fora do git.${atual && !m.sdk_instalado ? ` Falta o SDK: pip install ${esc(m.pip)}` : ''}</span></div></div></section>`;
}
function telaAjustes() {
  const opcao = (grupo, chave, [icone, titulo, desc], ativo) =>
    `<button class="opcao" data-${grupo}="${chave}" aria-pressed="${!!ativo}">${ic(icone)}<span><b>${titulo}</b><small>${desc}</small></span></button>`;
  const ex = E.execucao || {};
  const mascarar = !!E.privacidade?.mascarar_modelo;
  $('#ajustes').innerHTML = `<div class="ajustes">
    <h2 style="font-size:26px">Ajustes</h2>
    <section><div class="titulo-sec"><h2>Foco</h2></div><div class="opcoes">${Object.entries(MODOS).map(([k, v]) => opcao('modo', k, v, E.modo === k)).join('')}</div></section>
    ${secaoModelo()}
    <section><div class="titulo-sec"><h2>Agente</h2></div><div class="opcoes">${Object.entries(AGENTES).map(([k, [t, d]]) => opcao('agente', k, ['agente', t, d], E.agente === k)).join('')}</div></section>
    <section><div class="titulo-sec"><h2>O que vai para o modelo</h2></div>
      <div class="opcoes">${opcao('privacidade', 'off', ['olho', 'Dados reais', 'Padrão'], !mascarar)}${opcao('privacidade', 'on', ['info', 'Mascarar', 'E-mails, tickets e nomes viram marcadores'], mascarar)}</div>
      ${mascarar && !E.privacidade?.termos ? '<p class="aviso fino" style="margin-top:12px">Liste empresa e clientes em termos.txt, na pasta de dados da Luzia.</p>' : ''}
      <p class="dica">Vale só para as chamadas da Luzia. Seu agente vê os dados reais.</p></section>
    <section><div class="titulo-sec"><h2>Sobre</h2></div>
      <dl class="sobre-lista"><dt>Versão</dt><dd>${esc(ex.versao || '—')}</dd>
        <dt>Última chamada</dt><dd>${ex.tempo_total_s ? `${esc(ex.tempo_total_s)} s · ${esc(ex.pico_memoria_mib)} MiB · ${esc(ex.tokens_entrada)}→${esc(ex.tokens_saida)} tokens` : '—'}</dd>
        <dt>Modelo da última chamada</dt><dd>${esc(ex.modelo || '—')}${ex.quando ? ` · ${esc(dataCurta(ex.quando, true))}` : ''}</dd></dl></section>
    <p class="so-celular"><button class="btn link" id="sair-celular">Sair</button></p>
  </div>`;
}

// ------------------------------------------------------------------ gavetas
function abrirGaveta(html) {
  $('#gaveta-corpo').innerHTML = `<button class="fechar" data-fechar aria-label="Fechar">${ic('fechar')}</button>${html}`;
  $('#gaveta').hidden = false;
  $('#gaveta-corpo').focus();
}
function guiaPadrao(c) {
  if (c.estado === 'propria') return [c.porque || 'Você mostrou que entende este conceito.'];
  if (c.estado === 'apagada') return ['A Luzia explica o conceito com um exemplo do seu projeto.', 'Você aplica numa tarefa curta com o agente.', 'Você explica a escolha em 2 frases, e a luz já nasce própria.'];
  return [`A Luzia abre ${c.onde ? `o trecho de ${c.onde}` : 'o trecho'} em que o agente aplicou o conceito.`,
    'Você explica, com suas palavras, o que o agente fez e por quê; a Luzia pergunta o que faltar.',
    'Com nota 3 ou 4, a Luzia confirma o entendimento. Com o seu sim, a luz vira sua.'];
}
function abrirCentelha(id) {
  const c = cPorId(id);
  if (!c) return;
  const a = aPorId(id) || {};
  const p = pLuz(c.prisma) || { pct: 0, tot: 0, propria: 0, lista: [] };
  const depois = pctDepois(p, c);
  const guia = c.guia && c.guia.length && c.estado !== 'propria' ? c.guia : guiaPadrao(c);
  const guiaTitulo = c.estado === 'propria' ? 'Como você conquistou' : c.estado === 'apagada' ? 'Como a Luzia acende' : 'Como a Luzia guia a conversão';
  const conta = (c.conta || []).map(([n, d, v]) => `<div><span>${esc(n)} <small class="discreto">(${esc(d)})</small></span><b>+${v}</b></div>`).join('');
  const hist = (a.historico || []).slice(-6).reverse().map((h) => `<li>${esc(dataCurta(h.quando))} · ${esc(h.evento)}${h.nota != null ? ` · nota ${h.nota} de 4` : ''}${h.lm ? ` · ${h.lm} lm` : ''}${h.motivo ? ` · ${esc(h.motivo)}` : ''}${h.onde ? ` · ${esc(h.onde)}` : ''}</li>`).join('');
  const motivos = Object.entries(E.regras?.motivos || {}).map(([k, v]) => `<button data-descartar="${esc(c.id)}" data-motivo="${esc(k)}">${esc(cap(v))}</button>`).join('');
  let acao;
  if (c.estado === 'propria') {
    acao = `<div class="ja-sua">${orbe('propria')}Esta luz já é sua · +${c.lm} lm em ${curto(c.prisma)}</div>`;
  } else if (c.estado === 'descartada') {
    acao = `<button class="btn sec" data-restaurar="${esc(c.id)}">${ic('restaurar', 'p')}Restaurar</button>`;
  } else if (c.estado === 'convertendo' && c.confirmada) {
    acao = `<button class="btn acender" data-confirmar="${esc(c.id)}">Acender luz própria</button>
      <p class="dica">A Luzia confirmou seu entendimento${c.nota != null ? ` (nota ${c.nota} de 4)` : ''}. Falta só o seu sim.</p>`;
  } else {
    const dica = c.estado === 'apagada'
      ? `Abre na sua próxima mensagem no chat, ou digite /luzia:fazer ${c.id}.`
      : `A Luzia abre o contexto${c.onde ? ` de ${c.onde}` : ''} e guia você até a luz virar própria. No chat: /luzia:converter ${c.id}.`;
    acao = `<div class="acoes-bt"><button class="btn acender" data-enviar="${esc(c.id)}" ${c.na_fila ? 'disabled' : ''}>${esc(rotuloAcao(c))}</button>
      <button class="btn sec" data-copiar="${esc(c.id)}">${ic('copiar', 'p')}Copiar prompt</button></div>
      <p class="dica">${esc(dica)}</p>
      ${c.tentativas && a.dica ? `<p class="dica">Na última tentativa faltou: ${esc(a.dica)}</p>` : ''}`;
  }
  abrirGaveta(`
    <div class="estado-l cor-${esc(c.estado)}">${orbe(c.estado)}${esc(rotuloEstado(c))}${origemTxt(c) ? ` · ${esc(origemTxt(c))}` : ''}</div>
    <h2>${esc(c.titulo)}</h2>
    <p>${esc(c.porque || a.por_que || '')}</p>
    <div class="caixa">
      <div class="l1"><span>Prisma <b title="${esc(c.prisma)}">${curto(c.prisma)}</b></span><span>${c.estado === 'propria' ? `${p.pct}% seu` : `${p.pct}% → ${depois}% seu`}</span></div>
      ${segs(p.lista || [], { foco: c.id, rotulo: ariaPrisma({ ...p, nome: c.prisma }) })}
      ${c.onde ? `<p class="onde">Apareceu em <b>${esc(c.onde)}</b></p>` : ''}
    </div>
    ${acao}
    <h4>${guiaTitulo}</h4><ol class="guia">${guia.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
    <details class="recolhido" open><summary>Por que ${c.lm} lm ${ic('baixo', 'p')}</summary>
      <div class="conta">${conta}<div class="total"><span>Valor da centelha · fixo desde que nasceu</span><span>${c.lm} lm</span></div></div></details>
    ${a.prompt_completo ? `<details class="recolhido"><summary>Ver prompt ${ic('baixo', 'p')}</summary><pre class="prompt">${esc(a.prompt_completo)}</pre></details>` : ''}
    ${hist ? `<details class="recolhido"><summary>Histórico ${ic('baixo', 'p')}</summary><ul class="lista-simples">${hist}</ul></details>` : ''}
    ${['propria', 'descartada'].includes(c.estado) ? '' : `<details class="recolhido"><summary class="discreto">Descartar…</summary><div class="motivos">${motivos}</div></details>`}`);
}
function abrirPrisma(nome) {
  const p = pLuz(nome);
  const base = (E.prismas || []).find((x) => x.nome === nome) || {};
  if (!p) return;
  const px = cPorId(p.proxima);
  const temSub = nomeCurto(nome) !== nome;
  abrirGaveta(`
    <div class="prisma-g">${tri(p, true)}<span><small>Prisma</small><h2>${curto(nome)}</h2>${temSub ? `<small>${esc(nome)}</small>` : ''}</span></div>
    <div class="pct-g"><b>${p.pct}%</b><span>é luz própria · ${p.propria} de ${p.tot} lm</span></div>
    ${segs(p.lista || [], { classe: 'grossa', rotulo: ariaPrisma(p) })}
    <p class="resumo ${p.n_converter ? 'converter' : ''}" style="margin-top:10px">${esc(resumoPrisma(p))}</p>
    ${px ? `<p style="margin-top:18px"><button class="btn acender" data-centelha="${esc(px.id)}">${px.estado === 'apagada' ? 'Acender a próxima' : 'Converter a próxima'} · +${px.lm} lm</button></p>` : ''}
    <h4>Centelhas da meta</h4>
    ${(p.lista || []).length ? `<ul class="lista-c">${p.lista.map(itemLista).join('')}</ul>` : '<p class="vazio">Nenhuma centelha ainda.</p>'}
    ${p.na_meta ? '' : `<p style="margin-top:14px"><button class="btn sec mini" data-acender="${esc(nome)}">${ic('raio', 'p')}Acender 3 centelhas</button></p>`}
    <h4>Análise</h4>
    ${blocoLeitura(base.leitura, `${p.propria} de ${p.tot} lm em luz própria, ${plural(p.n, 'centelha')}`, true)}
    ${base.evidencia ? `<details class="recolhido"><summary>Evidência da triagem ${ic('baixo', 'p')}</summary>${blocoLeitura({ texto: base.evidencia, alvo_tipo: 'triagem', modelo: E.triagem_modelo?.modelo || 'modelo desconhecido', criado_em: E.triagem_modelo?.quando || '' }, `triagem: currículo, commits e histórico autorizados${E.triagem_modelo?.mascarado ? ' (mascarados antes do envio ao modelo)' : ''}`)}</details>` : ''}`);
}
function abrirLumen(i) {
  const l = (E.lumens || [])[i];
  if (!l) return;
  const propria = l.luz !== 'refletida';
  const texto = {
    agente: 'O código que o agente escreveu aplica este conceito. Foi ele quem aplicou, então a centelha acendeu como luz refletida: ainda não prova que você domina.',
    prompt: 'No seu pedido ao agente você dirigiu este conceito. Quando é você quem aponta o caminho, a centelha vira luz própria.',
    acesa: 'Você acendeu uma centelha: a Luzia confirmou o entendimento e você deu o sim.',
    conversao: 'Você explicou o que o agente tinha aplicado. A Luzia confirmou, e a luz refletida virou sua.',
  }[l.fonte] || 'A Luzia reconheceu esta luz pelas regras do jogo.';
  abrirGaveta(`
    <div class="estado-l ${propria ? 'cor-propria' : 'cor-refletida'}">${orbe(propria ? 'propria' : 'refletida')}${propria ? 'Luz própria' : 'Luz refletida'}</div>
    <h2>+${l.lm} lm · ${esc(cap(FONTES[l.fonte] || 'luz'))}</h2>
    <p>${esc(texto)}</p>
    <div class="caixa"><div class="l1"><span>Prisma <b>${curto(l.skill)}</b></span><span>${esc(dataCurta(l.quando, true))} ${esc(String(l.quando || '').slice(11, 16))}</span></div></div>
    ${l.ref && cPorId(l.ref) ? `<button class="btn sec" data-centelha="${esc(l.ref)}">Abrir a centelha</button>` : ''}
    <p class="dica">Cada centelha muda de luz uma vez só: repetir o conceito não soma de novo.</p>`);
}
async function abrirEntregaDetalhe(id) {
  const det = await api(`/api/entrega?id=${encodeURIComponent(id)}`);
  if (det.erro) {
    toast(det.erro, 'neutro');
    return;
  }
  const f = det.fatos || {};
  const tags = (det.prismas || []).map((p) => `<span class="tag refl" title="${esc(p.prisma)}">${curto(p.prisma)}${(p.termos || []).length ? ` · ${p.termos.map(esc).join(', ')}` : ''}</span>`).join('') || '<span class="vazio">Nenhum prisma nos caminhos ou mensagens.</span>';
  const ligadas = daEntrega(det.id);
  abrirGaveta(`
    <div class="estado-l">Entrega #${esc(det.id)}</div>
    <h2>${esc(det.titulo)}</h2>
    <div class="tags"><span class="tag">${esc(det.fonte || 'git')}</span>${(det.ids || []).map((i) => `<span class="tag">#${esc(i)}</span>`).join('')}
      <span class="tag">${esc(periodoCurto(f.inicio, f.fim) || '—')} · ${plural(f.duracao_dias || 1, 'dia')}</span><span class="tag">${plural(f.commits || 1, 'commit')}</span>
      <span class="tag">${plural(f.arquivos || 0, 'arquivo')}</span><span class="tag">+${numero(f.linhas || 0)} linhas</span>${(f.areas || []).map((ar) => `<span class="tag">${esc(ar)}</span>`).join('')}</div>
    <h4>Prismas</h4><div class="tags">${tags}</div>
    <h4>Análise</h4>${blocoLeitura(det.leitura, `${plural(f.commits ?? 1, 'commit')}, ${plural(f.arquivos ?? 0, 'arquivo')}, ${plural(f.linhas ?? 0, 'linha')}`, true)}
    <h4>Centelhas desta entrega · ${ligadas.length}</h4>
    ${ligadas.length ? `<ul class="lista-c">${ligadas.map(itemLista).join('')}</ul>` : '<p class="vazio">Nenhuma centelha ligada ainda.</p>'}
    <h4>Luz no período · ${(det.lumens_ligados || []).length}</h4>
    ${(det.lumens_ligados || []).length ? `<ul class="lista-simples">${det.lumens_ligados.map((l) => `<li>${l.luz === 'refletida' ? 'refletida' : 'própria'} · ${l.lm} lm · ${curto(l.prisma || l.skill)} · ${esc(FONTES[l.fonte] || l.fonte)} · ${esc(dataCurta(l.quando))}</li>`).join('')}</ul>` : '<p class="vazio">Nenhum lúmen no período desta entrega.</p>'}`);
}

// ------------------------------------------------------------------ conversão confirmada: o momento da luz própria
function renderConquista() {
  const el = $('#conquista');
  if (!conquista) {
    el.hidden = true;
    el.innerHTML = '';
    return;
  }
  const c = cPorId(conquista.id) || conquista.c;
  const r = conquista.r || {};
  const p = pLuz(c.prisma) || { pct: 0, lista: [] };
  const virou = conquista.fase === 'virou';
  const antes = virou ? r.pct_antes : p.pct;
  const depois = virou ? r.pct_depois : pctDepois(p, c);
  const proxima = centelhas().find((x) => ['convertendo', 'refletida'].includes(x.estado) && x.id !== c.id);
  el.className = `conquista ${virou ? 'virou' : ''}`;
  el.innerHTML = `<div class="caixa-c">
    <div class="orbe-grande" aria-hidden="true"><div class="r"></div><div class="p"></div><div class="n"><b>+${c.lm}</b><span>lm</span></div></div>
    <div class="sub">${curto(c.prisma)} · ${esc(c.titulo)}</div>
    <h2 id="cq-titulo">${virou ? 'Agora a luz é sua' : 'Pronta para virar sua'}</h2>
    <p>${virou ? `Você mostrou que entende. ${c.lm} lm de ${esc(nomeCurto(c.prisma))} viraram luz própria.${r.marco ? ` Marco ${r.marco.n} de 3: dossiê gerado.` : ''}`
      : `Na conversa você explicou o conceito, e a Luzia confirmou o entendimento${c.nota != null ? ` (nota ${c.nota} de 4)` : ''}.`}</p>
    <div class="barra-c"><div class="l1"><b>${curto(c.prisma)}</b><span>${virou ? `${antes}% → ${depois}% seu` : `${antes}% seu`}</span></div>${segs(p.lista || [], { foco: virou ? '' : c.id })}</div>
    <div class="acoes-bt" style="justify-content:center">
      ${virou
        ? `${proxima ? `<button class="btn acender" data-cq-proxima="${esc(proxima.id)}">Converter a próxima</button>` : ''}<button class="btn sec" data-cq-fechar="1">Fechar</button>`
        : `<button class="btn acender" data-cq-confirmar="${esc(c.id)}">Acender luz própria</button><button class="btn sec" data-cq-fechar="1">Agora não</button>`}
    </div></div>`;
  el.hidden = false;
  el.querySelector('.btn')?.focus();
}
function fecharConquista() {
  conquista = null;
  renderConquista();
}

// ------------------------------------------------------------------ carregar, render e navegação
let leiturasAutoPedidas = false;
function leiturasAutomaticas() {
  if (leiturasAutoPedidas || !E || !E.modelo_pronto || !(E.leituras_vencidas > 0)) return;
  leiturasAutoPedidas = true;
  api('/api/leituras', { auto: true }, true).then(async (r) => {
    if (r.erro || !r.geradas) return;
    toast(plural(r.geradas, 'análise atualizada', 'análises atualizadas'), 'neutro');
    await carregar(true);
  });
}

// Antes da triagem: o painel já abre, mostra os primeiros passos e deixa configurar o modelo.
function telaBoasVindas() {
  $('#nav').innerHTML = '';
  $('#nav-baixo').innerHTML = '';
  $('#hoje').innerHTML = `<div class="vazio-destaque">
    <span class="sobre-linha">Olá, eu sou a Luzia</span>
    <h1>Vamos montar a sua trajetória</h1>
    <ol class="guia">
      <li>Configure o modelo aqui embaixo (ex.: Gemini, com a sua chave). A chave fica só nesta máquina.</li>
      <li>No chat do seu agente, rode <b>/luzia:triage</b>. Eu leio o currículo, o git e o histórico que você autorizar.</li>
      <li>Volte aqui: as centelhas da sua meta aparecem em Hoje.</li>
    </ol>
  </div>
  <div style="margin-top:32px">${E.modelo ? secaoModelo() : ''}</div>`;
  irPara('hoje');
}

async function carregar(auto = false) {
  const tela = document.querySelector('.tela.ativa')?.id || 'hoje';
  const novo = await api('/api/estado', null, auto);
  if (novo.login) return;  // a tela de entrada já está aberta
  if (novo.erro) {
    toast(novo.erro, 'neutro');
    if (E) return;
    $('#hoje').innerHTML = `<div class="vazio-destaque"><h1>Não carregou</h1><p class="lacuna">Tente de novo pelo chat. <small>(${esc(novo.erro)})</small></p></div>`;
    return;
  }
  E = novo;
  if (E.vazio) {
    telaBoasVindas();
    return;
  }
  render(tela);
  leiturasAutomaticas();
}

function render(tela = document.querySelector('.tela.ativa')?.id || 'hoje') {
  cabecalho();
  telaHoje();
  telaTrajetoria();
  telaCentelhas();
  telaEntregas();
  telaAjustes();
  irPara(TELAS.some(([id]) => id === tela) ? tela : 'hoje');
  if (conquista) renderConquista();
}

function irPara(tela) {
  const destino = { rota: 'trajetoria', avancos: 'centelhas', feixes: 'centelhas', propria: 'entregas' }[tela] || tela;
  document.querySelectorAll('[data-tela]').forEach((b) => {
    if (b.dataset.tela === destino) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
  });
  document.querySelectorAll('.tela').forEach((s) => s.classList.toggle('ativa', s.id === destino));
}

// ------------------------------------------------------------------ eventos
const SELETOR = [
  '[data-tela]', '[data-ir]', '[data-centelha]', '[data-prisma]', '[data-lumen]', '[data-enviar]', '[data-copiar]',
  '[data-confirmar]', '[data-cq-confirmar]', '[data-cq-fechar]', '[data-cq-proxima]', '[data-descartar]', '[data-restaurar]',
  '[data-fechar]', '[data-filtro-estado]', '[data-filtro-ir]', '[data-limpar-filtros]', '[data-modo]', '[data-agente]',
  '[data-privacidade]', '#m-salvar', '#m-testar', '[data-acender]', '[data-gerar-leituras]', '[data-ampliar-entregas]',
  '[data-acender-entrega]', '[data-entrega-detalhe]', '#ent-identidade-salvar', '[data-abrir-pedido-form]', '#ped-enviar',
  '[data-pedido-aceitar]', '[data-pedido-recusar]', '[data-dividir-prisma]', '[data-dividir-todos]', '[data-pedido-dividir-ajustar]',
  '[data-reativar-prisma]', '#sair-celular',
].join(',');

async function aoClicar(t, ev) {
  const ds = t.dataset;
  if (t.closest('summary') && t.tagName === 'BUTTON') ev.preventDefault();  // botões no resumo da entrega não abrem/fecham

  if (ds.tela || ds.ir) {
    $('#gaveta').hidden = true;
    return irPara(ds.tela || ds.ir);
  }
  if (ds.filtroIr) {
    filtroEstado = ds.filtroIr;
    telaCentelhas();
    return irPara('centelhas');
  }
  if (ds.centelha) return abrirCentelha(ds.centelha);
  if (ds.prisma) return abrirPrisma(ds.prisma);
  if (ds.lumen !== undefined) return abrirLumen(Number(ds.lumen));
  if (ds.fechar !== undefined) {
    $('#gaveta').hidden = true;
    return;
  }
  if (ds.enviar) {
    t.disabled = true;
    const r = await api('/api/enviar', { id: ds.enviar });
    const c = cPorId(ds.enviar);
    toast(r.erro ? `Não enviou: ${r.erro}` : (c?.estado === 'apagada' ? `Na fila do ${nomeAgente()}` : `A Luzia guia a conversão no ${nomeAgente()}`), r.erro ? 'neutro' : '');
    await carregar();
    if (!$('#gaveta').hidden) abrirCentelha(ds.enviar);
    return;
  }
  if (ds.copiar) {
    const a = aPorId(ds.copiar);
    try {
      await navigator.clipboard.writeText(a?.prompt_completo || '');
    } catch {
      toast('Não copiou: o navegador bloqueou a área de transferência', 'neutro');
      return;
    }
    const r = await api('/api/iniciar', { id: ds.copiar });
    toast(r.erro ? `Copiado, mas: ${r.erro}` : 'Prompt copiado. Cole no chat.', 'neutro');
    await carregar();
    if (!$('#gaveta').hidden) abrirCentelha(ds.copiar);
    return;
  }
  if (ds.confirmar) {
    $('#gaveta').hidden = true;
    conquista = { id: ds.confirmar, fase: 'pronta', c: cPorId(ds.confirmar) };
    return renderConquista();
  }
  if (ds.cqConfirmar) {
    t.disabled = true;
    const r = await api('/api/confirmar', { id: ds.cqConfirmar });
    if (r.erro) {
      fecharConquista();
      toast(`Ainda não: ${r.erro}`, 'neutro');
      return carregar();
    }
    conquista = { ...conquista, fase: 'virou', r };
    await carregar();
    return renderConquista();
  }
  if (ds.cqFechar) return fecharConquista();
  if (ds.cqProxima) {
    fecharConquista();
    return abrirCentelha(ds.cqProxima);
  }
  if (ds.descartar) {
    const id = ds.descartar;
    const r = await api('/api/descartar', { id, motivo: ds.motivo });
    $('#gaveta').hidden = true;
    toast(r.erro ? `Não descartou: ${r.erro}` : 'Descartada', 'neutro', r.erro ? null : { rotulo: 'Desfazer', dados: { restaurar: id } });
    return carregar();
  }
  if (ds.restaurar) {
    await api('/api/restaurar', { id: ds.restaurar });
    $('#gaveta').hidden = true;
    toast('Restaurada', 'neutro');
    return carregar();
  }
  if (ds.filtroEstado) {
    filtroEstado = ds.filtroEstado;
    return telaCentelhas();
  }
  if (ds.limparFiltros) {
    filtroEstado = 'todas';
    filtroPrisma = 'todos';
    filtroTipo = 'todos';
    return telaCentelhas();
  }
  if (ds.modo) {
    const r = await api('/api/modo', { modo: ds.modo });
    toast(r.erro ? `Não salvou: ${r.erro}` : `Foco: ${MODOS[ds.modo]?.[1] || ds.modo}`, 'neutro');
    return carregar();
  }
  if (ds.agente) {
    await api('/api/agente', { agente: ds.agente });
    toast(`Agente: ${AGENTES[ds.agente]?.[0] || ds.agente}`, 'neutro');
    return carregar();
  }
  if (ds.privacidade) {
    const r = await api('/api/privacidade', { mascarar_modelo: ds.privacidade === 'on' });
    toast(r.erro ? `Não salvou: ${r.erro}` : (r.mascarar_modelo ? 'Mascarando' : 'Enviando dados reais'), 'neutro');
    return carregar();
  }
  if (t.id === 'm-salvar') {
    const sel = $('#m-select').value;
    const r = await api('/api/modelo', {
      provedor: provEscolhido || E.modelo.provedor,
      modelo: sel === '__outro' ? $('#m-outro').value : sel,
      base_url: $('#m-base')?.value || '',
      chave: $('#m-chave').value,
    });
    toast(r.erro ? `Não salvou: ${r.erro}` : 'Modelo salvo', 'neutro');
    if (!r.erro) {
      provEscolhido = null;
      carregar();
    }
    return;
  }
  if (t.id === 'm-testar') {
    toast('Testando…', 'neutro');
    const r = await api('/api/modelo/testar', {});
    toast(r.erro ? `Falhou: ${r.erro}` : (r.aviso ? `Atenção: ${r.aviso}` : `Respondeu em ${String(r.segundos).replace('.', ',')} s`), 'neutro');
    return;
  }
  if (t.id === 'sair-celular') return sair();
  if (ds.acender) {
    t.disabled = true;
    toast('Acendendo…', 'neutro');
    const r = await api('/api/acender', { prisma: ds.acender });
    toast(r.erro ? `Não acendeu: ${r.erro}` : `${plural((r.avancos || []).length, 'centelha nova', 'centelhas novas')} · ${nomeCurto(ds.acender)}`, r.erro ? 'neutro' : '');
    await carregar();
    if (!$('#gaveta').hidden && !r.erro) abrirPrisma(r.prisma || r.skill || ds.acender);
    return;
  }
  if (ds.gerarLeituras) {
    t.disabled = true;
    toast('Atualizando análises…', 'neutro');
    const r = await api('/api/leituras', {});
    toast(r.erro ? `Falhou: ${r.erro}` : (r.geradas ? plural(r.geradas, 'análise atualizada', 'análises atualizadas')
      : (E && E.modelo_pronto ? 'Nada gravado: já em dia ou o modelo não respondeu' : 'Sem modelo: configure em Ajustes')), 'neutro');
    return carregar();
  }
  if (ds.ampliarEntregas) {
    t.disabled = true;
    toast('Buscando…', 'neutro');
    const r = await api('/api/entregas/ampliar', { dias: Number(ds.ampliarEntregas) || 180 });
    toast(r.erro ? `Falhou: ${r.erro}` : plural(r.atualizacao?.novas ?? 0, 'entrega nova', 'entregas novas'), 'neutro');
    return carregar();
  }
  if (ds.acenderEntrega) {
    t.disabled = true;
    toast('Acendendo…', 'neutro');
    const r = await api('/api/entrega/acender', { id: Number(ds.acenderEntrega) });
    toast(r.erro ? `Não acendeu: ${r.erro}` : `${plural((r.avancos || []).length, 'centelha ligada', 'centelhas ligadas')} à entrega`, r.erro ? 'neutro' : 'refletida');
    return carregar();
  }
  if (ds.entregaDetalhe) return abrirEntregaDetalhe(ds.entregaDetalhe);
  if (t.id === 'ent-identidade-salvar') {
    const identidade = ($('#ent-identidade')?.value || '').trim();
    if (!identidade) return toast('Informe um nome ou e-mail dos seus commits.', 'neutro');
    t.disabled = true;
    const r = await api('/api/identidade', { identidade });
    if (r.erro) {
      t.disabled = false;
      return toast(`Não adicionou: ${r.erro}`, 'neutro');
    }
    toast('Buscando…', 'neutro');
    const amp = await api('/api/entregas/ampliar', { dias: 90 });
    toast(amp.erro ? `Falhou: ${amp.erro}` : plural(amp.atualizacao?.novas ?? 0, 'entrega nova', 'entregas novas'), 'neutro');
    return carregar();
  }
  if (ds.abrirPedidoForm !== undefined) {
    mostrarFormPedido = ds.abrirPedidoForm === '1';
    return telaTrajetoria();
  }
  if (t.id === 'ped-enviar') {
    const tipo = $('#ped-tipo')?.value || 'incluir';
    const prisma = ($('#ped-prisma')?.value || '').trim();
    const motivo = ($('#ped-motivo')?.value || '').trim();
    if (!prisma) return toast('Informe o nome do prisma.', 'neutro');
    t.disabled = true;
    toast('A Luzia está analisando…', 'neutro');
    const r = await api('/api/pedido', { acao: 'abrir', tipo, prisma, motivo });
    if (!r.erro) mostrarFormPedido = false;
    toast(r.erro ? `Não abriu: ${r.erro}` : 'Proposta pronta: confira abaixo', 'neutro');
    return carregar();
  }
  if (ds.pedidoAceitar) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'aceitar', id: Number(ds.pedidoAceitar) });
    toast(r.erro ? `Erro: ${r.erro}` : `Trajetória atualizada${r.pedido?.versao ? ` · v${r.pedido.versao}` : ''}`, 'neutro');
    return carregar();
  }
  if (ds.pedidoRecusar) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'recusar', id: Number(ds.pedidoRecusar) });
    toast(r.erro ? `Erro: ${r.erro}` : 'Pedido recusado', 'neutro');
    return carregar();
  }
  if (ds.dividirPrisma || ds.dividirTodos) {
    t.disabled = true;
    const r = ds.dividirPrisma
      ? await api('/api/pedido', { acao: 'abrir', tipo: 'dividir', prisma: ds.dividirPrisma, motivo: 'um prisma por habilidade' })
      : await api('/api/pedido', { acao: 'dividir_todos' });
    toast(r.erro ? `Erro: ${r.erro}` : 'Divisão proposta: confira em Trajetória', 'neutro');
    return carregar();
  }
  if (ds.pedidoDividirAjustar) {
    t.disabled = true;
    const pid = ds.pedidoDividirAjustar;
    const campos = [...document.querySelectorAll(`[data-div-parte="${pid}"]`)];
    const partes = campos.map((i) => i.value.trim()).filter(Boolean);
    const antes = campos.map((i) => i.defaultValue);
    const mover = {};
    document.querySelectorAll(`[data-div-mover="${pid}"]`).forEach((s) => { mover[s.dataset.avancoId] = s.value; });
    Object.keys(mover).forEach((k) => { const i = antes.indexOf(mover[k]); if (i >= 0 && partes[i]) mover[k] = partes[i]; });
    const r = await api('/api/pedido', { acao: 'ajustar', id: Number(pid), partes, mover });
    toast(r.erro ? `Erro: ${r.erro}` : 'Divisão ajustada', 'neutro');
    return carregar();
  }
  if (ds.reativarPrisma) {
    t.disabled = true;
    const r = await api('/api/pedido', { acao: 'abrir', tipo: 'reativar', prisma: ds.reativarPrisma, motivo: 'Reativado pelo painel' });
    toast(r.erro ? r.erro : 'Pedido aberto: aceite em Trajetória', 'neutro');
    return carregar();
  }
  return undefined;
}

document.addEventListener('click', (ev) => {
  const t = ev.target.closest(SELETOR);
  if (t) aoClicar(t, ev);
});
document.addEventListener('change', (ev) => {
  if (ev.target.id === 'm-select') $('#m-outro-l').hidden = ev.target.value !== '__outro';
  if (ev.target.id === 'm-prov') {
    provEscolhido = ev.target.value;
    if (E.vazio) telaBoasVindas(); else telaAjustes();
  }
  if (ev.target.id === 'ped-tipo') {
    tipoPedidoForm = ev.target.value;
    telaTrajetoria();
  }
  if (ev.target.matches('[data-filtro-select]')) {
    if (ev.target.dataset.filtroSelect === 'prisma') filtroPrisma = ev.target.value;
    else filtroTipo = ev.target.value;
    telaCentelhas();
    $(`[data-filtro-select="${ev.target.dataset.filtroSelect}"]`)?.focus();
  }
});
// Esc fecha a sobreposição ("Agora não") ou a gaveta; Tab fica preso dentro do diálogo aberto.
document.addEventListener('keydown', (ev) => {
  const dialogo = conquista ? $('#conquista') : (!$('#gaveta').hidden ? $('#gaveta-corpo') : null);
  if (ev.key === 'Escape') {
    if (conquista) fecharConquista(); else $('#gaveta').hidden = true;
    return;
  }
  if (ev.key !== 'Tab' || !dialogo) return;
  const focaveis = [...dialogo.querySelectorAll('button, [href], input, select, summary, [tabindex="0"]')].filter((x) => !x.disabled && x.offsetParent !== null);
  if (!focaveis.length) return;
  const primeiro = focaveis[0];
  const ultimo = focaveis[focaveis.length - 1];
  if (ev.shiftKey && document.activeElement === primeiro) {
    ev.preventDefault();
    ultimo.focus();
  } else if (!ev.shiftKey && document.activeElement === ultimo) {
    ev.preventDefault();
    primeiro.focus();
  }
});
// Detalhe de entrega aberto/fechado: guardado por id para o polling não fechar o que a pessoa abriu.
document.addEventListener('toggle', (ev) => {
  const d = ev.target;
  if (!d.matches || !d.matches('details.entrega')) return;
  if (d.open) entregasAbertas.add(d.dataset.entregaId); else entregasAbertas.delete(d.dataset.entregaId);
}, true);

// ------------------------------------------------------------------ acesso (entrada herdada do agente)
// O painel abre pelo agente (`career-map`) com um link de uso único no fragmento (#entrar=...), que nunca vai ao
// servidor nem ao Referer: a página o tira da barra e do histórico e o troca por uma sessão de 30 dias (cookie
// HttpOnly que o JS não vê). Nenhum dado é buscado antes de haver sessão; qualquer 401 traz de volta a tela de entrada
// e para o polling. Nada fica guardado no navegador.
const COMANDO_PAINEL = '/luzia:career-map';
let polling = null;
let acessoAberto = false;

function pararPolling() {
  clearInterval(polling);
  polling = null;
}

function limparPainel() {
  pararPolling();
  E = null;
  conquista = null;
  leiturasAutoPedidas = false;
  entregasAbertas.clear();
  $('#gaveta').hidden = true;
  $('#gaveta-corpo').innerHTML = '';
  $('#conquista').hidden = true;
  document.querySelectorAll('.tela').forEach((s) => (s.innerHTML = ''));
  $('#nav').innerHTML = '';
  $('#nav-baixo').innerHTML = '';
}

function linkDaBarra() {
  const m = /^#entrar=([\w-]{20,256})$/.exec(location.hash || '');
  if (location.hash) history.replaceState(null, '', location.pathname);  // o token sai da barra e do histórico
  return m ? m[1] : null;
}

async function acessoAoIniciar() {
  if (acessoAberto) return;
  acessoAberto = true;
  limparPainel();
  document.body.classList.add('fora');
  const token = linkDaBarra();
  let aviso = '';
  if (token) {
    const r = await api('/api/acesso/link', { token });
    if (!r.erro) return entrou();
    aviso = r.erro;
  }
  const st = await api('/api/acesso/estado');
  if (st.erro) {
    aviso = st.erro;
  } else if (st.sessao_valida) {
    return entrou();
  }
  telaAcesso(aviso);
}

function telaAcesso(aviso = '') {
  $('#acesso').innerHTML = `<div class="acesso-cartao">
    <div class="marca"><svg viewBox="0 0 64 64" aria-hidden="true"><polygon points="32,3 25,25 3,32 25,39 32,61" fill="#b9a2f2"/><polygon points="32,3 39,25 61,32 39,39 32,61" fill="#f08a3c"/></svg><b>Luzia</b></div>
    <h3>Abra pelo seu agente</h3>
    <p class="lacuna">Rode no chat. A sessão dura 30 dias neste navegador.</p>
    <div class="acoes-bt"><code>${COMANDO_PAINEL}</code><button class="btn neutro" type="button" id="ac-copiar">Copiar</button></div>
    <p class="dica acesso-msg" role="alert">${esc(aviso)}</p>
    <p class="dica">Só quem usa o seu agente nesta máquina entra.</p>
  </div>`;
}

async function entrou() {
  acessoAberto = false;
  $('#acesso').innerHTML = '';
  document.body.classList.remove('fora');
  await carregar();
  if (E && !polling) polling = setInterval(atualizarSozinho, 4000);
}

async function sair() {
  await api('/api/acesso/sair', {});
  toast('Você saiu neste navegador.', 'neutro');
  acessoAoIniciar();
}

document.addEventListener('click', async (ev) => {
  if (ev.target.closest('#ac-copiar')) {
    try {
      await navigator.clipboard.writeText(COMANDO_PAINEL);
      toast('Copiado. Cole no chat.', 'neutro');
    } catch {
      toast(`Copie: ${COMANDO_PAINEL}`, 'neutro');
    }
  }
});
$('#sair').addEventListener('click', sair);
window.addEventListener('hashchange', () => {  // link novo do agente numa aba que já estava aberta
  if (!/^#entrar=/.test(location.hash)) return;
  acessoAberto = false;
  acessoAoIniciar();
});

// Polling: o painel acompanha o que acontece no agente. Luz nova vira um toast; nada é refeito com algo aberto.
const chaveLm = (l) => `${l.quando}|${l.skill}|${l.lm}|${l.fonte}|${l.ref}`;
const assinatura = (e) => JSON.stringify([(e.lumens || []).map(chaveLm), (e.centelhas || []).map((c) => c.id + c.estado + c.confirmada + c.na_fila),
  (e.pedidos || []).map((p) => `${p.id}:${p.estado}`), e.trajetoria?.versao_atual, e.modo, e.agente, e.vazio]);
async function atualizarSozinho() {
  if (!E || !$('#gaveta').hidden || conquista || mostrarFormPedido) return;
  const novo = await api('/api/estado', null, true);
  if (novo.erro || !E) return;
  const vistos = new Set((E.lumens || []).map(chaveLm));
  const novos = (novo.lumens || []).filter((l) => !vistos.has(chaveLm(l)));
  const mudou = assinatura(novo) !== assinatura(E);
  E = novo;
  const editando = document.activeElement && ['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName);
  if (mudou && !editando) {
    if (E.vazio) telaBoasVindas(); else render();
  }
  if (novos.length) {
    const l = novos[novos.length - 1];
    toast(`+${l.lm} lm · ${nomeCurto(l.skill)} · ${FONTES[l.fonte] || 'luz'}`, l.luz === 'refletida' ? 'refletida' : '');
  }
}

acessoAoIniciar();
