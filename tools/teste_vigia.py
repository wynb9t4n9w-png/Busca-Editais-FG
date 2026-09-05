#!/usr/bin/env python3
"""
O vigia pega a rodada que não aconteceu?

`checa_rodada.py` nasceu de um caso concreto: em 05/09/2026 a varredura das
02:00 rodou 3 minutos e 45 segundos, terminou com status de sucesso e não
publicou nada. Todos os portões do projeto aprovaram — porque nenhum deles foi
acionado. Um portão só protege quem passa por ele, e uma rodada que morre no
caminho nunca chega até lá.

Um vigia que nunca foi testado é só mais uma coisa em que confiar sem motivo.
Cada cenário aqui é uma forma de a rodada não estar no ar, e a primeira é
exatamente o que aconteceu naquele dia.

    python3 tools/teste_vigia.py
"""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TZ = timezone(timedelta(hours=-3))
HOJE = datetime.now(TZ).date()
ONTEM = HOJE - timedelta(days=1)


def bom() -> dict:
    """Uma rodada saudável de hoje, do jeito que a rotina deveria publicar."""
    return {
        "versao": 1,
        "atualizado_em": datetime.now(TZ).isoformat(timespec="seconds"),
        "editais": [{"id": "pncp:1-1-000001-2026", "orgao": "X"}],
        "rodadas": [{
            "data": HOJE.isoformat(),
            "cobertura": {
                "iniciado_em": datetime.now(TZ).isoformat(timespec="seconds"),
                "concluido_em": datetime.now(TZ).isoformat(timespec="seconds"),
                "pncp": {"brutos": 5412, "esperados": 5412, "candidatos": 15},
                "triados": 15,
            },
        }],
    }


# ── os cenários ──

def _rodada_de_ontem(e):
    """O caso de 05/09/2026: a rodada mais nova é da véspera."""
    e["rodadas"][0]["data"] = ONTEM.isoformat()
    e["atualizado_em"] = (datetime.now(TZ) - timedelta(days=1)).isoformat(timespec="seconds")

def _sem_rodada_nenhuma(e):
    e["rodadas"] = []

def _rodada_fora_da_posicao_zero(e):
    # A página lê sempre a [0]. Existir na lista não basta.
    e["rodadas"].insert(0, {"data": ONTEM.isoformat(), "cobertura": {}})

def _coleta_vazia(e):
    # Registrar o fracasso como se fosse um dia calmo é o modo de falha que
    # este projeto teme desde o primeiro dia.
    e["rodadas"][0]["cobertura"]["pncp"]["brutos"] = 0

def _varredura_incompleta(e):
    e["rodadas"][0]["cobertura"]["pncp"]["brutos"] = 4000

def _publicada_no_meio(e):
    e["rodadas"][0]["cobertura"].pop("concluido_em")

def _triagem_incompleta(e):
    e["rodadas"][0]["cobertura"]["triados"] = 3

def _carimbo_velho(e):
    # A rodada está na lista, mas o cabeçalho da página mente para quem abre.
    e["atualizado_em"] = (datetime.now(TZ) - timedelta(days=3)).isoformat(timespec="seconds")

def _carimbo_ausente(e):
    e.pop("atualizado_em")


CENARIOS = [
    ("rodada saudável de hoje",            lambda e: None,             False, "ok"),
    ("a rodada mais nova é de ontem",      _rodada_de_ontem,           True,  "NÃO HÁ RODADA"),
    ("estado sem rodada nenhuma",          _sem_rodada_nenhuma,        True,  "NENHUMA rodada"),
    ("rodada de hoje fora da posição 0",   _rodada_fora_da_posicao_zero, True, "posição"),
    ("coleta devolveu zero contratações",  _coleta_vazia,              True,  "não aconteceu"),
    ("varredura incompleta",               _varredura_incompleta,      True,  "incompleta"),
    ("publicada antes de terminar",        _publicada_no_meio,         True,  "concluido_em"),
    ("triagem menor que os candidatos",    _triagem_incompleta,        True,  "triou"),
    ("carimbo de três dias atrás",         _carimbo_velho,             True,  "horas atrás"),
    ("estado sem atualizado_em",           _carimbo_ausente,           True,  "atualizado_em"),
]


def main() -> None:
    falhas = []
    largura = max(len(n) for n, _, _, _ in CENARIOS)

    with tempfile.TemporaryDirectory() as tmp:
        for nome, mexe, deve_reprovar, trecho in CENARIOS:
            e = bom()
            mexe(e)
            p = Path(tmp) / "estado.json"
            p.write_text(json.dumps(e, ensure_ascii=False), encoding="utf8")

            r = subprocess.run([sys.executable, "tools/checa_rodada.py", str(p)],
                               cwd=RAIZ, capture_output=True, text=True)
            reprovou = r.returncode != 0
            saida = r.stdout + r.stderr

            if reprovou != deve_reprovar:
                falhas.append(
                    f"{nome}: esperava {'reprovar' if deve_reprovar else 'aprovar'}, "
                    f"e {'reprovou' if reprovou else 'aprovou'}")
                marca = "FALHOU"
            elif trecho.lower() not in saida.lower():
                # Uma mensagem que não diz o que houve manda o leitor adivinhar,
                # e às 06:00 quem lê é outro agente com quatro horas de prazo.
                falhas.append(f"{nome}: a mensagem não menciona {trecho!r}")
                marca = "FALHOU"
            else:
                marca = "ok    "
            print(f"  {marca} {nome:<{largura}}  saída {r.returncode}")

    if falhas:
        print("\n" + "\n".join("  " + f for f in falhas))
        raise SystemExit(f"\n{len(falhas)} cenário(s) reprovado(s).")
    print(f"\nok  {len(CENARIOS)} cenários, incluindo a reprodução exata do "
          "silêncio de 05/09/2026.")


if __name__ == "__main__":
    main()
