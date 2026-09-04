#!/usr/bin/env python3
"""
Casos de ouro e casos de lixo do filtro.

Todos os textos abaixo são objetos REAIS, colhidos do PNCP em 02/09/2026 —
5.849 contratações num único dia. Não há exemplo inventado aqui de propósito:
o valor deste arquivo está em ser um retrato do que a fonte de fato publica,
com os empates e as ambiguidades que só aparecem em dado real.

O filtro é uma peneira com duas maneiras de errar, e elas não custam a mesma
coisa. Deixar passar lixo custa um parágrafo de leitura na triagem. Barrar um
edital bom custa um contrato — e some em silêncio, porque ninguém sente falta
do que nunca apareceu na lista. Por isso os casos de ouro são inegociáveis e
os de lixo toleram alguma frouxidão.

    python3 tools/teste_perfil.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from perfil import avalia, _confere_delimitadores  # noqa: E402

# (objeto, valor, modalidade, por que importa)
OURO = [
    ("Contratação de instituição especializada para desenvolvimento e implementação "
     "da Universidade Corporativa em Rede do Conselho Regional de Corretores de "
     "Imóveis de Santa Catarina – UniCRECI em Rede, contemplando planejamento "
     "metodológico, trilhas de aprendizagem e formação de multiplicadores",
     1_500_000, "Dispensa",
     "Universidade Corporativa está no portfólio, p.8 do institucional 2025"),

    ("Contratação empresa especializada para a prestação de serviços de assessoria e "
     "consultoria administrativa para realização de diagnóstico organizacional, "
     "mapeamento de processos internos, modelagem de fluxos administrativos "
     "(AS IS e TO BE), elaboração de fluxogramas e redesenho de procedimentos",
     60_000, "Dispensa",
     "frente Eficiência e Gestão — foi este que o veto 'opera' derrubou por engano"),

    ("Contratação de capacitação in company de Governança Corporativa para Empresas "
     "Estatais, com carga horária de 10 horas/aula, na modalidade online e ao vivo",
     62_406, "Inexigibilidade",
     "frente Governança; 'in company' é venda, não compra de assento"),

    ("FUTURA E EVENTUAL CONTRATAÇÃO DE EMPRESA ESPECIALIZADA PARA PRESTAÇÃO DE "
     "SERVIÇOS DE CAPACITAÇÃO E TREINAMENTO EM GESTÃO DE PESSOAS E RECURSOS HUMANOS, "
     "NA MODALIDADE HÍBRIDA, MEDIANTE REALIZAÇÃO DE CURSOS, PALESTRAS E OFICINAS",
     50_000, "Dispensa",
     "o objeto diz exatamente o que a Thutor faz"),

    # Sintéticos, para as frentes que não apareceram naquele dia específico.
    ("Contratação de consultoria para elaboração do Planejamento Estratégico "
     "Institucional 2027-2031, incluindo mapa estratégico, objetivos e metas",
     480_000, "Concorrência - Eletrônica", "frente Estratégia"),
    ("Contratação de empresa para realização de pesquisa de clima organizacional e "
     "diagnóstico da cultura organizacional junto aos servidores",
     220_000, "Pregão - Eletrônico", "frente Cultura, o carro-chefe da casa"),
    ("Serviços técnicos para dimensionamento da força de trabalho e revisão da "
     "estrutura organizacional da autarquia",
     900_000, "Concorrência - Eletrônica", "frente Eficiência — span of control"),
    ("Consultoria para implantação de gestão por competências, mapeamento de "
     "competências e programa de avaliação de desempenho dos servidores",
     650_000, "Pregão - Eletrônico", "frente Pessoas"),
    ("Programa de desenvolvimento gerencial para o corpo de gestores, com trilha de "
     "desenvolvimento da liderança e formação de sucessores",
     1_200_000, "Concorrência - Eletrônica", "frente Desenvolvimento de Líderes"),
]

LIXO = [
    ("Registro de Preços para o fornecimento de EQUIPAMENTOS DE INFORMÁTICA E "
     "SUPRIMENTOS, através da Secretaria de Administração e Gestão de Pessoas do "
     "Município", 270_977, "Pregão - Eletrônico",
     "quase toda prefeitura tem 'Secretaria de Gestão de Pessoas' e ela compra tudo"),

    ("A presente licitação tem por objeto o Registro de Preço para eventual "
     "contratação de empresa especializada para aquisição de óleo lubrificante para "
     "toda a frota, para atender as Secretarias Municipais de Serviços Urbanos",
     1_210_158, "Pregão - Eletrônico",
     "a compra vem depois de 'contratação de empresa' e escapava do veto"),

    ("Constitui objeto deste Edital o credenciamento de microempreendedores "
     "individuais interessados na prestação de serviços de instrutor de oficina de "
     "capoeira, incluindo aulas teóricas e práticas", 30_000, "Credenciamento",
     "em licitação pública 'cultura' quase sempre é cultura artística"),

    ("Prestação de serviços artísticos especializados para desenvolvimento e execução "
     "do Projeto Coral Luzes de Natal, compreendendo ensaios de canto coral e "
     "formação musical dos participantes", 12_500, "Inexigibilidade",
     "coral, canto, formação — três palavras do nosso léxico, nada a ver"),

    ("A contratação de serviços de fornecimento de coffee break justifica-se pela "
     "necessidade de atendimento aos eventos institucionais, quais sejam, fórum de "
     "diretores gerais e encontro de lideranças", 9_900, "Dispensa",
     "'fórum de diretores' e 'lideranças' num contrato de coffee break"),

    ("Contratação de instituição para planejamento, organização e realização do "
     "Concurso Público 01/2026 visando a formação de cadastro reserva",
     467_850, "Dispensa",
     "organizar concurso não é o negócio da Thutor"),

    ("Participação de 02 (dois) servidores desta Agência Reguladora no 21º Encontro "
     "Nacional de Secretariado e Gestão de Pessoas", None, "Inexigibilidade",
     "comprar assento no evento de outro não é oportunidade de venda"),

    ("CONTRATAÇÃO DE PESSOA JURÍDICA PARA SERVIÇOS ESPECIALIZADOS DE CONSULTORIA E "
     "ASSESSORIA JURÍDICA EM DIREITO SANITÁRIO E ADMINISTRAÇÃO PÚBLICA, DESTINADOS À "
     "REALIZAÇÃO DE ESTUDO E DIAGNÓSTICO", 430_000, "Inexigibilidade",
     "consultoria sim, nossa não"),

    ("Contratação de empresa especializada para ministrar capacitação em Educação "
     "Ambiental e Gestão Participativa em Recursos Hídricos para os membros dos "
     "Comitês de Bacias Hidrográficas", 22_250, "Inexigibilidade",
     "'gestão participativa' e 'comitês' são nossos; o assunto não é"),

    ("Contratação de empresa especializada na confecção de camisetas personalizadas "
     "em malha Dry Fit para a Secretaria Municipal de Desenvolvimento Social",
     70_000, "Pregão - Eletrônico", "camiseta"),
]


def _testa_disputa(falhas: list[str]) -> None:
    """
    A modalidade decide antes do prazo e antes do status do item.

    Inexigibilidade não é disputa encerrada, é disputa que a lei declarou
    inviável — e o radar já exibiu como oportunidade um processo de R$ 30,5
    milhões da SEDUC-PA com o contrato da FGV anexado, porque o item ainda
    dizia "Em andamento".
    """
    from coleta_pncp import disputa_provisoria
    casos = [
        ({"dataEncerramentoProposta": None, "modalidadeNome": "Inexigibilidade"},
         "inexigivel", "inexigibilidade sem prazo"),
        ({"dataEncerramentoProposta": "2099-01-01T09:00:00",
          "modalidadeNome": "Inexigibilidade"},
         "inexigivel", "inexigibilidade COM prazo declarado — a modalidade manda"),
        ({"dataEncerramentoProposta": None, "modalidadeNome": "Dispensa"},
         "decidido", "dispensa direta"),
        ({"dataEncerramentoProposta": "2099-01-01T09:00:00", "modalidadeNome": "Dispensa"},
         "aberto", "dispensa eletrônica, com janela real"),
        ({"dataEncerramentoProposta": "2099-01-01T09:00:00",
          "modalidadeNome": "Pregão - Eletrônico"}, "aberto", "pregão em aberto"),
    ]
    print("\n--- a modalidade decide a disputa ---")
    for reg, esperado, porque in casos:
        got = disputa_provisoria(reg)
        ok = got == esperado
        print(f"  {'ok ' if ok else 'ERRO'} {got:14s} · {porque}")
        if not ok:
            falhas.append(f"disputa de {porque}: esperado {esperado}, veio {got}")


def main() -> None:
    falhas = []

    # 1) A trava contra o erro que já aconteceu.
    suspeitos = _confere_delimitadores()
    if suspeitos:
        falhas.append(
            "vetos de palavra curta sem \\b — casam dentro de outra palavra, "
            "que foi como 'opera' matou 'operacionalização':\n      "
            + "\n      ".join(suspeitos)
        )

    # 2) Ouro: barrar qualquer um destes é perder contrato.
    print("--- casos de ouro (precisam passar) ---")
    for objeto, valor, mod, porque in OURO:
        r = avalia(objeto, valor, mod)
        ok = r["candidato"]
        print(f"  {'ok ' if ok else 'ERRO'} score {r['score']:3d} · {porque}")
        if not ok:
            motivo = (f"vetado por {r['veto']}" if r["veto"]
                      else "não sustenta (sem núcleo e sem duas frentes de apoio)"
                      if not r["sustenta"] else f"score {r['score']} abaixo do limiar")
            falhas.append(f"OURO barrado ({porque}): {motivo}\n      {objeto[:110]}")

    # 3) Lixo: passar um destes custa um parágrafo, não um contrato.
    print("\n--- casos de lixo (precisam ser barrados) ---")
    for objeto, valor, mod, porque in LIXO:
        r = avalia(objeto, valor, mod)
        ok = not r["candidato"]
        print(f"  {'ok ' if ok else 'ERRO'} score {r['score']:3d} · {porque}")
        if not ok:
            falhas.append(f"LIXO aprovado ({porque}), score {r['score']}, "
                          f"frentes {r['frentes']}\n      {objeto[:110]}")

    # 4) Valor não pode eliminar: edital sigiloso é incógnita, não zero.
    print("\n--- regras de valor ---")
    sig = avalia("Contratação de consultoria para pesquisa de clima organizacional",
                 None, "Pregão - Eletrônico")
    peq = avalia("Contratação de consultoria para pesquisa de clima organizacional",
                 12_000, "Pregão - Eletrônico")
    gra = avalia("Contratação de consultoria para pesquisa de clima organizacional",
                 800_000, "Pregão - Eletrônico")
    print(f"  sigiloso {sig['score']} · pequeno {peq['score']} · grande {gra['score']}")
    if not sig["candidato"]:
        falhas.append("edital de valor sigiloso foi barrado — sigiloso é incógnita, "
                      "não zero, e pode ser o maior do dia.")
    if not (gra["score"] > sig["score"] > peq["score"]):
        falhas.append(f"a ordem de valor não faz sentido: grande {gra['score']}, "
                      f"sigiloso {sig['score']}, pequeno {peq['score']}.")

    _testa_disputa(falhas)

    print()
    if falhas:
        print(f"FALHA: {len(falhas)} problema(s) no filtro.")
        for f in falhas:
            print(f"  - {f}")
        raise SystemExit(1)
    print(f"ok  {len(OURO)} casos de ouro passam, {len(LIXO)} casos de lixo barrados, "
          "vetos delimitados, valor não elimina, inexigibilidade nunca é disputa.")


if __name__ == "__main__":
    main()
