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
> pública é da rotina das 06:00. Não faça commit, não faça push, não rode
> `tools/build_publico.py`.
>
> **O que se espera de você:** encontrar oportunidade REAL para o portfólio da
> Thutor — edital ainda disputável, escopo aderente, porte que sustente o ticket.
> Dia sem nada quente é resultado legítimo. O que não se aceita é oportunidade
> inventada para encher a tela, nem oportunidade verdadeira que passou batido.
>
> **Orçamento:** você começa 02:00, ninguém abre antes das 08:00. A coleta leva
> ~4 minutos, a conferência na fonte mais alguns. Vá até o fim.
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
> Um comando faz suíte, **as duas varreduras do PNCP**, conferência item a item
> na fonte, e a fusão com o estado anterior. Ele **para com `FALHA:` e código
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
> rajada. **Ele retoma do checkpoint** — a coleta que já deu certo não é repetida.
>
> Saem dois arquivos em `trabalho/`: `base.json` (o estado fundido, que você NÃO
> edita) e `triagem.json` (o que espera julgamento).
>
> ### PASSO 3 — Camada 2 (já vem no PASSO 2)
> `tools/rodada.py` roda `tools/camada2.py` sozinho: ele busca as fontes fora do
> PNCP por código, com User-Agent de navegador, e devolve os candidatos junto
> com os do PNCP. Você **não precisa** visitar portal nenhum com WebFetch.
>
> Isso mudou em 06/09/2026. Antes era um plano em prosa com quinze portais para
> o agente visitar, e rendeu zero candidatos em três rodadas — metade devolvendo
> 403. O 403 era bloqueio de User-Agent, não política de robô; com o cabeçalho
> certo, o Canal do Fornecedor do Sebrae devolve JSON com as licitações abertas
> de todo o Sistema.
>
> A saída da fase informa quantas fontes abriram e por que as outras não. Se uma
> fonte que costumava abrir passar a falhar, **diga no relatório** — é assim que
> se descobre que um portal mudou de endereço.
>
> Se você encontrar por conta própria um edital aderente numa plataforma fora do
> registro, cite no relatório final com a URL. Fonte nova é o jeito mais barato
> de o radar crescer, e quem a acrescenta a `tools/camada2.py` é uma pessoa.
>
> ### PASSO 4 — Triagem (a sua parte)
> Leia `trabalho/triagem.json`. Para cada item, um veredito:
>
> - `quente` — aderência direta ao portfólio, `disputa` em `aberto`/`relicita`/
>   `indeterminado`, porte compatível com o ticket (R$ 50 mil/mês; 6 meses =
>   R$ 300 mil). Valor sigiloso **não** impede.
> - `morno` — tema certo, mas porte menor ou escopo ainda impreciso.
> - `frio` — não é o nosso negócio.
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
> python3 tools/monta.py --vereditos vereditos.json --externas externas.json \
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
> ### PASSO 7 — Conferir que entrou mesmo
> ```
> python3 tools/checa_rodada.py busca-editais-fg.html
> ```
> Publicar e confiar foi exatamente o que falhou em 05/09. Se este comando
> reprovar, você não terminou.
>
> ### PASSO 8 — O que o radar aprendeu
> ```
> python3 tools/aprende.py busca-editais-fg.html
> ```
> Propõe órgãos que voltaram a comprar, palavras que discriminaram os bons e
> ainda não estão no léxico, ruído que merece veto, e quem está ganhando.
>
> **NÃO APLIQUE NADA AUTOMATICAMENTE.** Um filtro que se reescreve sozinho é um
> filtro que ninguém audita depois. Leve as 2 ou 3 propostas mais fortes para o
> relatório, com o número que as sustenta.
>
> ### PASSO 9 — Fechar
> Em português, no máximo 10 linhas: contratações do PNCP e se a conta fechou;
> fontes externas visitadas/abertas e qual rendeu; candidatos, triados,
> conferidos; quentes e mornos, com objeto e valor de cada quente; quantos
> `relicita`; quantos fecham prazo em 7 dias; quantos candidatos **só a
> varredura por prazo aberto enxergou**; quantas inexigibilidades e quantas
> disputas encerradas saíram; duração; e o link do artifact.
>
> Feche com DUAS LINHAS do PASSO 8: a proposta mais forte de termo ou veto, e
> qualquer órgão que voltou a comprar.
>
> Se alguma fonte ficou sem cobertura, ou apareceu plataforma fora do registro,
> diga qual. **NÃO** reporte nada sobre a página pública — ela não é sua.


## Rotina 2 — Espelho público, 06:00 (America/Sao_Paulo)

Cron em UTC: `0 9 * * *` · presa à conversa `session_017BXpt2HuGTEHkC9QKLhABx`

Esta é a única peça do sistema que escreve no repositório, e por isso é a única
que roda numa **conversa fixa**: ela foi criada com o repositório anexado como
fonte e como destino, o que é o que dá permissão de push. A varredura das 02:00
roda em sessão nova todo dia e não tem essa permissão — nem precisa ter.

O prompt completo do procedimento vive dentro daquela conversa, estabelecido na
primeira mensagem; o gatilho diário só a acorda com um lembrete curto. Se a
conversa precisar ser recriada, o texto de referência é o desta seção.

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
