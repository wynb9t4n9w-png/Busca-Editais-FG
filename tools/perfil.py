#!/usr/bin/env python3
"""
O perfil comercial da Thutor traduzido em código.

Este é o coração do projeto. Todo o resto — a varredura do PNCP, o ranking, a
triagem — só faz sentido a partir daqui: dado o texto do objeto de uma
contratação, quanto ela se parece com o que a Thutor vende?

A resposta NÃO é binária de propósito. Falso positivo custa um parágrafo de
leitura; falso negativo custa um contrato de seiscentos mil reais. Então o
filtro é generoso e deixa a decisão fina para a triagem, que lê o objeto
inteiro. O que este arquivo faz é reduzir 5.800 contratações diárias a algumas
dezenas de candidatos — sem descartar nada por engano.

As seis frentes são as do institucional 2025. "Negócios familiares" ficou de
fora: family office e configuração sucessória não são objeto de licitação
pública, e incluir a frente só traria ruído.

Uso:
    python3 tools/perfil.py "texto do objeto"        # explica a pontuação
    python3 tools/perfil.py --termos                 # lista o léxico
"""

import re
import sys
import unicodedata

# ---------------------------------------------------------------------------
# Léxico
# ---------------------------------------------------------------------------
# Três camadas de peso, e a razão de existirem três:
#
#   NUCLEO  — o termo sozinho já descreve um serviço que a Thutor entrega.
#             "cultura organizacional" num objeto de licitação é sempre
#             relevante, não importa o resto da frase.
#   APOIO   — o termo é do campo semântico certo mas é ambíguo sozinho:
#             "capacitação" tanto pode ser de liderança quanto de operação de
#             empilhadeira. Vale ponto, mas não qualifica por si.
#   CONTEXTO— sinais fracos de que o público-alvo é o certo (gestores, alta
#             administração). Servem de desempate.
#
# Os termos são comparados contra o objeto normalizado (sem acento, minúsculo),
# então escreva-os já nessa forma. Prefixos truncados ("lideranc") capturam as
# variações de gênero e número sem precisar listar todas.

NUCLEO: dict[str, list[str]] = {
    "cultura": [
        "cultura organizacional", "clima organizacional", "pesquisa de clima",
        "clima e cultura", "transformacao cultural", "mudanca cultural",
        "diagnostico organizacional", "diagnostico de cultura",
        "mapeamento cultural", "valores organizacionais", "cultura corporativa",
        "engajamento dos colaboradores", "engajamento de equipes",
        "jornada do colaborador", "gestao da mudanca", "endomarketing",
        "qualidade de vida no trabalho", "marca empregadora", "employer branding",
        "pesquisa de engajamento", "clima e engajamento",
    ],
    "estrategia": [
        "planejamento estrategico", "plano estrategico", "planejamento institucional",
        "revisao do planejamento", "gestao estrategica", "mapa estrategico",
        "objetivos e metas", "gestao de metas", "balanced scorecard",
        "painel estrategico", "diretrizes estrategicas", "plano diretor de gestao",
        "modelo de gestao", "gestao para resultados", "gestao por resultados",
        "planejamento participativo", "agenda estrategica",
    ],
    "lideranca": [
        "desenvolvimento de lideranc", "desenvolvimento de lider",
        "formacao de lideranc", "formacao de lider", "programa de lideranc",
        "desenvolvimento gerencial", "capacitacao de gestores",
        "capacitacao de lideranc", "desenvolvimento de gestores",
        "universidade corporativa", "escola de governo", "escola de gestao",
        "educacao corporativa", "trilha de aprendizagem", "trilha de desenvolvimento",
        "academia de lideranc", "formacao de sucessores", "mentoria de executivos",
        "desenvolvimento de equipes", "desenvolvimento de times",
        "programa de desenvolvimento gerencial", "lideranca de alta performance",
    ],
    "eficiencia": [
        "estrutura organizacional", "desenho organizacional", "design organizacional",
        "redesenho organizacional", "modelagem organizacional",
        "reestruturacao organizacional", "reestruturacao administrativa",
        "dimensionamento da forca de trabalho", "dimensionamento de pessoal",
        "forca de trabalho", "workforce planning", "span of control",
        "mapeamento de processos", "escritorio de processos",
        "otimizacao de processos", "modernizacao administrativa",
        "reforma administrativa", "revisao de organograma",
    ],
    "governanca": [
        "governanca corporativa", "conselho de administracao",
        "estruturacao de conselho", "comite de gestao", "comites estrategicos",
        "avaliacao de conselho", "governanca publica", "governanca institucional",
        "modelo de governanca", "estrategia institucional",
        "compliance e integridade", "programa de integridade",
    ],
    "pessoas": [
        "gestao por competencia", "gestao de competencia",
        "mapeamento de competencia", "matriz de competencia",
        "avaliacao de desempenho", "gestao de desempenho",
        "gestao do desempenho", "plano de cargos", "cargos e salarios",
        "plano de carreira", "trilha de carreira", "descricao de cargos",
        "descricao de posic", "politica de remuneracao", "remuneracao variavel",
        "plano de sucessao", "planejamento sucessorio", "banco de talentos",
        "gestao de pessoas por competencia", "politica de gestao de pessoas",
        "plano de desenvolvimento individual", "gestao do conhecimento",
        "levantamento de necessidades de treinamento", "politica de treinamento",
        "plano de capacitacao", "plano anual de capacitacao",
    ],
}

APOIO: dict[str, list[str]] = {
    # "cultura" sozinho NÃO entra: numa varredura real de 5.849 contratações,
    # oito dos 65 candidatos eram oficina de capoeira, coral e feira do livro.
    # Em licitação pública "cultura" é quase sempre cultura artística; só o
    # termo composto ("cultura organizacional") separa uma coisa da outra.
    "cultura": ["engajamento", "comunicacao interna", "integracao de equipes",
                "clima e cultura"],
    "estrategia": ["estrategic", "planejamento", "indicadores de desempenho institucional"],
    "lideranca": [
        "treinamento", "capacitacao", "formacao", "imersao", "workshop",
        "palestra", "mentoria", "coaching", "facilitacao", "oficina",
    ],
    "eficiencia": ["consultoria em gestao", "consultoria organizacional", "assessoria em gestao",
                   "consultoria administrativa", "diagnostico institucional"],
    "governanca": ["governanca", "conselho", "comite"],
    "pessoas": ["gestao de pessoas", "recursos humanos", "desenvolvimento humano",
                "sucessao", "desempenho", "competencia"],
}

CONTEXTO = [
    "servidores", "gestores", "lideranc", "alta administracao", "alta direcao",
    "alta lideranc", "in company", "corpo gerencial", "dirigentes",
    "equipe multidisciplinar", "colaboradores", "empregados publicos",
]

# ---------------------------------------------------------------------------
# Vetos
# ---------------------------------------------------------------------------
# Um veto derruba o candidato mesmo que ele tenha marcado pontos. Ele existe
# porque o léxico acima colide com o vocabulário burocrático: quase toda
# prefeitura tem uma "Secretaria de Administração e Gestão de Pessoas", e ela
# compra papel, computador e gasolina. Sem veto, esses objetos entopem a fila.
#
# Regra de ouro: só entra aqui o que é INEQUIVOCAMENTE outra coisa. Na dúvida,
# deixe passar — a triagem lê o objeto inteiro e descarta em um parágrafo. É
# muito mais barato do que perder um edital de verdade.

VETOS = [
    # bens e materiais
    r"aquisicao de (?:material|equipament|mobiliario|veicul|genero|combustivel|medicament|uniform|\\bpneu\\b|\\btoner\\b|licenc)",
    r"fornecimento de (?:material|equipament|refeic|genero|combustivel|medicament|agua|energia)",
    r"registro de preco(?:s)? .{0,80}?(?:aquisicao|fornecimento|compra) de",
    r"para (?:a )?aquisicao de|visando a aquisicao de",
    r"material (?:de expediente|escolar|de limpeza|permanente|hospitalar|de consumo)",
    r"genero(?:s)? alimentici|merenda|hortifrut|cesta basica",
    # obras e engenharia
    r"pavimentac|recapeament|\\bdrenagem\\b|terraplanagem|calcament|sinalizacao viaria",
    r"(?:construcao|reforma|ampliacao|revitalizacao|manutencao predial) (?:de|do|da|dos|das)",
    r"obra(?:s)? de engenharia|projeto executivo de engenharia",
    # TI como produto
    r"licenca(?:s)? de uso de (?:programa|software|sistema)",
    r"(?:sustentacao|suporte tecnico|manutencao) (?:d[oa]s|de) sistemas",
    r"software de gestao|sistema informatizado|solucao tecnologica|datacenter|link de internet",
    # serviços operacionais
    r"locacao de (?:veicul|imovel|maquin|equipament)",
    r"lavagem|vigilancia (?:armada|patrimonial)|limpeza e conservacao|portaria e recepcao",
    r"transporte escolar|coleta de residuos|servico funerario",
    r"mao de obra terceirizada|cessao de mao de obra|posto de trabalho",
    # saúde e assistência
    r"servicos medic|exames laboratoriais|consultas medicas|\\bleitos\\b|orteses e proteses",
    # concursos e seleção (organizar prova não é o negócio da Thutor)
    r"(?:realizacao|organizacao|execucao|aplicacao) d[eo] concurso publico|concurso publico n?[ºo°]",
    r"banca examinadora|elaboracao e aplicacao de provas|processo seletivo simplificado",
    # patrocínio e eventos de terceiros
    r"contrato de patrocinio|apoio financeiro para (?:a )?participacao",
    r"inscric(?:ao|oes) (?:em|para|de)",
    # --- cultura artística, esporte e eventos -------------------------------
    # A colisão mais cara do léxico. Tudo aqui usa as mesmas palavras que a
    # Thutor usa e não tem nada a ver com o que ela vende.
    r"oficina(?:s)? de (?:music|danc|capoeira|teatro|artesanat|circo|canto|violao|percussao|jiu.?jitsu|karate|luta|xadrez|informatica basica)",
    r"canto (?:coral|lirico)|coral (?:municipal|infantil|adulto)|\\bopera\\b|banda musical",
    r"(?:setor|profissional|produca|producao) artistic|contratacao artistica|atracao musical",
    r"feira do livro|\\bfestival\\b|\\bcarnaval\\b|festa (?:junina|do|da)|\\bdesfile\\b|show musical",
    r"instrutor(?:a)? de (?:recreacao|esporte|educacao fisica|modalidade)",
    r"aulas? de (?:musica|danca|esporte|natacao|futebol|ginastica)",
    r"\\bmaestro\\b|acervo museologic|patrimonio cultural|fundo municipal de cultura",
    r"servicos? esportiv|consultoria esportiva|atividades recreativas",
    # --- compra de vaga em evento de terceiro --------------------------------
    # Comprar assento no curso de outra pessoa não é oportunidade de venda.
    # "in company" é o oposto disso e continua passando.
    r"participacao (?:de|do|da|dos|das) (?:\d+ ?\(?\w*\)? ?)?(?:servidor|vereador|assessor|membro|profissional|represent|aluno|conselheiro)",
    r"cota de participacao|taxa de inscricao|\\banuidade\\b|contribuicao associativa",
    # --- outras consultorias que não são a nossa -----------------------------
    r"(?:assessoria|consultoria) juridic|direito sanitario|assessoria contabil",
    r"consultoria (?:ambiental|tributaria|atuarial|de engenharia|imobiliaria|turistica)",
    r"estudo atuarial|calculo atuarial|educacao ambiental|recursos hidricos",
    # --- alimentação e apoio a evento ---------------------------------------
    r"coffee ?break|kit (?:evento|lanche|alimenta)|\\bbuffet\\b|servico de alimentacao",
    r"infraestrutura e apoio logistico|montagem e desmontagem|locacao de estrutura",
    # --- despesas correntes que caíram no filtro por acaso -------------------
    r"tarifa de energia|registro (?:do|de) dominio|contribuicao (?:anual|sindical)",
    r"^diversos$|^diversos\b",
    # publicidade
    r"agencia de publicidade|veiculacao de (?:publicidade|midia)|assessoria de imprensa",
]
VETOS_RE = [re.compile(v) for v in VETOS]


def _alternativas_de_topo(padrao: str) -> list[str]:
    """
    Fatia o veto pelos "|" de fora dos parenteses. Alternativa dentro de grupo
    ja vem ancorada pelo literal que a precede — em "aquisicao de (?:material|
    veicul)", o "veicul" nunca casa sozinho. So a de topo corre risco.
    """
    partes, atual, prof = [], [], 0
    i = 0
    while i < len(padrao):
        c = padrao[i]
        if c == "\\":
            atual.append(padrao[i:i + 2]); i += 2; continue
        if c == "(":
            prof += 1
        elif c == ")":
            prof -= 1
        elif c == "|" and prof == 0:
            partes.append("".join(atual)); atual = []; i += 1; continue
        atual.append(c); i += 1
    partes.append("".join(atual))
    return partes


def _confere_delimitadores() -> list[str]:
    """
    Um veto de palavra curta e sem \\b casa dentro de outra palavra. Foi assim
    que "opera" derrubou "operacionalizacao" — e com ela o melhor edital de
    02/09/2026, um diagnostico organizacional com mapeamento de processos.

    O erro e barato de cometer e caro de perceber, porque some em silencio: o
    candidato simplesmente nunca aparece na fila, e nao ha nada para estranhar.
    tools/teste_perfil.py chama esta funcao justamente para que ele nao possa
    voltar sem alguem notar.
    """
    suspeitos = []
    for v in VETOS:
        for alt in _alternativas_de_topo(v):
            # Espaco no padrao ja ancora: "canto (?:coral|lirico)" nunca casa
            # no meio de outra palavra.
            if "\\b" in alt or "^" in alt or " " in alt:
                continue
            nu = re.sub(r"\(\?:[^)]*\)|\\[a-zA-Z]|[.*+?\[\]{}()$]", "", alt).strip()
            if nu and len(nu) < 7:
                suspeitos.append(f"{nu!r} no veto {v[:46]!r}")
    return suspeitos


# ---------------------------------------------------------------------------
# Pontuação
# ---------------------------------------------------------------------------
PESO_NUCLEO, PESO_APOIO, PESO_CONTEXTO = 22, 6, 2
TETO_TEMA = 60

# O ticket mínimo da Thutor é R$ 50.000/mês de projeto. Um contrato de seis
# meses nesse ritmo vale R$ 300.000 — é esse o patamar que interessa. Mas valor
# NÃO elimina: quando ele vem zerado, o edital é sigiloso ou tem valor por
# item, e pode perfeitamente ser o maior do dia. Sigiloso pontua como
# incógnita, não como zero.
FAIXAS_VALOR = [
    (600_000, 25),   # 12 meses no ticket mínimo, ou mais
    (300_000, 22),   # 6 meses — o patamar-alvo
    (150_000, 15),
    (50_000, 8),
    (0, 2),          # valor declarado abaixo do ticket mensal: quase certamente pequeno
]
PONTOS_SIGILOSO = 14  # incógnita vale mais que um valor pequeno declarado

# Modalidade diz quanto de disputa real existe. Inexigibilidade quase sempre já
# tem dono — a Thutor só entraria se fosse ela a credenciada.
PONTOS_MODALIDADE = {
    "concorrencia": 10, "pregao": 9, "dispensa": 7, "credenciamento": 8,
    "concurso": 5, "manifestacao": 6, "pre-qualificacao": 6,
    "dialogo": 8, "inexigibilidade": 3, "leilao": 0,
}

LIMIAR_CANDIDATO = 14  # abaixo disto não vale nem o parágrafo de triagem

# A partir de quantos termos de núcleo a evidência temática vence um veto.
# Ver a nota extensa em avalia(): dois é o ponto medido em que só o caso
# legítimo volta, sem trazer ruído junto.
NUCLEOS_QUE_VENCEM_VETO = 2


def normaliza(texto: str | None) -> str:
    """Minúsculo, sem acento, espaços colapsados — a forma em que o léxico vive."""
    s = unicodedata.normalize("NFD", (texto or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s)


def vetado(objeto_norm: str) -> str | None:
    """Devolve o padrão que vetou o objeto, ou None."""
    for rx in VETOS_RE:
        if rx.search(objeto_norm):
            return rx.pattern
    return None


def pontos_valor(valor: float | None) -> tuple[int, bool]:
    """(pontos, sigiloso). Valor ausente ou zerado é incógnita, não zero."""
    if not valor or valor <= 0:
        return PONTOS_SIGILOSO, True
    for piso, pts in FAIXAS_VALOR:
        if valor >= piso:
            return pts, False
    return 0, False


def pontos_modalidade(nome: str | None) -> int:
    n = normaliza(nome)
    for chave, pts in PONTOS_MODALIDADE.items():
        if chave in n:
            return pts
    return 5


def avalia(objeto: str, valor: float | None = None, modalidade: str | None = None,
           complemento: str | None = None) -> dict:
    """
    Pontua uma contratação. O 'complemento' é o campo informacaoComplementar do
    PNCP — às vezes o objeto é lacônico ("contratação de consultoria") e a
    descrição real está lá.
    """
    texto = normaliza(f"{objeto} {complemento or ''}")

    veto = vetado(texto)

    achados: dict[str, dict[str, list[str]]] = {}
    tema = 0
    for frente, termos in NUCLEO.items():
        hits = [t for t in termos if t in texto]
        if hits:
            achados.setdefault(frente, {})["nucleo"] = hits
            tema += PESO_NUCLEO * len(hits)
    for frente, termos in APOIO.items():
        hits = [t for t in termos if t in texto]
        if hits:
            achados.setdefault(frente, {})["apoio"] = hits
            tema += PESO_APOIO * len(hits)
    ctx = [t for t in CONTEXTO if t in texto]
    tema += PESO_CONTEXTO * len(ctx)
    tema = min(tema, TETO_TEMA)

    pv, sigiloso = pontos_valor(valor)
    pm = pontos_modalidade(modalidade)

    # Sem nenhum termo de núcleo, o tema sozinho não sustenta o candidato:
    # "treinamento" + "servidores" pode ser curso de Excel. Exige-se ou um
    # núcleo, ou dois termos de apoio de frentes diferentes.
    frentes_apoio = {f for f, d in achados.items() if "apoio" in d}
    tem_nucleo = any("nucleo" in d for d in achados.values())
    sustenta = tem_nucleo or len(frentes_apoio) >= 2

    # Um veto NÃO aniquila quando o objeto traz evidência forte de núcleo.
    #
    # O veto existe para matar o que só PARECE aderente por uma palavra solta —
    # a retroescavadeira comprada "para atender ao planejamento estratégico".
    # Mas ele é um "ou" contra um "e": basta uma frase em qualquer ponto do
    # texto para zerar tudo, e quanto mais longo e detalhado o objeto, maior a
    # chance de alguma frase infeliz aparecer. Editais bons são justamente os
    # longos e detalhados.
    #
    # Foi assim que o SAAE de Lagoa da Prata/MG quase sumiu: consultoria
    # organizacional para reformular o Plano de Cargos, Carreiras e Salários,
    # com "plano de cargos", "matriz de competência" e "descrição de cargos" no
    # texto — vetado porque, 2.400 caracteres adiante, a metodologia prometia
    # "transparência, participação dos servidores, equidade". A frase disparou o
    # veto de "apoio financeiro para participação", que existe para custeio de
    # inscrição em congresso.
    #
    # Pior: o MESMO edital pontuava 52 ou 0 conforme o endpoint que o trouxesse,
    # porque /publicacao devolve o objeto curto e /proposta devolve o completo.
    #
    # Medido sobre 28.014 contratações com prazo aberto: com o corte em dois
    # termos de núcleo, exatamente UM registro volta — o de Lagoa da Prata, com
    # três núcleos. Zero ruído. Um núcleo só devolveria seis, e aí a fronteira
    # começa a ficar discutível; dois é onde a evidência é inequívoca.
    nucleos = sum(len(d["nucleo"]) for d in achados.values() if "nucleo" in d)
    veto_vale = veto and nucleos < NUCLEOS_QUE_VENCEM_VETO

    score = 0 if (veto_vale or not sustenta) else min(100, tema + pv + pm)

    return {
        "score": score,
        "veto": veto,
        "veto_vencido": bool(veto and not veto_vale),
        "tema": tema,
        "pontos_valor": pv,
        "pontos_modalidade": pm,
        "sigiloso": sigiloso,
        "frentes": sorted(achados),
        "achados": achados,
        "contexto": ctx,
        "veto": veto,
        "sustenta": sustenta,
        "candidato": score >= LIMIAR_CANDIDATO,
    }


def _explica(texto: str) -> None:
    r = avalia(texto)
    print(f"score {r['score']}  (tema {r['tema']} + valor {r['pontos_valor']} + modalidade {r['pontos_modalidade']})")
    print(f"candidato: {r['candidato']}")
    if r["veto"]:
        print(f"VETADO por: {r['veto']}")
    if not r["sustenta"]:
        print("não sustenta: sem termo de núcleo e sem duas frentes de apoio")
    for frente, d in r["achados"].items():
        print(f"  {frente}: " + "; ".join(f"{k}={v}" for k, v in d.items()))
    if r["contexto"]:
        print(f"  contexto: {r['contexto']}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "--termos":
        for frente in NUCLEO:
            print(f"\n=== {frente} ===")
            print("núcleo: " + ", ".join(NUCLEO[frente]))
            print("apoio:  " + ", ".join(APOIO.get(frente, [])))
        print(f"\ncontexto: {', '.join(CONTEXTO)}")
        print(f"\n{len(VETOS)} vetos, limiar de candidato = {LIMIAR_CANDIDATO}")
        return
    _explica(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    main()
