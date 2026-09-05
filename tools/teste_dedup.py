#!/usr/bin/env python3
"""
Duas publicações da mesma disputa viram uma — e duas disputas distintas, não.

O PNCP aceita que o mesmo processo apareça sob sequenciais diferentes: edital e
aviso, ou dois registros criados com minutos de diferença. Medido em
06/09/2026, seis dos setenta e quatro editais do radar eram três pares assim.

Contar dois vale caro nos dois sentidos. Para cima, o agente tria o mesmo objeto
de novo e quem for propor pode mandar proposta em duplicidade achando que são
certames diferentes. Para baixo — unir o que não devia — some uma oportunidade,
e oportunidade que some não reclama. É o erro caro, e é por isso que a regra
exige mesmo valor E cobertura alta de palavras, nunca uma das duas sozinha.

Os quatro casos abaixo são reais, tirados do radar do dia:

    SAAE Lagoa da Prata   mesmo valor, cobertura 0,91  -> UNE
    Caçu                  mesmo valor, cobertura 1,00  -> UNE
    Campo Belo            cobertura 1,00, valores 0 e 25.400  -> NÃO une
    Comando da Marinha    cobertura 0,88, R$ 588 mil e R$ 4,17 mi -> NÃO une

Os dois últimos são a razão de o valor entrar na chave. Sem ele, o texto quase
idêntico de dois lotes distintos os fundiria, e o lote escondido nunca apareceria
para ninguém.

    python3 tools/teste_dedup.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rodada import dedup                              # noqa: E402


def ed(id_, cnpj, valor, objeto, **extra):
    return {"id": id_, "cnpj": cnpj, "valor": valor, "objeto": objeto,
            "link": f"https://pncp.gov.br/app/editais/{cnpj}/2026/{id_}", **extra}


# O par do SAAE: a mesma disputa, uma publicação com o objeto completo e outra
# com o resumo. As aberturas são diferentes ("CONTRATAÇÃO DE EMPRESA
# ESPECIALIZADA NA PRESTAÇÃO DE..." contra "Prestação de Serviços Técnicos..."),
# e foi isso que derrubou a primeira versão da chave, que olhava o começo.
SAAE_LONGO = (
    "CONTRATAÇÃO DE EMPRESA ESPECIALIZADA NA PRESTAÇÃO DE SERVIÇOS TÉCNICOS EM "
    "CONSULTORIA ORGANIZACIONAL, VISANDO À REFORMULAÇÃO DO PLANO DE CARGOS, "
    "CARREIRAS E SALÁRIOS (PCCS) DO SERVIÇO AUTÔNOMO DE ÁGUA E ESGOTO (SAAE) DE "
    "LAGOA DA PRATA/MG, ABRANGENDO TODO O CORPO DE SERVIDORES EFETIVOS DA "
    "AUTARQUIA, COM DIAGNÓSTICO INSTITUCIONAL, MATRIZ DE COMPETÊNCIA, DESCRIÇÃO "
    "DE CARGOS, TABELA DE VENCIMENTOS E MINUTA DE PROJETO DE LEI.")
SAAE_CURTO = (
    "Prestação de Serviços Técnicos em Consultoria Organizacional, visando a "
    "reformulação do Plano de Cargos, Carreiras e Salários (PCCS) do Serviço "
    "Autônomo de Água e Esgoto – SAAE, abrangendo diagnóstico institucional, "
    "matriz de competência e descrição de cargos.")

CACU = ("CONTRATAÇÃO DE EMPRESA ESPECIALIZADA DO RAMO PARA A PRESTAÇÃO DE "
        "SERVIÇOS TÉCNICOS DE PLANEJAMENTO, ORGANIZAÇÃO, COORDENAÇÃO, "
        "OPERACIONALIZAÇÃO, EXECUÇÃO E ACOMPANHAMENTO DE CONCURSO PÚBLICO "
        "DESTINADO AO PROVIMENTO DE CARGOS EFETIVOS DO MUNICÍPIO DE CAÇU/GO.")

CAMPO_BELO = ("CONTRATAÇÃO DE EMPRESA TÉCNICO ESPECIALIZADA PARA A ELABORAÇÃO DE "
              "ESTUDO TÉCNICO DESCRITIVO DE IMPACTO ORÇAMENTÁRIO E FINANCEIRO, "
              "VISANDO SUBSIDIAR A ANÁLISE DE SENSIBILIDADE FISCAL E VIABILIDADE "
              "DO PROJETO DE LEI DO PLANO DE CARREIRA DOS SERVIDORES PÚBLICOS")

MARINHA_A = ("Contratação de empresa credenciada junto à Autoridade Marítima para "
             "a prestação de serviços de planejamento, organização e execução de "
             "cursos do Ensino Profissional Marítimo na Jurisdição da Capitania "
             "dos Portos em Cabo Frio")
MARINHA_B = ("Planejamento, organização e execução integral do Curso de Formação "
             "de Aquaviários CFAQ-MAC/MAM, Ensino Profissional Marítimo, "
             "prestação de serviços de cursos para a Autoridade Marítima")

CASOS = [
    ("par do SAAE: objeto completo e resumo, mesmo valor",
     [ed("91", "18423582000184", 112386.60, SAAE_LONGO),
      ed("92", "18423582000184", 112386.60, SAAE_CURTO)], 1),

    ("par de Caçu: texto idêntico, mesmo valor",
     [ed("49", "01164292000160", 127330.0, "[LICITANET] - " + CACU),
      ed("50", "01164292000160", 127330.0, CACU)], 1),

    ("Campo Belo: mesmo texto, valores diferentes — são dois lotes",
     [ed("511", "18659334000137", 0, CAMPO_BELO),
      ed("512", "18659334000137", 25400.0, CAMPO_BELO)], 0),

    ("Marinha: textos parecidos, valores muito diferentes — dois cursos",
     [ed("11048", "00394502000144", 588420.0, MARINHA_A),
      ed("11049", "00394502000144", 4174584.0, MARINHA_B)], 0),

    ("órgãos diferentes com o mesmo objeto e o mesmo valor",
     [ed("1", "11111111111111", 50000.0, CACU),
      ed("2", "22222222222222", 50000.0, CACU)], 0),

    ("objeto vazio não funde com nada",
     [ed("1", "33333333333333", 50000.0, ""),
      ed("2", "33333333333333", 50000.0, "")], 0),
]


def main() -> None:
    falhas = []
    largura = max(len(n) for n, _, _ in CASOS)
    for nome, editais, esperado in CASOS:
        _, unidas = dedup([dict(e) for e in editais])
        ok = unidas == esperado
        if not ok:
            falhas.append(f"{nome}: esperava {esperado} fusão(ões), houve {unidas}")
        print(f"  {'ok    ' if ok else 'FALHOU'} {nome:<{largura}}  uniu {unidas}")

    # O sobrevivente precisa ser o mais informativo, e precisa apontar o outro
    # registro: quem for propor tem de saber que é um certame só.
    restam, _ = dedup([dict(e) for e in CASOS[0][1]])
    vencedor = restam[0]
    if len(vencedor["objeto"]) != len(SAAE_LONGO):
        falhas.append("o sobrevivente do par do SAAE não é o de objeto mais longo")
    if not vencedor.get("tambem_publicado_como"):
        falhas.append("o sobrevivente não registrou a outra publicação")
    print(f"  {'ok    ' if not falhas else 'FALHOU'} sobrevivente guarda o objeto "
          f"longo e aponta o outro registro")

    if falhas:
        print("\n" + "\n".join("  " + f for f in falhas))
        raise SystemExit(f"\n{len(falhas)} caso(s) reprovado(s).")
    print(f"\nok  {len(CASOS)} casos reais, incluindo os dois pares que NÃO podem "
          "ser unidos — unir esconde oportunidade, e o que some não reclama.")


if __name__ == "__main__":
    main()
