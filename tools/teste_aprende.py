#!/usr/bin/env python3
"""
O ciclo de aprendizado, com um histórico de mentira e desfecho conhecido.

tools/aprende.py é o que faz o mecanismo melhorar em vez de só rodar: ele lê o
histórico e propõe o que a próxima versão do filtro deveria procurar. Se ele
quebrar, nada estoura — o filtro simplesmente congela na versão de hoje, e o
radar continua entregando o mesmo de sempre sem ninguém perceber que parou de
aprender. É a mesma família de falha silenciosa que motivou os outros testes.

O histórico aqui é sintético de propósito: para testar que a proposta é a certa,
é preciso saber de antemão qual é a resposta. Os objetos, esses, são reais.

    python3 tools/teste_aprende.py
"""

import io
import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import aprende  # noqa: E402
import camada2  # noqa: E402


def edital(i, veredito, objeto, orgao="ORGAO X", uf="SP", **extra):
    e = {"id": f"pncp:0000000000019{i}-1-00000{i}-2026", "fonte": "PNCP",
         "orgao": orgao, "uf": uf, "objeto": objeto, "veredito": veredito,
         "disputa": "aberto", "situacao_item": "em_disputa",
         "modalidade": "Pregão - Eletrônico", "esfera": "M", "valor": 400000.0,
         "link": "https://pncp.gov.br/app/editais/x", "score": 70,
         "frentes": ["cultura"], "justificativa": "x" * 30}
    e.update(extra)
    return e


# "mentoria reversa" aparece só nos bons; "empilhadeira" só nos frios. Um deve
# ser proposto como termo, o outro como veto.
ESTADO = {
    "versao": 1,
    "editais": [
        edital(1, "quente", "Programa de mentoria reversa e desenvolvimento de "
               "lideranças femininas na alta administração", orgao="TRIBUNAL ALFA"),
        edital(2, "morno", "Consultoria para programa de mentoria reversa entre "
               "gerações, com trilha de liderança", orgao="TRIBUNAL ALFA"),
        edital(3, "morno", "Contratação de mentoria reversa para o corpo gerencial",
               orgao="PREFEITURA BETA"),
        edital(4, "frio", "Treinamento de operadores de empilhadeira e ponte rolante"),
        edital(5, "frio", "Capacitação em empilhadeira, NR-11, para almoxarifes"),
        edital(6, "frio", "Curso de empilhadeira e movimentação de cargas",
               vencedor={"fornecedor": "FUNDACAO DE APOIO XYZ", "valor": 90000.0}),
    ],
    "rodadas": [{"data": "2026-09-03", "cobertura": {}}] * 6,
    "fontes": {
        "sesc": {"tentativas": 6, "aberturas": 6, "editais": 0, "falhas_seguidas": 0},
        "senar": {"tentativas": 6, "aberturas": 5, "editais": 4, "falhas_seguidas": 0},
        "sebrae-scf": {"tentativas": 6, "aberturas": 0, "editais": 0, "falhas_seguidas": 6},
    },
}


def saida_de(fn, *args) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def main() -> None:
    falhas = []

    print("--- aprende.py sobre um histórico de desfecho conhecido ---")
    out = saida_de(aprende.relatorio, ESTADO, 2)

    casos = [
        ("propõe o termo que só aparece nos bons", "mentoria" in out or "reversa" in out),
        ("propõe veto para o que só aparece nos frios", "empilhadeira" in out),
        ("não propõe termo que o léxico já tem", "lideranc" not in out.split("RUÍDO")[0].split("VOCABULÁRIO")[-1]
         or "lideranca " not in out),
        ("acha o órgão que voltou a comprar", "TRIBUNAL ALFA" in out),
        ("não inventa recorrência onde houve uma só", "PREFEITURA BETA" not in out),
        ("reconhece o padrão das fundações", "fundação" in out.lower() or "fundacao" in out.lower()),
        ("avisa quando a camada 2 não rendeu", "camada 2" in out.lower() or "Nenhum edital veio" in out),
    ]
    for nome, ok in casos:
        print(f"  {'ok ' if ok else 'ERRO'} {nome}")
        if not ok:
            falhas.append(nome)

    # A camada 2 já foi um plano em prosa que um agente lia e visitava a mão.
    # Hoje é código, e o que precisa ser verdade mudou junto: não "a ordem da
    # lista está certa", e sim "o cadastro de fontes é coerente". Uma fonte com
    # id repetido sobrescreve a outra no registro de cobertura e some sem avisar
    # — que é a forma que este projeto mais teme.
    print("\n--- o cadastro de fontes da camada 2 é coerente ---")
    ids = [i for i, _, _, _ in camada2.SONDAS]
    reais = len(camada2.FONTES) - len(camada2.SONDAS)
    conf = [
        ("nenhuma sonda com id repetido", len(ids) == len(set(ids))),
        ("toda sonda diz por escrito por que não rende",
         all(len(nota) > 30 for _, _, _, nota in camada2.SONDAS)),
        ("toda sonda aponta para um endereço https",
         all(u.startswith("https://") for _, _, u, _ in camada2.SONDAS)),
        ("há mais extrator de verdade do que sonda", reais > len(camada2.SONDAS)),
    ]
    for nome, ok in conf:
        print(f"  {'ok ' if ok else 'ERRO'} {nome}")
        if not ok:
            falhas.append(nome)

    print("\n--- histórico vazio não quebra nada ---")
    try:
        saida_de(aprende.relatorio, {"editais": [], "rodadas": []}, 2)
        print("  ok  radar vazio passa sem erro")
    except Exception as e:
        print(f"  ERRO {e}")
        falhas.append(f"quebra com histórico vazio: {e}")

    print()
    if falhas:
        print(f"FALHA: {len(falhas)} problema(s) no ciclo de aprendizado.")
        for f in falhas:
            print(f"  - {f}")
        raise SystemExit(1)
    print("ok  o radar propõe o termo certo, veta o ruído certo, e o cadastro "
          "da camada 2 fecha.")


if __name__ == "__main__":
    main()
