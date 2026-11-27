/**
 * Luzia · cria o formulário de avaliação do teste no Google Forms, com a planilha de respostas.
 *
 * Como usar (uma vez, com a conta Google que vai receber as respostas):
 * 1. Abra https://script.google.com e clique em "Novo projeto".
 * 2. Apague o conteúdo do editor, cole este arquivo inteiro e salve.
 * 3. Escolha a função `criarFormulario` e clique em "Executar". Autorize com a sua conta quando o Google pedir.
 * 4. Em "Registro de execução" aparecem os links: o de responder (para os testadores), o de editar e o da planilha.
 *
 * As perguntas são as de docs/teste/AVALIACAO.md (mesmos códigos: B1, C2...). Cada item de escala vira uma coluna
 * numérica na planilha, pronta para calcular médias. O formulário não coleta e-mail nem nome.
 */

var ESCALA = ['Discordo totalmente', 'Concordo totalmente'];

var SECOES = [
  {
    titulo: 'A. Perfil',
    itens: [
      { tipo: 'texto', codigo: 'A1', texto: 'Cargo, área e senioridade (ex.: dev júnior, cientista de dados pleno, analista de segurança, estágio em dados)' },
      { tipo: 'numero', codigo: 'A2', texto: 'Anos programando' },
      { tipo: 'opcao', codigo: 'A3', texto: 'Com que frequência você usa agentes de IA, como o Claude Code, no trabalho?',
        opcoes: ['Todo dia', 'Algumas vezes por semana', 'De vez em quando', 'Raramente'] },
      { tipo: 'numero', codigo: 'A4', texto: 'Por quantos dias você usou a Luzia?' },
      { tipo: 'opcao', codigo: 'A5', texto: 'Quantas centelhas você converteu, mais ou menos?',
        opcoes: ['Nenhuma', '1 a 2', '3 a 5', 'Mais de 5'] },
      { tipo: 'opcao', codigo: 'A6', texto: 'Quanto tempo você costuma esperar o agente terminar uma tarefa longa?',
        opcoes: ['Menos de 1 min', '1 a 5 min', '5 a 15 min', 'Mais de 15 min'] },
    ],
  },
  {
    titulo: 'B. O problema, no seu trabalho',
    ajuda: 'Pense em como era antes da Luzia. 1 = discordo totalmente, 5 = concordo totalmente.',
    itens: [
      { tipo: 'escala', codigo: 'B1', texto: 'Aceito código do agente que eu não saberia explicar sem a IA.' },
      { tipo: 'escala', codigo: 'B2', texto: 'Isso me preocupa para o meu crescimento profissional.' },
      { tipo: 'escala', codigo: 'B3', texto: 'Tenho dificuldade de saber o que estudar a partir do que o agente faz por mim.' },
      { tipo: 'escala', codigo: 'B4', texto: 'Já tive dificuldade de explicar ou defender uma entrega minha (revisão de código ou de análise, reunião, avaliação).' },
      { tipo: 'escala', codigo: 'B5', texto: 'Ter evidência do que eu realmente domino (para PDI, promoção ou feedback) seria útil para mim.' },
      { tipo: 'escala', codigo: 'B6', texto: 'Com que frequência você aceita código do agente sem entender tudo?',
        rotulos: ['Nunca', 'Quase sempre'] },
    ],
  },
  {
    titulo: 'C. A Luzia resolve?',
    ajuda: 'Responda pelo que aconteceu no seu uso, não pelo que a Luzia promete.',
    itens: [
      { tipo: 'escala', codigo: 'C1', texto: 'Converter centelhas me ajudou a entender o que eu tinha aceitado do agente (código, análise, script ou configuração).' },
      { tipo: 'escala', codigo: 'C2', texto: 'Depois de converter uma centelha, eu conseguiria explicar o conceito a um colega sem a IA.' },
      { tipo: 'escala', codigo: 'C3', texto: 'As centelhas propostas tinham a ver com o meu trabalho e com a minha meta.' },
      { tipo: 'escala', codigo: 'C4', texto: 'A diferença entre luz própria e luz refletida descreve bem como eu uso IA.' },
      { tipo: 'escala', codigo: 'C5', texto: 'O "% do caminho" acompanha o que eu sinto que aprendi.' },
      { tipo: 'escala', codigo: 'C6', texto: 'A Luzia me mostrou com clareza o que praticar a seguir.' },
      { tipo: 'escala', codigo: 'C7', texto: 'Confio nas notas de propriedade (P1 a P4) das minhas entregas.' },
      { tipo: 'paragrafo', codigo: 'C8', texto: 'Descreva uma centelha que você converteu. O que você entendeu que não entendia antes?', opcional: true },
    ],
  },
  {
    titulo: 'D. Uso',
    itens: [
      { tipo: 'escala', codigo: 'D1', texto: 'Os recursos da Luzia atendem ao que eu preciso.' },
      { tipo: 'escala', codigo: 'D2', texto: 'A Luzia é fácil de usar.' },
      { tipo: 'escala', codigo: 'D3', texto: 'O tutorial do painel me ensinou o suficiente para começar.' },
      { tipo: 'escala', codigo: 'D4', texto: 'Os avisos no chat (modo Em foco) foram toleráveis no meu ritmo de trabalho.' },
      { tipo: 'escala', codigo: 'D5', texto: 'A Luzia atrapalhou o meu fluxo de trabalho.' },
    ],
  },
  {
    titulo: 'E. Viabilidade e adoção',
    itens: [
      { tipo: 'escala', codigo: 'E1', texto: 'Eu continuaria usando a Luzia nas próximas semanas.' },
      { tipo: 'escala', codigo: 'E2', texto: 'Eu usaria a Luzia no meu trabalho com as regras de privacidade de hoje.' },
      { tipo: 'escala', codigo: 'E3', texto: 'Eu mostraria o dossiê da Luzia ao meu líder ou num PDI.' },
      { tipo: 'escala', codigo: 'E4', texto: 'O tempo que gastei convertendo centelhas valeu a pena.' },
      { tipo: 'opcao', codigo: 'E5', texto: 'Como você se sentiria se não pudesse mais usar a Luzia?',
        opcoes: ['Seria uma grande perda', 'Seria uma pequena perda', 'Não faria diferença'] },
      { tipo: 'escala', codigo: 'E6', texto: 'Quanto você recomendaria a Luzia a um colega que trabalha com agentes de IA?',
        min: 0, max: 10, rotulos: ['Nada provável', 'Muito provável'] },
      { tipo: 'escala', codigo: 'E7', texto: 'Converter centelhas enquanto o agente trabalhava aproveitou um tempo em que eu só ficaria esperando.' },
      { tipo: 'escala', codigo: 'E8', texto: 'A Luzia tomou um tempo que eu preferiria usar em outra coisa.' },
    ],
  },
  {
    titulo: 'F. Privacidade e confiança',
    itens: [
      { tipo: 'escala', codigo: 'F1', texto: 'Ficou claro o que a Luzia observa, o que guarda e o que envia ao modelo.' },
      { tipo: 'escala', codigo: 'F2', texto: 'Eu me senti confortável com o que a Luzia observa.' },
      { tipo: 'paragrafo', codigo: 'F3', texto: 'Você deixaria a Luzia ler o histórico do Claude Code e do Codex? Por quê?', opcional: true },
    ],
  },
  {
    titulo: 'G. Aberto',
    itens: [
      { tipo: 'paragrafo', codigo: 'G1', texto: 'O que você manteria?', opcional: true },
      { tipo: 'paragrafo', codigo: 'G2', texto: 'O que você tiraria?', opcional: true },
      { tipo: 'paragrafo', codigo: 'G3', texto: 'O que faltou?', opcional: true },
      { tipo: 'paragrafo', codigo: 'G4', texto: 'Se pudesse mudar uma única coisa, qual seria?', opcional: true },
      { tipo: 'paragrafo', codigo: 'G5', texto: 'Algo não funcionou ou atrapalhou, na instalação ou no uso? Conte em poucas palavras.', opcional: true },
    ],
  },
];

function criarFormulario() {
  var form = FormApp.create('Luzia · Avaliação do teste');
  form.setDescription(
    'A participação é voluntária e anônima: o formulário não pede nome nem e-mail. As respostas vão só para a Rayane, ' +
    'para o trabalho da disciplina. Não cole código da empresa nem segredos (chaves, tokens, e-mails). Leva cerca de 10 minutos.');
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setProgressBar(true);
  form.setConfirmationMessage('Obrigada! Sua resposta foi registrada.');

  SECOES.forEach(function (secao, i) {
    if (i > 0) form.addPageBreakItem().setTitle(secao.titulo).setHelpText(secao.ajuda || '');
    else form.addSectionHeaderItem().setTitle(secao.titulo).setHelpText(secao.ajuda || '');
    secao.itens.forEach(function (it) { adicionar(form, it); });
  });

  var planilha = SpreadsheetApp.create('Luzia · Respostas da avaliação');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, planilha.getId());

  Logger.log('Link para responder (mande aos testadores): ' + form.getPublishedUrl());
  Logger.log('Link para editar o formulário: ' + form.getEditUrl());
  Logger.log('Planilha de respostas: ' + planilha.getUrl());
}

function adicionar(form, it) {
  var titulo = it.codigo + '. ' + it.texto;
  var item;
  if (it.tipo === 'escala') {
    var rot = it.rotulos || ESCALA;
    item = form.addScaleItem().setTitle(titulo).setBounds(it.min === undefined ? 1 : it.min, it.max || 5)
      .setLabels(rot[0], rot[1]);
  } else if (it.tipo === 'opcao') {
    item = form.addMultipleChoiceItem().setTitle(titulo).setChoiceValues(it.opcoes);
  } else if (it.tipo === 'numero') {
    item = form.addTextItem().setTitle(titulo)
      .setValidation(FormApp.createTextValidation().requireNumberGreaterThanOrEqualTo(0).build());
  } else if (it.tipo === 'paragrafo') {
    item = form.addParagraphTextItem().setTitle(titulo);
  } else {
    item = form.addTextItem().setTitle(titulo);
  }
  item.setRequired(!it.opcional);
}
