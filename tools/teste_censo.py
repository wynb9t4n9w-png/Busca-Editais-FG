#!/usr/bin/env python3
"""
O censo de fontes: quem publica no PNCP, contado antes de qualquer corte.

O que estes casos protegem é uma distinção que custa caro errar. Quando um
comprador grande nunca aparece no radar, há duas explicações incompatíveis —
ele não compra o nosso tema, ou ele não publica onde olhamos — e elas pedem
trabalhos opostos: mexer no filtro, ou escrever um raspador. O censo existe
para separá-las, e só separa se contar o registro CRU: se ele contasse depois
do corte de score, todo comprador que não compra consultoria pareceria ausente
do PNCP, que é justamente o erro que se quer evitar.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coleta_pncp import anota_censo          # noqa: E402
from rodada import unifica_censo, funde_censo  # noqa: E402
from fontes import VIGILANCIA                # noqa: E402

falhas: list[str] = []


def checa(nome: str, condicao: bool, detalhe: str = "") -> None:
    print(f"  {'ok  ' if condicao else 'FALHOU'} {nome}"
          + ("" if condicao else f"   <<< {detalhe}"))
    if not condicao:
        falhas.append(nome)


def reg(cnpj: str, nome: str = "ORGAO", uf: str = "SP") -> dict:
    return {"orgaoEntidade": {"cnpj": cnpj, "razaoSocial": nome, "esferaId": "F"},
            "unidadeOrgao": {"ufSigla": uf}}


ANVISA = next(c for c, (n, _) in VIGILANCIA.items() if n == "ANVISA")

print("=== o que entra no censo ===")

c: dict = {}
anota_censo(c, reg("11111111111111", "MUNICIPIO DE QUALQUER"), False)
checa("órgão sem tema e fora da vigilância não entra", c == {},
      f"entrou: {c}")

c = {}
anota_censo(c, reg(ANVISA, "ANVISA", "DF"), False)
checa("órgão da vigilância entra mesmo pontuando zero",
      ANVISA in c and c[ANVISA]["tema"] == 0 and c[ANVISA]["brutos"] == 1,
      f"{c}")

c = {}
anota_censo(c, reg("22222222222222", "PREFEITURA QUE COMPRA O TEMA", "MG"), True)
checa("órgão que pontua no tema entra",
      c.get("22222222222222", {}).get("tema") == 1, f"{c}")

c = {}
anota_censo(c, {"orgaoEntidade": {}, "unidadeOrgao": {}}, True)
checa("registro sem CNPJ é ignorado sem estourar", c == {}, f"{c}")

# A razão de ser do censo, em um caso: a ANVISA precisa aparecer como PRESENTE
# com zero do tema. "Presente e não compra" é o diagnóstico que manda mexer no
# filtro; "ausente" é o que manda escrever raspador. Se o censo só contasse o
# que pontua, os dois virariam a mesma coisa.
c = {}
for _ in range(40):
    anota_censo(c, reg(ANVISA, "ANVISA", "DF"), False)
checa("presente-sem-tema é distinguível de ausente",
      c[ANVISA]["brutos"] == 40 and c[ANVISA]["tema"] == 0, f"{c}")

print()
print("=== soma das duas varreduras ===")

a = {"33333333333333": {"nome": "X", "uf": "SP", "esfera": "M", "brutos": 2, "tema": 1}}
b = {"33333333333333": {"nome": "NOME BEM MAIS LONGO", "uf": "SP", "esfera": "M",
                        "brutos": 3, "tema": 2},
     "44444444444444": {"nome": "Y", "uf": "BA", "esfera": "E", "brutos": 1, "tema": 1}}
unifica_censo(a, b)
checa("os totais somam", a["33333333333333"]["brutos"] == 5
      and a["33333333333333"]["tema"] == 3, f"{a['33333333333333']}")
checa("fica o nome mais longo", a["33333333333333"]["nome"] == "NOME BEM MAIS LONGO",
      a["33333333333333"]["nome"])
checa("órgão só da segunda varredura entra", "44444444444444" in a, f"{list(a)}")

print()
print("=== acúmulo entre rodadas ===")

d1 = funde_censo(None, {"55555555555555": {"nome": "Z", "uf": "PR", "esfera": "M",
                                           "brutos": 4, "tema": 2}}, "2026-09-10")
checa("primeira aparição marca `primeiro` e `ultimo`",
      d1["55555555555555"]["primeiro"] == "2026-09-10"
      and d1["55555555555555"]["ultimo"] == "2026-09-10", f"{d1}")
checa("primeira rodada conta 1 dia", d1["55555555555555"]["dias"] == 1,
      f"{d1['55555555555555']['dias']}")

d2 = funde_censo(d1, {"55555555555555": {"nome": "Z", "uf": "PR", "esfera": "M",
                                         "brutos": 6, "tema": 1}}, "2026-09-11")
z = d2["55555555555555"]
checa("`dias` conta rodadas, não contratações", z["dias"] == 2, f"{z['dias']}")
checa("os totais acumulam", z["brutos"] == 10 and z["tema"] == 3, f"{z}")
checa("`primeiro` não se mexe", z["primeiro"] == "2026-09-10", z["primeiro"])
checa("`ultimo` anda", z["ultimo"] == "2026-09-11", z["ultimo"])

# Quem não apareceu hoje continua no censo com a data antiga: é assim que se
# descobre que uma fonte morreu. Zerar seria apagar a evidência do sumiço.
d3 = funde_censo(d2, {}, "2026-09-12")
checa("quem não apareceu hoje guarda a data antiga",
      d3["55555555555555"]["ultimo"] == "2026-09-11"
      and d3["55555555555555"]["dias"] == 2, f"{d3['55555555555555']}")

print()
print("=== o cadastro de vigilância ===")
checa("todo CNPJ da vigilância tem 14 dígitos",
      all(len(c) == 14 and c.isdigit() for c in VIGILANCIA),
      str([c for c in VIGILANCIA if len(c) != 14 or not c.isdigit()]))
checa("nenhum nome repetido na vigilância",
      len({n for n, _ in VIGILANCIA.values()}) == len(VIGILANCIA))

print()
print("=== o relatório não afirma antes de poder ===")

# Este caso existe porque o defeito aconteceu: a primeira versão media a
# maturidade do censo pelo número de RODADAS do histórico, não pelo tempo que o
# censo existe. Com oito rodadas registradas e uma única noite de censo, o
# relatório afirmava "ausência sustentada" sobre órgãos que tivera uma chance de
# ver. É o erro do vigia de 09/09 outra vez: conclusão coerente com o que se
# viu, e falsa.
import io, contextlib
from aprende import censo_fontes                      # noqa: E402

def saida(dias: int) -> str:
    est = {"fontes_pncp": {ANVISA: {"nome": "ANVISA", "uf": "DF", "esfera": "F",
                                    "brutos": 12, "tema": 0, "dias": dias,
                                    "primeiro": "2026-09-04", "ultimo": "2026-09-10"}}}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        censo_fontes(est, 99)       # 99 rodadas no histórico, de propósito
    return buf.getvalue()

novo, maduro = saida(1), saida(7)
checa("censo de 1 rodada NÃO fala em ausência sustentada",
      "sustentada" not in novo and "ainda NÃO distingue" in novo, novo[-160:])
checa("censo de 7 rodadas fala", "sustentada" in maduro, maduro[-160:])
checa("a maturidade vem do censo, não do histórico de rodadas",
      "1 rodada(s)" in novo and "7 rodadas" in maduro,
      "o número exibido não veio de `dias`")

print()
if falhas:
    print(f"FALHA: {len(falhas)} caso(s) — {', '.join(falhas)}")
    sys.exit(1)
print("ok  o censo conta o registro cru, soma as duas varreduras e acumula por rodada")
