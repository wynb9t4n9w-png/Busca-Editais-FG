#!/usr/bin/env python3
"""
A rodada de hoje entrou no ar? — o vigia que faltava.

Em 05/09/2026 a varredura das 02:00 rodou por 3 minutos e 45 segundos, terminou
com status SUCCEEDED, e não publicou nada. O radar amanheceu com a rodada da
véspera, o carimbo do cabeçalho dizia "04/09", e ninguém foi avisado. Quem
descobriu foi uma pessoa abrindo a página.

Esse é o modo de falha que este projeto inteiro foi construído para não ter, e
ele passou pela porta que ninguém tinha trancado. Todos os portões existentes
perguntam se o DADO está certo:

    valida_rodada.py   os números batem? a cobertura fecha? o quente é disputável?
    teste_pagina.py    as abas abrem? vazou campo interno?
    testes.py          o filtro ainda discrimina? o aprendizado roda?

Nenhum deles pergunta se A RODADA ACONTECEU. Um portão só é acionado quando
alguém chega até ele — e uma rodada que morre no caminho nunca chega. Portão
nenhum protege contra a ausência.

Este script pergunta a ausência, e é de propósito que ele NÃO olhe o arquivo
local: ele lê o estado que a rotina publicou. É a única evidência que importa,
porque é a que a equipe abre de manhã.

    python3 tools/checa_rodada.py <estado.html|.json>
    python3 tools/checa_rodada.py <estado.html> --data 2026-09-05
    python3 tools/checa_rodada.py <estado.html> --toleranica-horas 30

Saída 0 = a rodada do dia está lá e é sólida. Saída 1 = não está, e a mensagem
diz o que fazer. Quem chama é a rotina das 06:00, que roda quatro horas depois
e tem tudo de que precisa para refazer o serviço.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=-3))          # America/Sao_Paulo, sem DST desde 2019
DADOS_RE = re.compile(r"/\*DADOS\*/(.*?)/\*FIM\*/", re.S)

# Uma rodada pode ser magra num feriado, mas não pode ser vazia: se a coleta
# devolveu zero contratações brutas, ela não varreu o PNCP — ela falhou e
# registrou o fracasso como se fosse um dia calmo.
MINIMO_BRUTOS = 200

problemas: list[str] = []


def falha(msg: str) -> None:
    problemas.append(msg)


def carrega(caminho: Path) -> dict:
    txt = caminho.read_text(encoding="utf8")
    if caminho.suffix.lower() == ".json":
        return json.loads(txt)
    m = DADOS_RE.search(txt)
    if not m:
        raise SystemExit(f"FALHA: {caminho} não tem o bloco /*DADOS*/…/*FIM*/. "
                         "Não é um estado do Busca Editais FG.")
    return json.loads(m.group(1))


def confere(estado: dict, dia: str, tolerancia_horas: float) -> None:
    rodadas = estado.get("rodadas") or []
    if not rodadas:
        falha("o estado não tem NENHUMA rodada. O radar nunca rodou, ou o "
              "estado publicado foi sobrescrito por um vazio.")
        return

    # A rodada do dia precisa estar na posição 0. Se ela existe mas está no meio
    # da lista, alguma coisa inseriu fora de ordem — e a página lê sempre a [0].
    datas = [r.get("data") for r in rodadas]
    if dia not in datas:
        ultima = datas[0] or "?"
        atraso = ""
        try:
            d1 = datetime.strptime(dia, "%Y-%m-%d")
            d2 = datetime.strptime(ultima, "%Y-%m-%d")
            dias = (d1 - d2).days
            atraso = f" — {dias} dia(s) de atraso" if dias > 0 else ""
        except ValueError:
            pass
        falha(f"NÃO HÁ RODADA DE {dia}. A mais recente é de {ultima}{atraso}. "
              "A varredura das 02:00 não publicou hoje: ela pode ter falhado no "
              "meio, estourado o tempo, ou terminado sem chegar ao PASSO 7.")
        return

    if datas[0] != dia:
        falha(f"a rodada de {dia} existe, mas está na posição {datas.index(dia)} "
              f"em vez da 0 (a posição 0 é de {datas[0]}). A página mostra sempre "
              "a primeira, então o painel está exibindo outro dia.")

    r = next(x for x in rodadas if x.get("data") == dia)
    c = r.get("cobertura") or {}
    p = c.get("pncp") or {}

    brutos, esperados = p.get("brutos") or 0, p.get("esperados") or 0
    if brutos < MINIMO_BRUTOS:
        falha(f"a rodada de {dia} registra apenas {brutos} contratações colhidas. "
              "Isso não é dia magro, é varredura que não aconteceu.")
    elif esperados and brutos < esperados * 0.99:
        falha(f"a rodada de {dia} colheu {brutos:,} de {esperados:,} contratações "
              f"({esperados - brutos} não vistas). A varredura ficou incompleta.")

    if not c.get("concluido_em"):
        falha(f"a rodada de {dia} não tem 'concluido_em'. Ela foi registrada "
              "antes de terminar — provavelmente publicada no meio do caminho.")

    if (c.get("triados") or 0) < (p.get("candidatos") or 0):
        falha(f"a rodada de {dia} triou {c.get('triados') or 0} de "
              f"{p.get('candidatos') or 0} candidatos. Um candidato não lido "
              "pode ser o contrato do ano.")

    # O carimbo do cabeçalho vem de atualizado_em, e é o que a equipe vê. Se ele
    # está velho, a página MENTE mesmo que a rodada esteja na lista.
    at = estado.get("atualizado_em")
    if not at:
        falha("o estado não tem 'atualizado_em'; o cabeçalho da página não sabe "
              "dizer quando o radar rodou pela última vez.")
    else:
        try:
            quando = datetime.fromisoformat(at)
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=TZ)
            horas = (datetime.now(TZ) - quando).total_seconds() / 3600
            if horas > tolerancia_horas:
                falha(f"'atualizado_em' é de {horas:.0f} horas atrás ({at}). "
                      f"O limite é {tolerancia_horas:.0f}h — o radar está velho "
                      "na tela, seja qual for o conteúdo da lista de rodadas.")
        except ValueError:
            falha(f"'atualizado_em' não é uma data ISO válida: {at!r}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("estado", type=Path)
    ap.add_argument("--data", help="dia esperado (padrão: hoje em São Paulo)")
    ap.add_argument("--tolerancia-horas", type=float, default=28.0,
                    help="idade máxima de atualizado_em (padrão 28h: a rodada "
                         "das 02:00 mais uma folga de um dia)")
    a = ap.parse_args()

    dia = a.data or datetime.now(TZ).date().isoformat()
    estado = carrega(a.estado)
    confere(estado, dia, a.tolerancia_horas)

    rodadas = estado.get("rodadas") or []
    if problemas:
        print(f"FALHA: a rodada de {dia} não está no ar como deveria.\n")
        for i, p in enumerate(problemas, 1):
            print(f"  {i}. {p}")
        print("\nO que fazer: refaça a rodada agora, seguindo ROTINAS.md do PASSO 1\n"
              "ao PASSO 7. A varredura leva ~4 minutos e a conferência mais alguns;\n"
              "é mais barato refazer do que deixar a equipe abrir um radar de ontem\n"
              "achando que é de hoje.")
        sys.exit(1)

    r = rodadas[0]
    c = r.get("cobertura") or {}
    p = c.get("pncp") or {}
    print(f"ok  rodada de {dia} publicada · {p.get('brutos', 0):,} contratações "
          f"· {c.get('triados', 0)} triados · {len(estado.get('editais') or [])} "
          f"editais no radar")


if __name__ == "__main__":
    main()
