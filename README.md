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
| Quem abre | só quem tem acesso na conta Claude | qualquer pessoa com o link |
| Acompanhamento comercial | editável, protegido por senha | não existe |
| Papel | **fonte da verdade** | espelho somente-leitura |

Um edital é informação pública por definição: publicá-lo não vaza nada. Já o
que a Thutor está fazendo com ele, sim. `status: "participando"`, ou uma nota
dizendo quem é o contato dentro do órgão, é o funil comercial da casa — num
repositório público, é o concorrente lendo o pipeline de graça. Por isso o
espelho perde `auth`, `status`, `nota` e a aba Acompanhamento, e
`tools/teste_pagina.py` falha se algum deles atravessar.

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

O registro também aprende: `--relatorio` lê o estado e mostra quais fontes de
fato renderam edital, para que o esforço vá para as que pagam.

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
| menos de 1.500 contratações em dia útil | a API não respondeu (o piso de fim de semana é 60) |
| camada 2 ausente, ou menos de 8 fontes | o segmento mais aderente ficou de fora |
| nenhuma fonte externa abriu | ou a rede está bloqueada, ou a camada não rodou |
| triados < candidatos colhidos | alguém não foi lido, e pode ser o contrato do ano |
| rodada durou menos de 5 minutos | as duas camadas levam mais que isso |
| rodada não é de hoje | o radar mostraria a varredura anterior |
| `auth` sumiu | o estado foi corrompido |
| edital sem veredito, ou quente sem justificativa | não passou pela triagem |
| id duplicado, status fora da lista, link sem esquema | dado inventado |

**Rodada sem nada quente passa.** Dia sem edital aderente é resultado legítimo —
foi o que aconteceu na camada 2 do dia 03/09: nove fontes visitadas, cinco
abertas, zero candidatos. O que não passa é rodada sem varredura.

### O que a coleta nunca sobrescreve

`status` e `nota` são de quem trabalha o funil. A rotina só escreve
`status: "novo"` em edital que ainda não existia; num que já está no radar, ela
atualiza valor, prazo e veredito e não encosta nesses dois campos. Sobrescrevê-
los apagaria análise que não volta.

## Testes

```bash
python3 tools/teste_perfil.py      # o filtro, contra objetos reais do PNCP
python3 tools/teste_validador.py   # o portão, em 18 cenários
python3 tools/teste_pagina.py      # a página num navegador, e o vazamento
```

O primeiro usa objetos **reais** colhidos em 02/09/2026, não exemplos
inventados: nove casos de ouro que precisam passar, dez de lixo que precisam ser
barrados, e a trava contra o veto sem delimitador. O segundo reproduz o
incidente das 56 segundos e a conta de cobertura que a Pauta Thutor não tinha
como fazer. O terceiro abre `docs/index.html` no Chromium, **clica em cada
aba** — porque remover a aba administrativa já quebrou as outras uma vez, na
Pauta Thutor, quando `irPara()` continuou percorrendo a lista antiga e
`el("tab-...")` virou `null` — e depois lê o JSON embutido para conferir que
`auth`, `status` e `nota` não atravessaram.

## Limitações conhecidas

**O PNCP não é o Brasil inteiro.** Ele cobre a administração direta sob a Lei
14.133. Sistema S, estatais sob a Lei 13.303 e alguns conselhos ficam de fora —
daí a camada 2, que é frágil por natureza porque depende de trinta portais que
ninguém controla.

**A camada 2 depende de rede aberta.** Se o ambiente bloquear egresso, ela cai
para `WebSearch` e perde muito. A Pauta Thutor vive esse teto: a política de
rede de lá libera só artifact, Pages e gerenciadores de pacote, e toda a coleta
passa pelo buscador.

**Credenciamento não é edital.** O Sebrae, o Senar e boa parte do Sistema S
contratam consultoria por credenciamento contínuo. Um radar de editais não
enxerga esse caminho, e ele pode ser o mais curto até o cliente.

## Privacidade

A página pública lista órgãos e objetos de editais — informação pública por
definição. Ela sai com `<meta name="robots" content="noindex,nofollow">`, então
não aparece em buscadores, mas quem tiver o link vê tudo. O acompanhamento
comercial não vai para lá; veja *Como funciona*.
