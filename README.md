# Busca Editais FG

Radar diário de editais de licitação aderentes ao portfólio da consultoria
Thutor — cultura organizacional, estratégia, desenvolvimento de líderes,
eficiência e governança.

Projeto irmão da [Pauta Thutor](https://github.com/wynb9t4n9w-png/Pauta-Thutor),
de onde vieram a arquitetura de duas páginas, o portão de validação e a
disciplina de nunca deixar uma execução falhar em silêncio. O que mudou, mudou
por um motivo — e cada motivo está registrado abaixo.

## O que este projeto não é

Não é um clipping. A Pauta Thutor procura notícia com `WebSearch`, e para
notícia isso funciona. Para edital, não: em 03/09/2026 o buscador do próprio
PNCP recebeu o termo "educação corporativa" e devolveu, entre os primeiros
resultados, *aquisição de materiais de higiene e limpeza*. Busca textual sobre
objeto de licitação é rasa demais para servir de filtro.

O caminho aqui é outro. A Lei 14.133/2021 obriga a administração pública a
publicar tudo no **PNCP**, e o portal tem API aberta. Então baixamos o dia
inteiro — cerca de 5.800 contratações — e filtramos localmente, com um léxico
que conhece o vocabulário da Thutor. Custa dois minutos e não erra por
ranqueamento.

## Como funciona

Duas páginas, com papéis diferentes — o mesmo desenho da Pauta Thutor:

| | Artifact (privado) | GitHub Pages (público) |
|---|---|---|
| Endereço | [`22647cdb…`](https://claude.ai/code/artifact/22647cdb-abec-49c7-a7cc-caa27d1af32b) | [`wynb9t4n9w-png.github.io/Busca-Editais-FG/`](https://wynb9t4n9w-png.github.io/Busca-Editais-FG/) |
| Quem abre | só quem tem acesso na conta Claude | qualquer pessoa com o link |
| Acompanhamento comercial | editável, no banco do artifact | não existe |
| Papel | **fonte da verdade** | espelho somente-leitura |

Um edital é informação pública por definição: publicá-lo não vaza nada. Já o
que a Thutor está fazendo com ele, sim. `status: "participando"`, ou uma nota
dizendo quem é o contato dentro do órgão, é o funil comercial da casa. Por isso
o espelho perde `auth`, `status`, `nota` e a aba Acompanhamento, e
`tools/teste_pagina.py` falha se algum deles atravessar.

Desde 03/09/2026 esses dois campos nem chegam a passar pelo HTML: eles vivem no
**banco do artifact**, sob a regra `{read: "interact", write: "admin"}` — quem
consegue abrir o radar lê, só quem tem permissão de edição escreve, e é o
servidor que decide. O espelho público não tem como alcançá-los, porque no
GitHub Pages não existe `window.claude`. O sanitizador virou defesa em
profundidade, não a única linha.

A visibilidade do repositório não entra nessa conta, e é importante entender por
quê antes de contar com ela. Um site do GitHub Pages é servido **público de
qualquer jeito**: mesmo em repositório privado — fora do plano Enterprise — o
`docs/index.html` que ninguém lê no GitHub fica aberto no endereço do Pages. E
um repositório pode mudar de privado para público num clique, como este mudou
em 03/09/2026.

Ou seja: a sanitização é o que protege o funil, sempre, e não uma redundância
para o caso de o repositório vazar. É por isso que `tools/teste_pagina.py` a
trata como falha de publicação, e não como aviso.

## A rotina diária

Roda às 02:00 (horário de São Paulo) e tem a manhã inteira de folga. Os prompts
estão em [`ROTINAS.md`](ROTINAS.md) — versionados de propósito, o que a Pauta
Thutor não faz.

1. lê o estado atual do artifact;
2. **camada 1**: varre o PNCP inteiro pela API e filtra pelo perfil comercial;
3. **camada 2**: lê os portais do Sistema S, estatais e bancos, que o PNCP não
   cobre;
4. tria os candidatos em quente, morno ou frio, com justificativa;
5. **valida** a rodada — se não passar, não publica;
6. republica o artifact e gera `docs/index.html`.

Às 06:00 uma segunda rotina confere se a página ficou mesmo igual ao artifact e
repara se não ficou. Existe porque em 29/08/2026 a coleta da Pauta Thutor
publicou o artifact e não fez o commit, e a página pública ficou uma edição
atrás sem ninguém perceber.

## As duas camadas

### Camada 1 — o PNCP

```bash
python3 tools/coleta_pncp.py                   # ontem e hoje
python3 tools/coleta_pncp.py 20260902 20260902
```

Onze modalidades, todas as páginas, quatro trabalhadores em paralelo. Medido em
02/09/2026: **5.849 contratações em 124 páginas, 117 segundos**. Leilão fica de
fora — é venda de bem público, não contratação de serviço.

O script conta quantos registros a API prometeu (`totalRegistros`) e quantos
chegaram. Quando uma página falha, ele espera 20 segundos e repesca; se ainda
assim faltar, ele **diz**, e o validador barra. Isso importa: na primeira
execução de teste, nove páginas se perderam para HTTP 503 e 504 — cerca de
quatrocentas contratações desapareceram sem nenhum sinal na saída.

### Camada 2 — o que o PNCP não alcança

```bash
python3 tools/fontes_externas.py               # o plano de leitura
python3 tools/fontes_externas.py --relatorio <estado.html>
```

O Sistema S (Sebrae, Sesi, Senai, Sesc, Senac, Senar, Sest/Senat) tem
regulamento próprio de licitação e publica nos seus portais. Parte espelha no
PNCP por opção — o SEBRAE/PR aparece lá —, a maioria não. E é o segmento mais
aderente à Thutor. Estatais e bancos públicos (Lei 13.303) são o mesmo caso,
com tickets maiores.

Este arquivo **não é um raspador**, e isso é decisão de projeto. Raspar trinta
portais em Python quebra toda semana: 403 antirrobô, página montada em
JavaScript, seletor que muda sem aviso. O que existe é um registro — onde olhar
e o que procurar — lido pelo modelo via `WebFetch`, que atravessa página
dinâmica e entende layout novo sem manutenção.

Duas coisas que a sondagem de 03/09/2026 ensinou e que ficaram gravadas no
registro:

- **Metade das URLs "que abriam" eram páginas-índice.** A listagem real do Sesc
  está em `sesc.com.br/licitacoes/licitacoes-em-andamento-v2/`, a do Senar em
  `app3.cna.org.br/transparencia/`, e nenhuma das duas é adivinhável a partir da
  página principal.
- **O Sistema Sebrae inteiro publica num endereço só** — o Canal do Fornecedor,
  `scf3.sebrae.com.br/portalcf` — e não em 27 portais estaduais. Mais
  importante: o Sebrae contrata consultoria e instrutoria por **credenciamento
  contínuo**, não por licitação avulsa. Quem não está credenciado não é
  convidado, e nenhum radar de editais resolve isso. É uma tarefa de uma vez só,
  não de todo dia.

### O mecanismo melhora todo dia

A Pauta Thutor tem um dossiê de fontes que se refaz a cada execução: ele olha
quais veículos de fato renderam notícia e vira uma camada de busca dirigida por
evidência. A lista fixa do prompt envelhece; o dossiê não.

Aqui a mesma ideia opera em dois lugares, e o material é melhor porque a coleta
é determinística.

**A ordem de visita aprende.** Cada rodada registra em `estado["fontes"]` o que
aconteceu com cada portal — tentativas, aberturas, candidatos, editais rendidos,
falhas seguidas. Passando o estado ao script, o plano sai ordenado: quem rende
vem primeiro, quem não abre há três rodadas vai para o fim. E **continua na
lista**: portal de licitação passa semanas sem publicar nada do nosso tema, e
abandonar cedo é como perder cliente por não ligar.

```bash
python3 tools/fontes_externas.py <estado.html>   # plano ordenado por rendimento
python3 tools/fontes_externas.py --relatorio <estado.html>
```

**O filtro aprende.** `tools/aprende.py` lê o histórico e propõe o que a
próxima versão deveria procurar:

```bash
python3 tools/aprende.py <estado.html>
```

- **órgãos que voltaram** a comprar o tema — prospecção direta, não espera pelo
  próximo edital;
- **palavras que discriminaram** os editais bons dos frios e ainda não estão no
  léxico, ranqueadas por quanto discriminam e não por frequência crua (a
  frequência elegeria "serviços");
- **ruído recorrente** que merece veto, sempre conferindo que a palavra nunca
  apareceu num edital bom;
- **quem está ganhando** — na primeira medição, 7 dos 12 contratos foram para
  fundação, universidade ou entidade do Sistema S. Se isso se confirmar ao longo
  das semanas, é uma característica do mercado, e uma decisão de posicionamento.

Nada disso é aplicado sozinho. O script **propõe**, com o número que sustenta
cada proposta; quem edita `tools/perfil.py` é uma pessoa, e cada termo novo entra
junto com um caso de ouro em `tools/teste_perfil.py`. Um filtro que se reescreve
sozinho é um filtro que ninguém consegue auditar depois — e este projeto já
gastou caro aprendendo que o erro que some em silêncio é o que custa.

## O perfil comercial

```bash
python3 tools/perfil.py "texto do objeto"   # explica a pontuação
python3 tools/perfil.py --termos            # lista o léxico
```

Aqui vive a tradução do institucional 2025 em código: seis frentes (cultura,
estratégia, liderança, eficiência, governança, pessoas), cada uma com termos de
núcleo, de apoio e de contexto, mais uma lista de vetos.

O filtro é **generoso de propósito**. As duas maneiras de errar não custam o
mesmo: deixar passar lixo custa um parágrafo de leitura na triagem; barrar um
edital bom custa um contrato — e some em silêncio, porque ninguém sente falta do
que nunca apareceu na lista.

### O que o dado real ensinou

Rodar o filtro contra 5.849 contratações de um dia só derrubou três suposições:

**"Cultura" é uma armadilha.** Em licitação pública, cultura quase sempre
significa cultura artística. Dos 65 primeiros candidatos, oito eram oficina de
capoeira, coral infantil e feira do livro. O termo solto saiu do léxico; só
"cultura organizacional" e parentes qualificam.

**Toda prefeitura tem uma Secretaria de Gestão de Pessoas, e ela compra
gasolina.** O vocabulário de RH aparece no cabeçalho de objetos que não têm
nada a ver — equipamentos de informática, óleo lubrificante, camisetas. Daí a
regra de sustentação: sem nenhum termo de núcleo, é preciso ter dois termos de
apoio de frentes diferentes.

**Um veto de cinco letras matou o melhor lead do dia.** O padrão `opera`, sem
delimitador de palavra, casou dentro de *operacionalização* e derrubou um
diagnóstico organizacional com mapeamento de processos — exatamente a frente
Eficiência e Gestão. O erro é barato de cometer e caríssimo de perceber, porque
o candidato simplesmente não aparece. Hoje `perfil._confere_delimitadores()`
recusa qualquer veto de palavra curta sem `\b`, e o teste chama essa função.

O resultado do dia 02/09, depois do ajuste: **5.849 brutos → 33 candidatos → 17
guardados → 1 quente**. O quente era a Universidade Corporativa em Rede do
CRECI/SC, R$ 1,5 milhão — trinta meses no ticket mínimo, e um item literal do
portfólio.

### Ainda dá para disputar?

Esta pergunta não existia no projeto, e a ausência dela produziu o pior erro que
o radar já cometeu. Em 03/09/2026 ele exibiu como **oportunidade quente** um
contrato de R$ 1,5 milhão — Universidade Corporativa do CRECI/SC, exatamente o
portfólio da casa. O contrato já havia sido assinado com a UFSC no dia anterior.
Só apareceu porque um humano abriu o link.

O que torna o caso instrutivo é que **nenhum campo de status denunciava**:
`situacaoCompraNome` dizia "Divulgada no PNCP". Em contratação direta — Dispensa
e Inexigibilidade — o portal publica o extrato *depois* do fato, e o registro
fica indistinguível de um edital novo para quem só lê o status.

Quem responde é a **janela de proposta**, e a medição explica por que o erro não
era raro: das 33 contratações aderentes de 02/09/2026, **27 não tinham janela
nenhuma**. Quatro dos cinco editais que entraram no radar como quente ou morno
eram desse tipo. O radar estava mostrando, em sua maioria, o retrovisor.

A pergunta é respondida em dois passos, e o segundo existe porque o primeiro
erra. A varredura em massa **deduz** a partir do que a listagem entrega — é de
graça, mas é dedução. Depois, `tools/situacao.py` **abre cada candidato** e lê a
situação item a item, que é o que o PNCP de fato registra.

A diferença entre os dois foi medida em 03/09/2026: das 17 classificações,
**três estavam erradas** — e duas delas escondiam edital ainda disputável como
se já tivesse dono. É o erro caro, o que some em silêncio. Uma inexigibilidade
do Município de Estrela e um processo de Jacobina estavam "Em andamento" na
fonte, e a dedução os havia enterrado.

Cada edital carrega agora um campo `disputa`:

| | |
|---|---|
| `aberto` | o prazo de proposta ainda corre — é oportunidade |
| `encerrado` | havia prazo, e passou |
| `decidido` | contratação direta sem janela: o fornecedor já estava escolhido |
| `inexigivel` | modalidade Inexigibilidade: a lei declarou a competição inviável. Nunca foi disputa e nunca vai ser |
| `relicita` | **deserto** (ninguém apareceu) ou **fracassado** (apareceram e foram desclassificados) — o órgão quis comprar e não conseguiu, e costuma voltar. É disputável, e das melhores horas de aparecer |
| `cancelado` | anulado ou revogado |
| `indeterminado` | modalidade com disputa mas sem prazo declarado — o órgão publicou incompleto; não descarte, confira |

Deserto e fracassado a dedução não enxergava de jeito nenhum: os dois apareciam
como prazo vencido. São justamente os casos em que quem já leu o edital chega na
frente da próxima rodada.

O Radar e a aba Prazos mostram só o que é disputável, e o validador **reprova a
rodada** que marcar como `quente` algo que não seja.

### Inexigibilidade não é uma disputa: é a ausência de uma

O campo `disputa` nasceu olhando para o prazo, e por isso ainda deixava passar
uma classe inteira de falso positivo. Em 04/09/2026 o radar exibiu como
oportunidade um processo de **R$ 30,5 milhões** da SEDUC-PA — estruturação de
Unidade de Assessoramento Técnico, metodologia, governança, indicadores: o
portfólio da casa quase palavra por palavra. O item ainda dizia "Em andamento" e
`temResultado` era `false`, então tanto a dedução quanto `situacao.py` o
classificaram como `aberto`. Um dos anexos do próprio processo se chamava
`Contrato_n__046.2026_-_FGV.pdf`.

O erro não estava na leitura do status. Estava em perguntar pelo prazo quando a
pergunta certa era pela **modalidade**. O art. 74 da Lei 14.133/2021 só autoriza
inexigibilidade quando a competição é *inviável* — fornecedor singular, notória
especialização, exclusividade. Não existe janela para entrar, hoje ou daqui a
uma semana: a decisão sobre quem executa é premissa do processo, não resultado
dele. Uma inexigibilidade "em andamento" está apenas com a papelada em trânsito.

Daí a regra, gravada em `coleta_pncp.py` e reforçada em `situacao.py`:
**a modalidade decide antes do prazo.** Se a modalidade é Inexigibilidade, a
disputa é `inexigivel`, sem consultar item, resultado ou data — e `inexigivel`
não é disputável, então o edital nunca chega ao Radar nem à aba Prazos, e o
validador reprova a rodada que o marque como `quente`.

O tamanho do problema também foi medido: **18 dos 38 editais** do estado eram
inexigibilidade. Um deles era o único `quente` do dia (SAAE Guanhães, R$ 180
mil), e ele também não era oportunidade.

`situacao.py` ganhou no mesmo movimento uma segunda checagem, para o caso
inverso: quando o item **está** em disputa, ele lê `/arquivos` e procura anexo
cujo nome denuncie o fecho (contrato, ratificação, homologação, adjudicação,
empenho, ata de registro). Foi esse anexo que denunciou a FGV, e é ele que passa
a denunciar os próximos.

### O retrovisor vale dinheiro

Descartar as contratações já decididas seria trocar um erro por outro. Elas
dizem quais órgãos compram o que a Thutor vende, quanto pagam e quem está
ganhando — informação que uma consultoria não consegue comprar. A diferença
entre lixo e inteligência aqui é só o rótulo.

```bash
python3 tools/contratos.py --do-estado <estado.html>
python3 tools/contratos.py <cnpj> <AAAAMMDD> "trecho do objeto"
```

```bash
python3 tools/situacao.py --do-estado <estado.html>
python3 tools/situacao.py <cnpj> <ano> <sequencial>
```

`situacao.py` é o caminho principal e o mais barato em incerteza: o resultado do
item traz o vencedor com o valor homologado, direto da fonte. `contratos.py`
sobrou como reserva, para os órgãos que publicam o contrato mas não os itens —
ele cruza os objetos palavra a palavra, o que é engenhoso e aproximado.

A diferença entre os dois apareceu na primeira medição: a comparação de texto
identificou **3 fornecedores em 13**; a leitura dos itens identificou **12 em
12**. Uma é dedução esperta, a outra é o dado. Foi assim que o contrato do
CRECI/SC saiu completo — **UFSC, R$ 1,5 milhão** — e junto com ele o IBGC na
VALEC, o SENAT em Uberlândia, e uma fila de fundações universitárias que é, por
si só, o retrato de quem concorre com a Thutor neste mercado.

### Valor não elimina

O ticket mínimo é R$ 50.000/mês; seis meses valem R$ 300.000, e é esse o
patamar-alvo. Mas valor entra como **nota**, nunca como corte: boa parte dos
editais vem com valor sigiloso ou por item, e um deles pode ser o maior do dia.
Sigiloso pontua como incógnita — acima de um valor pequeno declarado, abaixo de
um grande.

## Por que existe um validador

```bash
python3 tools/valida_rodada.py <estado.html|estado.json>
```

Em 29/08/2026 o disparo automático da Pauta Thutor terminou em **56 segundos**.
Não pesquisou nada, não publicou nada — e foi registrado como `SUCCEEDED`. O
jornal seguiu mostrando a notícia da véspera e ninguém percebeu, porque uma
execução que falha em silêncio é indistinguível de uma que deu certo.

Aqui o portão é mais rigoroso do que lá, e a razão é a arquitetura: a coleta é
determinística e a própria API informa quantos registros existem no período.
Então não se pergunta "demorou o bastante?" — pergunta-se **"você viu tudo o que
existia?"**. A conta fecha ou não fecha.

A rodada é recusada, com saída 1, quando:

| Situação | Por quê |
|---|---|
| colheu menos do que a API prometeu | faltou página; cada uma são até 50 oportunidades |
| página perdida mesmo após repescagem | idem, e o script já tentou duas vezes |
| modalidade falhou por inteiro | a varredura está incompleta |
| a API não disse quantas existiam e vieram menos de 40 | sem essa conta, é a fonte que mudou de resposta |
| camada 2 ausente, ou menos de 8 fontes | o segmento mais aderente ficou de fora |
| nenhuma fonte externa abriu | ou a rede está bloqueada, ou a camada não rodou |
| triados < candidatos colhidos | alguém não foi lido, e pode ser o contrato do ano |
| rodada durou menos de 5 minutos | as duas camadas levam mais que isso |
| rodada não é de hoje | o radar mostraria a varredura anterior |
| `auth` sumiu | o estado foi corrompido |
| edital sem veredito, ou quente sem justificativa | não passou pela triagem |
| id duplicado, status fora da lista, link sem esquema | dado inventado |

**Volume baixo não reprova, desde que a conta feche.** A API informa quantos
registros existem por modalidade, então a pergunta certa não é "veio bastante
coisa?" e sim "veio tudo o que havia?". Um feriado com 180 contratações e uma
quarta-feira com 5.849 são as duas corretas. Um portão que reprovasse feriado —
e 7 de setembro cai numa segunda — viraria o alarme que se aprende a ignorar.
O piso absoluto sobrou só para o caso em que a verificação não existe: a fonte
parou de informar o total.

**Rodada sem nada quente passa.** Dia sem edital aderente é resultado legítimo —
foi o que aconteceu na camada 2 do dia 03/09: nove fontes visitadas, cinco
abertas, zero candidatos. O que não passa é rodada sem varredura.

### O que a coleta não tem como sobrescrever

`status` e `nota` são de quem trabalha o funil, e a primeira versão os guardava
no próprio estado, com uma instrução no prompt da rotina mandando não tocar
neles. Instrução se esquece — e bastava uma rodada distraída para apagar
semanas de análise.

Hoje eles vivem no banco do artifact. A varredura das 02:00 reescreve a página
inteira todo dia e, estruturalmente, não alcança o banco: não é que ela não
deva: é que não há caminho. O validador guarda a fronteira pelo outro lado, e
reprova a rodada que escrever `status`, `nota` ou `auth` de volta no estado.

Uma regra de prompt virou um fato da arquitetura, e é a única classe de
proteção que sobrevive a quem não leu o prompt.

## Testes

```bash
python3 tools/testes.py            # a suíte inteira
python3 tools/testes.py --rapido   # pula o que precisa de rede
```

Cinco testes, e nenhum decorativo — cada um existe por causa de uma falha que
já aconteceu, aqui ou na Pauta Thutor. O denominador comum é o modo de falha
que este projeto teme: **o silencioso**. Uma coleta que não acha nada se parece
com um dia sem oportunidade, e um radar vazio não reclama.

| Teste | O que protege |
|---|---|
| `teste_perfil.py` | O filtro, contra objetos **reais** de 02/09/2026 — nove casos de ouro que precisam passar, dez de lixo que precisam ser barrados. Inclui a trava contra veto de palavra curta sem `\b`, que já derrubou o melhor edital do dia. |
| `teste_validador.py` | O portão, em 21 cenários: o incidente das 56 segundos, a conta de cobertura, a fronteira do `db` e a distinção entre feriado e falha. |
| `teste_coleta.py` | O **contrato com a API do PNCP**, falando com ela de verdade. |
| `teste_pagina.py` | As duas versões da página num Chromium real, clicando em **cada aba**. |

O teste da API merece explicação, porque é o único que gasta rede. Se o PNCP
renomear `objetoCompra`, mudar `valorTotalEstimado` de número para texto ou
parar de informar `totalRegistros`, **nada estoura**: a coleta roda, os filtros
não encontram nada, e o radar amanhece vazio. O validador tampouco pega — ele
confere que a coleta viu tudo o que a API prometeu, e uma API que promete zero
cumpre a promessa. Por isso o teste conversa com a API real e não com um dublê:
um dublê congela a resposta de hoje e passa a confirmar a suposição de ontem,
que é exatamente o que se quer detectar. Sem rede, ele avisa e sai sem reprovar.

O teste de página cobre as duas versões — a pública e a do artifact, com uma aba
a mais. A da direita não era testada por ninguém até 03/09/2026. Ele clica em
cada aba porque remover a aba administrativa já quebrou as outras uma vez, na
Pauta Thutor, quando `irPara()` continuou percorrendo a lista antiga e
`el("tab-...")` virou `null`. Na versão pública ele também lê o JSON embutido,
para conferir que `auth`, `status` e `nota` não atravessaram, e que o CSS veio
junto — este último por causa de uma publicação real em que o estilo ficou para
trás e três verificações aprovaram assim mesmo.

## Limitações conhecidas

**O PNCP não é o Brasil inteiro.** Ele cobre a administração direta sob a Lei
14.133. Sistema S, estatais sob a Lei 13.303 e alguns conselhos ficam de fora —
daí a camada 2, que é frágil por natureza porque depende de trinta portais que
ninguém controla.

Mas ele cobre mais do que parece, e vale saber o quanto. Medindo o campo
`linkSistemaOrigem` em 1.700 registros de um dia: **81 plataformas distintas**
alimentam o PNCP — Comprasnet/SERPRO à frente, depois Portal de Compras
Públicas, BLL, BNC, Licitar Digital, Licitanet, Pregão Banrisul e dezenas de
portais municipais. O **Licitações-e do Banco do Brasil está entre elas**
(`licitacoes-e2.bb.com.br`, 29 registros), o que significa que a camada 1 já o
alcança e raspá-lo seria trabalho duplicado num site com antirrobô e chave de
acesso paga. Nenhuma estratégia de raspagem cobriria 81 plataformas: é o
argumento mais forte a favor de partir do PNCP.

**A camada 2 depende de rede aberta.** Se o ambiente bloquear egresso, ela cai
para `WebSearch` e perde muito. A Pauta Thutor vive esse teto: a política de
rede de lá libera só artifact, Pages e gerenciadores de pacote, e toda a coleta
passa pelo buscador.

**A varredura não escreve no repositório, e isso virou desenho.** Em 04/09/2026
a rotina das 02:00 rodou certo, publicou o artifact e falhou no último passo:

```
remote: access denied by the git proxy
```

A causa foi verificada com uma rotina-sonda descartável, não deduzida: gatilhos
criados por ferramenta nascem com `sources: []`, `outcomes: []` e
`allowed_push_branches: []`, e não há parâmetro para preenchê-los. Recriar o
gatilho da mesma forma reproduziria o defeito.

O que resolve é criar a SESSÃO com o repositório anexado — aí ela nasce com

```json
"sources":  [{"git_repository": {"url": ".../Busca-Editais-FG",
                                 "revision": "claude/epic-goodall-he30lz"}}],
"outcomes": [{"git_repository": {"git_info": {
               "repo": "wynb9t4n9w-png/busca-editais-fg",
               "branches": ["claude/epic-goodall-he30lz"]}}}]
```

e o push funciona (conferido com um `git push --dry-run` numa sessão de teste).
Um gatilho preso a essa sessão herda a permissão dela.

Daí a divisão de trabalho atual, que é melhor do que a original e não pior:

| | Onde roda | O que faz |
|---|---|---|
| **02:00 varredura** | sessão nova a cada dia | coleta, confere, tria e publica **o artifact**. Não faz commit, não faz push, nem tenta. |
| **06:00 espelho** | conversa fixa, criada com o repositório anexado | lê o artifact, valida, gera `docs/index.html` e empurra |

A sessão nova diária é o lugar certo para a varredura: quarenta minutos de
trabalho complexo pedem contexto limpo, para o julgamento não derivar de um dia
para o outro. E a conversa fixa é o lugar certo para o espelho: a tarefa é
pequena, quase sem estado, e acumula pouco contexto por execução.

O preço, dito por inteiro: **conversa fixa acumula contexto**. Se um dia o
espelho começar a se comportar de forma estranha, o conserto é criar outra
conversa com o repositório anexado e reapontar o gatilho — o procedimento inteiro
está no prompt dela, então recriar custa minutos. E o artifact **nunca** fica
atrasado em nenhum cenário, porque a varredura o publica sem depender de git.

**Credenciamento não é edital.** O Sebrae, o Senar e boa parte do Sistema S
contratam consultoria por credenciamento contínuo. Um radar de editais não
enxerga esse caminho, e ele pode ser o mais curto até o cliente.

## Privacidade

A página pública lista órgãos e objetos de editais — informação pública por
definição. Ela sai com `<meta name="robots" content="noindex,nofollow">`, então
não aparece em buscadores, mas quem tiver o link vê tudo. O acompanhamento
comercial não vai para lá; veja *Como funciona*.

**Sobre o acesso ao acompanhamento.** Houve uma senha aqui, e ela era teatro: o
estado inteiro viajava embutido no HTML, então quem abria o artifact já tinha
`status` e `nota` no código-fonte, com senha ou sem. O portão impedia edição
desatenta, nunca leitura.

Hoje o gate é real e do servidor. A capacidade `db` restringe leitura a quem tem
o artifact e escrita a quem tem permissão de edição; um campo que o visitante
não pode ler não chega ao navegador dele. Em troca, o artifact passa a ser
**interno à organização e não pode ser compartilhado publicamente** — o que,
para um funil comercial, é a troca certa.
