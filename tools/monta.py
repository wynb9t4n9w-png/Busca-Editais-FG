#!/usr/bin/env python3
"""
Aplica os vereditos, monta a página e passa pelos portões.

A outra metade de rodada.py. O agente entra aqui com um arquivo pequeno — só
{id: {veredito, justificativa}} — e sai com o HTML pronto para publicar, já
aprovado por valida_rodada.py e teste_pagina.py. Ele não escreve JSON de estado
em momento nenhum, e é esse o ponto: em 05/09/2026 a rodada morreu sem deixar
rastro, e a parte mais provável de tê-la matado era justamente a reescrita
manual de um bloco de dados de 109 KB.

O molde vem do próprio artifact lido no PASSO 1: a página é a fonte da verdade,
e trocar só o miolo entre /*DADOS*/ e /*FIM*/ garante que nenhuma correção de
layout feita ontem se perca hoje.

    python3 tools/monta.py --trabalho trabalho \\
        --vereditos vereditos.json --saida busca-editais-fg.html

    # opcional, quando a camada 2 rendeu alguma coisa:
    python3 tools/monta.py ... --externas externas.json

Formato de vereditos.json:
    {"pncp:123-1-000004-2026": {"veredito": "quente",
                                "justificativa": "uma ou duas frases"}}

Formato de externas.json (o que o PASSO 3 apurou):
    {"tentadas": 15, "abertas": 7, "candidatos": 0,
     "falhas": ["Senac: HTTP 403"], "fontes": {...}}
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=-3))
RAIZ = Path(__file__).resolve().parent.parent
DADOS_RE = re.compile(r"(/\*DADOS\*/)(.*?)(/\*FIM\*/)", re.S)

VEREDITOS = ("quente", "morno", "frio")
SCORE_MINIMO_FRIO = 30
MAX_RODADAS = 30

# Um quente precisa poder ser disputado. O validador também confere, mas falhar
# aqui custa um comando; falhar lá custa a montagem inteira.
DISPUTAVEL = {"aberto", "indeterminado", "relicita"}


def serializa(estado: dict) -> str:
    # "</script" dentro de uma string JSON fecha a tag no navegador e o resto da
    # página vira texto solto. Escapar a barra resolve, e o JSON continua válido.
    return json.dumps(estado, ensure_ascii=False, indent=1).replace("</script", "<\\/script")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trabalho", type=Path, default=Path("trabalho"))
    ap.add_argument("--vereditos", type=Path, required=True)
    ap.add_argument("--externas", type=Path)
    ap.add_argument("--molde", type=Path,
                    help="HTML de onde vem o layout (padrão: o estado lido pela rodada)")
    ap.add_argument("--saida", type=Path, default=Path("busca-editais-fg.html"))
    a = ap.parse_args()

    base = json.loads((a.trabalho / "base.json").read_text(encoding="utf8"))
    vereditos = json.loads(a.vereditos.read_text(encoding="utf8"))
    rodada = base.pop("_rodada")
    # Sai sempre do estado: é caminho de arquivo desta máquina, não tem o que
    # fazer numa página publicada.
    molde_guardado = base.pop("_molde", None)
    dia = rodada["data"]

    # ── aplica os vereditos ──
    faltando, invalidos = [], []
    for e in base["editais"]:
        v = vereditos.get(e["id"])
        if v:
            if v.get("veredito") not in VEREDITOS:
                invalidos.append(f"{e['id']}: veredito {v.get('veredito')!r}")
                continue
            e["veredito"] = v["veredito"]
            if v.get("justificativa"):
                e["justificativa"] = v["justificativa"]
        if not e.get("veredito"):
            faltando.append(f"{e['id']}  {(e.get('orgao') or '')[:44]}")

    if invalidos:
        raise SystemExit("FALHA: veredito inválido —\n  " + "\n  ".join(invalidos) +
                         f"\nEsperado um de {list(VEREDITOS)}.")
    if faltando:
        raise SystemExit(
            f"FALHA: {len(faltando)} edital(is) sem veredito. Um candidato não "
            "lido pode ser o contrato do ano —\n  " + "\n  ".join(faltando[:20]))

    # ── quente precisa ser disputável ──
    presos = [f"{e['id']} ({e.get('disputa')})" for e in base["editais"]
              if e.get("veredito") == "quente" and e.get("disputa") not in DISPUTAVEL]
    if presos:
        raise SystemExit(
            "FALHA: veredito 'quente' em edital que não dá para disputar —\n  " +
            "\n  ".join(presos) +
            "\nQuente significa que a Thutor ainda pode entrar. Rebaixe para morno "
            "e diga na justificativa que serve como referência de mercado.")

    sem_just = [e["id"] for e in base["editais"]
                if e.get("veredito") in ("quente", "morno") and not (e.get("justificativa") or "").strip()]
    if sem_just:
        raise SystemExit("FALHA: quente/morno sem justificativa —\n  " +
                         "\n  ".join(sem_just) +
                         "\nQuem abre o radar decide fazer proposta lendo essa frase.")

    # ── frio raso não entra: conta e some ──
    antes = len(base["editais"])
    base["editais"] = [e for e in base["editais"]
                       if not (e.get("veredito") == "frio"
                               and (e.get("score") or 0) < SCORE_MINIMO_FRIO)]
    descartados = antes - len(base["editais"])

    # ── a rodada ──
    rodada["cobertura"]["triados"] = len(vereditos)
    rodada["cobertura"]["descartados"] = descartados
    if a.externas:
        x = json.loads(a.externas.read_text(encoding="utf8"))
        base["fontes"] = {**(base.get("fontes") or {}), **(x.pop("fontes", {}) or {})}
        rodada["cobertura"]["externas"].update(x)
    rodada["cobertura"]["concluido_em"] = datetime.now(TZ).isoformat(timespec="seconds")

    rodadas = [r for r in (base.get("rodadas") or []) if r.get("data") != dia]
    base["rodadas"] = [rodada] + rodadas[:MAX_RODADAS - 1]
    base["atualizado_em"] = rodada["cobertura"]["concluido_em"]

    # ── molde: só o miolo muda ──
    molde = a.molde or molde_guardado
    if not molde or not Path(molde).exists():
        molde = a.saida if a.saida.exists() else None
    if not molde:
        raise SystemExit("FALHA: não sei de onde tirar o layout. Passe --molde "
                         "com o HTML do artifact lido no PASSO 1.")
    html = Path(molde).read_text(encoding="utf8")
    m = DADOS_RE.search(html)
    if not m:
        raise SystemExit(f"FALHA: {molde} não tem o bloco /*DADOS*/…/*FIM*/.")
    a.saida.write_text(html[:m.start(2)] + serializa(base) + html[m.end(2):],
                       encoding="utf8")

    # ── os portões ──
    for script in ("valida_rodada.py", "teste_pagina.py"):
        r = subprocess.run([sys.executable, f"tools/{script}", str(a.saida)],
                           cwd=RAIZ, capture_output=True, text=True)
        print(r.stdout[-2500:] if r.returncode else
              r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")
        if r.returncode:
            print(r.stderr[-1500:], file=sys.stderr)
            raise SystemExit(f"FALHA: {script} reprovou. NÃO publique — corrija "
                             "e rode monta.py de novo.")

    quentes = sum(1 for e in base["editais"] if e.get("veredito") == "quente")
    mornos = sum(1 for e in base["editais"] if e.get("veredito") == "morno")
    print(f"\nok  {a.saida} pronta para publicar")
    print(f"    rodada {dia} · {quentes} quentes · {mornos} mornos · "
          f"{len(base['editais'])} no radar")


if __name__ == "__main__":
    main()
