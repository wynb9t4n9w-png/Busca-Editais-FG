#!/usr/bin/env python3
"""
O piso de valor corta o pequeno e preserva o desconhecido.

Participar de licitação custa quase o mesmo trabalho em qualquer tamanho de
contrato — ler o edital, montar proposta técnica, reunir habilitação,
acompanhar sessão. Abaixo de R$ 500.000 a conta não fecha nem ganhando, e foi
por isso que o piso entrou em 09/09/2026.

A parte que este teste protege é a OUTRA metade da regra, a que é fácil de
quebrar sem perceber: valor sigiloso ou não declarado NÃO é valor baixo. Medido
no radar daquele dia, 14 dos 66 editais não declaravam valor. Um filtro escrito
como `valor >= 500_000` apagaria os catorze junto com os pequenos, e a
assimetria é violenta: manter cada incógnita custa um parágrafo de triagem por
noite; descartar uma pode custar o contrato do ano.

    python3 tools/teste_valor.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perfil import VALOR_MINIMO, vale_o_trabalho     # noqa: E402

CASOS = [
    ("Barueri, diagnóstico institucional — o melhor achado do radar",
     2_312_225.0, False, True),
    ("exatamente no piso passa", VALOR_MINIMO, False, True),
    ("um centavo abaixo do piso não passa", VALOR_MINIMO - 0.01, False, False),
    ("CREA-PB, R$ 47 mil — tema certo, porte que não paga a proposta",
     47_140.5, False, False),
    ("carimbos de R$ 690", 690.0, False, False),

    # A metade que este arquivo existe para defender:
    ("sigiloso declarado: incógnita, e incógnita fica", 0.0, True, True),
    ("valor zerado sem flag: também incógnita", 0.0, False, True),
    ("valor ausente: idem", None, False, True),
    ("valor ausente e sigiloso: idem", None, True, True),
    ("sigiloso com valor pequeno gravado por engano continua incógnita",
     1_000.0, True, True),
]


def main() -> None:
    falhas = []
    largura = max(len(n) for n, _, _, _ in CASOS)
    for nome, valor, sigiloso, esperado in CASOS:
        got = vale_o_trabalho(valor, sigiloso)
        ok = got is esperado
        if not ok:
            falhas.append(f"{nome}: esperava {esperado}, veio {got}")
        v = "incógnita" if not valor else f"R$ {valor:,.2f}"
        print(f"  {'ok    ' if ok else 'FALHOU'} {nome:<{largura}}  {v:>16} -> "
              f"{'fica' if got else 'fora'}")

    if falhas:
        print("\n" + "\n".join("  " + f for f in falhas))
        raise SystemExit(f"\n{len(falhas)} caso(s) reprovado(s).")
    print(f"\nok  piso de R$ {VALOR_MINIMO:,.0f}, e as cinco formas de dizer "
          "'não sei o valor' continuam passando.")


if __name__ == "__main__":
    main()
