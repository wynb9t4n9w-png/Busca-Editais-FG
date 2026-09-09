# As rotinas

Os prompts abaixo são o que de fato roda todo dia. Eles ficam versionados aqui
de propósito.

Na Pauta Thutor, o prompt da rotina existe só dentro do agendamento: ninguém
consegue lê-lo sem abrir a configuração, ninguém revisa uma mudança, e não há
histórico de por que uma instrução foi parar ali. Um dos prompts de lá tem mais
de cem linhas de aprendizado acumulado — cada linha comprada com um dia de
coleta ruim — e nada disso aparece no repositório. Aqui aparece.

Quem editar uma rotina no painel de agendamentos deve trazer a mudança para cá
no mesmo commit. Um prompt que diverge do arquivo é pior do que um prompt não
versionado, porque dá a impressão de estar documentado.

---

## Rotina 1 — Varredura diária, 02:00 (America/Sao_Paulo)

Cron em UTC: `0 5 * * *`

Esta rotina foi reescrita em 05/09/2026, depois de uma varredura que rodou 3
minutos e 45 segundos, terminou com status de sucesso e não publicou nada.
Nenhum script tinha quebrado — a suíte passava, a coleta trazia 5.412 de 5.412
contratações. O que quebrou foi a forma: dez passos em prosa numa única
passagem, com o agente **reescrevendo à mão um bloco JSON de 109 KB** no meio do
caminho. Agora a parte determinística é um comando, a parte de julgamento é
outro, e cada uma deixa arquivo no disco.

> Você vai gerar a rodada diária do **Busca Editais FG** — o radar de editais de
> licitação aderentes ao portfólio da consultoria Thutor.
>
> Destino único: o artifact privado, que é a fonte da verdade.
> https://claude.ai/code/artifact/22647cdb-abec-49c7-a7cc-caa27d1af32b
>
> **Você NÃO escreve no repositório.** Sessões criadas por gatilho nascem sem o
> repositório nas fontes autorizadas e o proxy do git recusa o push. A página
> pública é da rotina das 04:00. Não faça commit, não faça push, não rode
> `tools/build_publico.py`.
>
> **O que se espera de você:** encontrar oportunidade REAL para o portfólio da
> Thutor — edital ainda disputável, escopo aderente, porte que sustente o ticket.
> Dia sem nada quente é resultado legítimo. O que não se aceita é oportunidade
> inventada para encher a tela, nem oportunidade verdadeira que passou batido.
>
> **Orçamento:** você começa 02:00, ninguém abre antes das 08:00 — são seis
> horas. A rodada determinística leva de **30 a 45 minutos**, e a maior parte
> disso é a fase 5, que faz uma consulta ao PNCP por edital, com pausa entre
> elas. Não é travamento: é o preço de perguntar à fonte em vez de adivinhar, e
> a fase grava no disco a cada dez editais, então nada se perde se ela for
> interrompida. **Vá até o fim.**
>
> ### PASSO 1 — Ler o estado
> Artifact com `action:"read"` na URL acima. **GUARDE O CAMINHO** do HTML salvo —
> todos os comandos abaixo o recebem. Se a leitura falhar, responda começando com
> `FALHA:`, cole o erro, e diga que nada foi publicado hoje.
>
> ### PASSO 2 — A rodada determinística
> ```
> cd /home/user/Busca-Editais-FG      # clone se faltar; leitura funciona
> python3 tools/rodada.py <caminho do HTML do artifact>
> ```
> Um comando faz seis fases: suíte, **as duas varreduras do PNCP**, a camada 2,
> conferência item a item na fonte, e a fusão com o estado anterior — que
> deduplica as publicações da mesma disputa e guarda tudo na memória antes de
> cortar o que já não dá para pescar. Ele **para com `FALHA:` e código
> diferente de zero** em qualquer problema, e a mensagem diz o que fazer. Leia a
> saída inteira.
>
> As duas varreduras respondem perguntas diferentes: `/publicacao` traz o que
> entrou nas últimas 24h — e o que não declara prazo; `/proposta` traz tudo que
> **aceita proposta nos próximos 60 dias**, publicado quando for. Medido em
> 06/09/2026 no mesmo instante: a primeira achava 13 aderentes disputáveis, as
> duas juntas acharam 94. Um edital fica aberto de 15 a 45 dias — olhar só o de
> ontem era ver um trigésimo do açude.
>
> Se ele falhar por varredura incompleta, rode de novo: o PNCP devolve 503 em
> rajada. **Ele retoma do checkpoint** — a coleta que já deu certo não é
> repetida, e a fase 5 grava a cada dez editais, então uma interrupção custa
> segundos e não meia hora.
>
> A janela da varredura por publicação **alarga sozinha** quando o que volta é
> magro demais para um dia útil: 3 dias, 5, 8, 11. Em 08/09/2026, terça depois
> do 7 de Setembro, a de 3 dias trouxe 587 contratações e a de 5 trouxe 11.744.
> Se você vir a linha "alargando a janela" na saída, é isso funcionando — não é
> defeito.
>
> Saem dois arquivos em `trabalho/`: `base.json` (o estado fundido, que você NÃO
> edita) e `triagem.json` (o que espera julgamento). Só precisam de veredito os
> que ainda não têm um; os demais vêm decididos de rodadas anteriores.
>
> ### PASSO 3 — Camada 2 (já vem no PASSO 2)
> `tools/rodada.py` roda `tools/camada2.py` sozinho: ele busca as fontes fora do
> PNCP por código, com cabeçalho completo de navegador, e devolve os candidatos
> junto com os do PNCP. Você **não precisa** visitar portal nenhum com WebFetch.
>
> Isso mudou em 06/09/2026. Antes era um plano em prosa com quinze portais para
> o agente visitar, e rendeu zero candidatos em três rodadas — metade devolvendo
> 403. O 403 não era política de robô: faltavam os cabeçalhos `Sec-Fetch-*`. Com
> eles, seis fontes abriram e a camada passou de 6 licitações lidas por noite
> para 85 — Sebrae (Sistema inteiro), Sesc DN, Senac-ES, Sistema FIESC, SESI-SP
> e SENAI-SP. Senac DN e CNI continuam fechados, e ficam sondados.
>
> A saída da fase informa quantas fontes abriram e por que as outras não. Se uma
> fonte que costumava abrir passar a falhar, **diga no relatório** — é assim que
> se descobre que um portal mudou de endereço.
>
> Duas anotações do registro estavam erradas e custaram semanas de fonte fechada
> à toa: SESI-SP e o Sistema FIESC tinham sido julgados pela primeira página que
> responderam. Se você for anotar uma fonte como sem serventia, **anote a prova**,
> não a impressão.
>
> Se você encontrar por conta própria um edital aderente numa plataforma fora do
> registro, cite no relatório final com a URL. Fonte nova é o jeito mais barato
> de o radar crescer, e quem a acrescenta a `tools/camada2.py` é uma pessoa.
>
> ### PASSO 4 — Triagem (a sua parte)
> Leia `trabalho/triagem.json`. Para cada item sem veredito, um veredito:
>
> - `quente` — aderência direta ao portfólio, `disputa` em `aberto`/`relicita`/
>   `indeterminado`, porte compatível com o ticket (R$ 50 mil/mês; 6 meses =
>   R$ 300 mil). Valor sigiloso **não** impede.
> - `morno` — tema certo, mas porte menor ou escopo ainda impreciso.
> - `frio` — não é o nosso negócio.
>
> **Edital pequeno não chega mais até você.** Desde 09/09/2026 o piso é
> `perfil.VALOR_MINIMO` = R$ 500.000 de valor global, e o corte vale para o
> radar **e para a memória**. A razão é aritmética: ler o edital, montar
> proposta, reunir habilitação e acompanhar sessão custa quase o mesmo em
> qualquer tamanho de contrato, e abaixo desse patamar a conta não fecha nem
> ganhando. Espere um radar curto: a meta é pipeline comercial real, não volume.
> Radar de dois editais com os dois valendo proposta é um bom radar.
>
> **Valor sigiloso ou não declarado PASSA pelo piso**, e passa de propósito:
> desconhecido não é pequeno. Dos 66 editais medidos em 09/09/2026, 36
> declaravam menos de R$ 500 mil, 16 declaravam mais e **14 não declaravam
> nada**. Quem decide sobre a incógnita é você, lendo o objeto — e um deles pode
> ser o maior do ano.
>
> **`relicita` (deserto ou fracassado) merece atenção EXTRA**: o órgão quis
> comprar, não conseguiu, e costuma voltar. Quem já leu o edital chega na frente.
>
> Portfólio (institucional 2025): Cultura Organizacional; Estratégia;
> Desenvolvimento de Líderes; Eficiência e Gestão (design organizacional, span of
> control, workforce planning); Governança.
>
> **Só chega até você o que ainda dá para disputar.** `tools/rodada.py` remove na
> fusão tudo que não é disputável — contratação direta já fechada, prazo vencido,
> processo cancelado — e faz isso *depois* de `situacao.py` ler a situação na
> fonte, nunca pelo palpite da coleta. O objetivo é pescar oportunidade real e
> converter em vitória no certame; disputa terminada não serve a isso com rótulo
> nenhum. O validador reprova a rodada que deixar uma passar, com veredito nenhum.
>
> **Inexigibilidade não chega até você**, e não deve chegar:
> `tools/coleta_pncp.py` a descarta antes de o candidato existir. O art. 74 da
> Lei 14.133 só a autoriza quando a competição é *inviável* — fornecedor
> singular, notória especialização, exclusividade —, então a escolha antecede o
> processo e nunca há janela para entrar, com vencedor publicado ou não. Se uma
> aparecer na sua lista, veio da camada 2: deixe fora do radar e cite no
> relatório. O validador reprova a rodada que deixar uma em `editais`, com
> qualquer veredito, e reprova também a chave `mercado` de volta no estado.
>
> Regras duras:
> 1. **NUNCA invente** edital, órgão, valor, prazo ou link.
> 2. Todo quente e morno precisa de `justificativa` — uma ou duas frases para
>    quem vai decidir se faz proposta.
> 3. Objeto truncado ou ambíguo: **abra o edital** antes de decidir. Um `frio`
>    errado desaparece para sempre.
>
> Grave `vereditos.json`:
> ```
> {"pncp:...": {"veredito": "morno", "justificativa": "..."}}
> ```
>
> ### PASSO 5 — Montar e validar
> ```
> python3 tools/monta.py --trabalho trabalho --vereditos vereditos.json \
>     --saida busca-editais-fg.html
> ```
> Ele aplica os vereditos, monta o HTML a partir do molde do próprio artifact,
> e roda `valida_rodada.py` e `teste_pagina.py`. Se reprovar, **não publique**:
> a mensagem diz o quê. Corrija `vereditos.json` e rode de novo.
>
> Nunca edite o validador nem os scripts de `tools/` para atravessar um portão.
>
> ### PASSO 6 — Publicar
> Artifact com `file_path=busca-editais-fg.html`, a `url` do artifact, label
> `rodada-DD-MM-AAAA`.
>
> **NÃO passe `capabilities`** — omiti-lo carrega adiante a declaração guardada
> (`db`, com a regra do acompanhamento). Declaração errada revoga o banco e apaga
> o acesso da equipe ao funil. Também não passe `favicon` nem `title`.
>
> **Se a publicação for RECUSADA** — por permissão, por conflito de versão, por
> qualquer motivo —, **não termine em silêncio**. Responda com a PRIMEIRA LINHA
> sendo `FALHA: rodada pronta e NÃO publicada`, cole o motivo exato que a
> ferramenta devolveu, e diga que o HTML validado está em
> `busca-editais-fg.html`. Esta rotina tem notificação por push: uma resposta
> que começa com FALHA chega a alguém. Uma sessão que vai dormir calada, não —
> e foi isso que aconteceu em 05/09 e de novo em 06/09, as duas vezes com a
> rodada inteira feita e validada, morrendo na última linha.
>
> ### PASSO 7 — Conferir que entrou mesmo
> Leia o artifact **de novo** com `action:"read"` e rode o vigia sobre o arquivo
> que voltou dessa leitura — não sobre o seu:
> ```
> python3 tools/checa_rodada.py <html que a releitura do artifact salvou>
> ```
> Rodar sobre `busca-editais-fg.html` não prova nada: esse arquivo é o que VOCÊ
> montou, e ele passa no vigia mesmo que a publicação tenha sido recusada. Foi
> assim que o vigia criado depois de 05/09 deixou 06/09 passar. O que precisa
> ser conferido é o que está no ar.
>
> Se o vigia reprovar a releitura, a publicação não aconteceu: volte ao PASSO 6
> e, se ela continuar recusada, responda com `FALHA:` como acima.
>
> ### PASSO 8 — O que o radar aprendeu
> ```
> python3 tools/aprende.py busca-editais-fg.html
> ```
> Propõe órgãos que voltaram a comprar, palavras que discriminaram os bons e
> ainda não estão no léxico, ruído que merece veto, e quem está ganhando. Ele lê
> a **memória**, não o radar: o radar guarda só o que ainda dá para disputar, e
> aprender só com ele seria comparar os últimos três dias contra os últimos três
> dias para sempre.
>
> **NÃO APLIQUE NADA AUTOMATICAMENTE.** Um filtro que se reescreve sozinho é um
> filtro que ninguém audita depois. Leve as 2 ou 3 propostas mais fortes para o
> relatório, com o número que as sustenta.
>
> ### PASSO 9 — Fechar
> Em português, no máximo 10 linhas: contratações do PNCP e se a conta fechou;
> fontes externas visitadas/abertas e qual rendeu; candidatos, triados,
> conferidos; quentes e mornos, com objeto e valor de cada quente; quantos
> `relicita`; quantos fecham prazo em 3 dias (a faixa de urgência do topo do
> Radar); quantos candidatos **só a varredura por prazo aberto enxergou**;
> quantas inexigibilidades, quantas disputas encerradas, quantas publicações
> duplicadas e quantos abaixo do piso de R$ 500 mil saíram; duração; e o link
> do artifact.
>
> Feche com DUAS LINHAS do PASSO 8: a proposta mais forte de termo ou veto, e
> qualquer órgão que voltou a comprar.
>
> Se alguma fonte ficou sem cobertura, ou apareceu plataforma fora do registro,
> diga qual. **NÃO** reporte nada sobre a página pública — ela não é sua.


## Rotina 2 — Espelho público, 04:00 (America/Sao_Paulo)

Cron em UTC: `0 7 * * *` · gatilho `trig_012RxsqvKz1ivmocrGZi2pud` (v3) · presa à conversa `session_017BXpt2HuGTEHkC9QKLhABx`

Esta é a única peça do sistema que escreve no repositório, e por isso é a única
que roda numa **conversa fixa**: ela foi criada com o repositório anexado como
fonte e como destino, o que é o que dá permissão de push. A varredura das 02:00
roda em sessão nova todo dia e não tem essa permissão — nem precisa ter.

O prompt completo do procedimento vive dentro daquela conversa, estabelecido na
primeira mensagem; o gatilho diário só a acorda com um lembrete curto. Se a
conversa precisar ser recriada, o texto de referência é o desta seção.

**Por que 04:00 e não 06:00.** Em 09/09/2026 o dono do projeto abriu a página
às 05:53, viu a rodada da véspera e concluiu que tinha quebrado de novo. Não
tinha: a varredura das 02:00 termina de publicar entre 02:38 e 03:06, o espelho
só rodava às 06:00, e nesse intervalo de três horas a página mostra ontem sem
nenhuma forma de distinguir "ainda não atualizou" de "parou de funcionar". Às
04:00 a janela cai para cerca de uma hora, e um espelho atrasado depois disso é
falha de verdade — que é o que um alarme precisa ser para valer alguma coisa.

**A regra que passou a valer acima de todas as outras neste prompt: não afirmar
nada sobre o repositório sem ter acabado de verificar com um comando, nesta
execução, colando a saída.** Em 09/09/2026 o relatório da rotina fechou dizendo
que `.claude/settings.json` "não existe no repositório" e que o desbloqueio
daquele dia "veio do ambiente, não do arquivo". As duas afirmações eram falsas —
o arquivo estava commitado desde 08/09 às 11:01 UTC, e a execução que falhou
rodou às 09:02, duas horas ANTES de ele existir. O arquivo era exatamente a
causa do desbloqueio.

Isso não seria grave se ficasse no log. Mas relatório de vigia é lido por
pessoa: a frase chegou ao dono do projeto, que veio perguntar o que estava
errado quando nada estava. **Vigia que relata fato não verificado gasta a
confiança que ele existe para produzir**, e é essa confiança que faz alguém
levar a sério o alarme no dia em que ele for verdadeiro.

**Duas armadilhas que dormiam no prompt anterior**, encontradas ao mudar o
horário: ele mandava o caminho de resgate rodar `tools/fontes_externas.py`,
removido em 06/09, e chamar `monta.py --externas`, opção que não existe mais. O
resgate teria quebrado exatamente na hora em que fosse necessário. Prompt de
rotina envelhece junto com o código e ninguém percebe, porque ele só é lido pela
máquina — e só no dia ruim.

Existe também pelo motivo que a rotina gêmea da Pauta Thutor existe: em
29/08/2026 a coleta de lá publicou o artifact mas não fez o commit, e a página
pública ficou uma edição atrás sem ninguém perceber. Uma varredura que falha em
silêncio é indistinguível de uma que deu certo.

> Rede de segurança do **Busca Editais FG**. A varredura roda às 02:00; você roda
> às 06:00. Sua função é garantir que a página pública não fique atrás do
> artifact.
>
> Artifact (fonte da verdade): https://claude.ai/code/artifact/22647cdb-abec-49c7-a7cc-caa27d1af32b
> Página pública: `https://wynb9t4n9w-png.github.io/Busca-Editais-FG/`
> Repositório: `wynb9t4n9w-png/Busca-Editais-FG`
>
> **PASSO 1 — Ler o artifact.** `action:"read"` na URL acima. Extraia o JSON do
> bloco `/*DADOS*/`. Anote `atualizado_em` e a data da rodada na posição 0.
> Se a leitura falhar, responda começando com `FALHA:` e cole o erro exato.
>
> **PASSO 1.5 — A rodada de hoje entrou?**
> ```
> python3 tools/checa_rodada.py <html do artifact>
> ```
> Se **aprovar**, siga para o PASSO 2 e faça o seu trabalho normal de espelho.
>
> Se **reprovar**, a varredura das 02:00 não publicou hoje, e **quem refaz é
> você**. Não é escopo emprestado: você tem o repositório, as ferramentas e
> quatro horas de folga antes de alguém abrir a página. Vá para ROTINAS.md,
> Rotina 1, e execute do PASSO 2 ao PASSO 7 — a rodada inteira. Depois volte
> para cá e espelhe o que você mesmo publicou.
>
> Isto está escrito porque a versão anterior deste prompt dizia o contrário:
> *"a varredura falhou. Não há o que reparar: responda com FALHA e termine
> aqui."* Em 05/09/2026 a varredura morreu em 3 minutos, esta rotina detectou
> corretamente o problema às 06:00, obedeceu, e não fez nada. O radar passou o
> dia mostrando a véspera. Detectar sem reparar é quase tão ruim quanto não
> detectar — custa o mesmo dia e ainda dá a impressão de que há vigilância.
>
> **PASSO 2 — Comparar.** No repositório: `git fetch origin && git pull --rebase`.
> Extraia o mesmo bloco de `docs/index.html` e compare `atualizado_em` e a rodada
> da posição 0. Se forem iguais, **não faça commit**: responda em uma linha
> dizendo que o espelho está em dia, com a data da rodada e o número de editais
> quentes. Termine aqui.
>
> **PASSO 3 — Só se estiverem diferentes.**
> ```
> python3 tools/valida_rodada.py <html do artifact>
> python3 tools/build_publico.py <html do artifact> docs/index.html
> python3 tools/teste_pagina.py docs/index.html
> ```
> Se o validador reprovar, o problema está na varredura, não no espelho: NÃO
> publique, responda com `FALHA:` e cole a saída. Se os três passarem, commit em
> `docs/index.html` apenas, e push com até 4 tentativas em espera crescente.
>
> **NÃO** altere os scripts de `tools/` e **NÃO** edite o validador.
>
> **PASSO 4 — Fechar.** No máximo 4 linhas: se o espelho já estava em dia ou se
> precisou reparo, a data da rodada, quantos quentes há em aberto, e o link
> público. Se reparou, diga que a varredura das 02:00 não fechou o ciclo sozinha
> — essa informação importa para o dono do projeto.
