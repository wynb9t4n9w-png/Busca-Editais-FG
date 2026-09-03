#!/usr/bin/env python3
"""
Roda a suíte inteira, e diz o que cada parte protege.

Cinco testes, e nenhum deles é decorativo — cada um existe por causa de uma
falha que já aconteceu, aqui ou na Pauta Thutor:

  perfil     um veto de cinco letras sem delimitador derrubou o melhor edital
             do dia, e sumiu em silêncio
  validador  uma execução de 56 segundos que não pesquisou nada foi registrada
             como sucesso
  coleta     se o PNCP renomear um campo, a varredura roda, não acha nada, e o
             radar amanhece vazio sem ninguém desconfiar
  página     remover a aba administrativa quebrou as outras abas, e o CSS já
             ficou para trás numa publicação sem que nada estourasse
  espelho    o funil comercial não pode atravessar para a versão pública

O denominador comum é o modo de falha que este projeto teme: o silencioso.
Uma coleta que não acha nada se parece com um dia sem oportunidade, e um radar
vazio não reclama.

    python3 tools/testes.py           # tudo
    python3 tools/testes.py --rapido  # pula o que precisa de rede
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# (nome, argumentos, precisa de rede, o que protege)
SUITE = [
    ("perfil", ["tools/teste_perfil.py"], False,
     "o filtro comercial, contra objetos reais do PNCP"),
    ("validador", ["tools/teste_validador.py"], False,
     "o portão que impede publicar uma rodada que não aconteceu"),
    ("coleta", ["tools/teste_coleta.py"], True,
     "o contrato com a API do PNCP — o teste contra a falha silenciosa"),
    ("página pública", ["tools/teste_pagina.py", "docs/index.html"], False,
     "as quatro abas do espelho, o CSS e o vazamento do funil"),
    ("página do artifact", ["tools/teste_pagina.py", "busca-editais-fg.html"], False,
     "as cinco abas da fonte da verdade, com o caminho do acompanhamento"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rapido", action="store_true",
                    help="pula os testes que falam com a internet")
    a = ap.parse_args()

    resultados = []
    for nome, args, rede, protege in SUITE:
        alvo = RAIZ / args[-1] if args[-1].endswith((".html",)) else None
        if alvo and not alvo.exists():
            print(f"— {nome}: {args[-1]} não existe, pulado")
            resultados.append((nome, "pulado", 0.0))
            continue
        if rede and a.rapido:
            print(f"— {nome}: pulado (--rapido)")
            resultados.append((nome, "pulado", 0.0))
            continue

        print(f"\n{'='*70}\n{nome.upper()} — {protege}\n{'='*70}")
        t0 = time.time()
        r = subprocess.run([sys.executable, *args], cwd=RAIZ)
        dur = time.time() - t0
        resultados.append((nome, "ok" if r.returncode == 0 else "FALHOU", dur))

    print(f"\n{'='*70}")
    largura = max(len(n) for n, _, _ in resultados)
    for nome, estado, dur in resultados:
        marca = {"ok": "ok    ", "FALHOU": "FALHOU", "pulado": "-     "}[estado]
        print(f"{marca} {nome:<{largura}}  {dur:5.1f}s" if dur else
              f"{marca} {nome:<{largura}}      —")

    falhou = [n for n, e, _ in resultados if e == "FALHOU"]
    if falhou:
        print(f"\n{len(falhou)} teste(s) reprovado(s): {', '.join(falhou)}")
        print("Não publique enquanto não estiver verde.")
        raise SystemExit(1)
    pulados = sum(1 for _, e, _ in resultados if e == "pulado")
    print(f"\nSuíte verde"
          + (f" ({pulados} pulado(s))" if pulados else "") + ".")


if __name__ == "__main__":
    main()
