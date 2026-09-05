#!/usr/bin/env python3
"""
A rodada inteira, menos a parte que exige julgamento.

Por que este script existe
──────────────────────────
Em 05/09/2026 a varredura das 02:00 rodou 3 minutos e 45 segundos, terminou com
status de sucesso e não publicou nada. Nenhum script quebrou: a suíte passa, a
coleta traz 5.412 de 5.412 contratações em 222 segundos, situacao.py, aprende.py
e fontes_externas.py rodam limpos contra o estado do dia. O que falhou foi a
FORMA da rodada.

Até aqui a rodada era um procedimento em prosa de dez passos, e o agente
executava tudo numa única passagem: ler o artifact (109 KB), rodar a coleta,
conferir situação, triar, **reescrever o bloco JSON inteiro à mão**, validar e
publicar. Dois defeitos estruturais nisso:

  1. A montagem do estado é a parte mais cara e mais burra do trabalho. São
     centenas de linhas de JSON copiadas de um lado para o outro, e elas crescem
     a cada dia que o radar acumula. É trabalho de máquina sendo feito por quem
     deveria estar julgando editais.

  2. Um tropeço no minuto 3 joga fora os 3 minutos e obriga a recomeçar do zero,
     sem deixar nada no disco para inspecionar depois. Foi por isso que a falha
     de 05/09 não deixou rastro nenhum.

Então a rodada foi partida em duas metades:

    rodada.py   tudo que é determinístico — suíte, coleta, conferência na fonte,
                fusão com o estado anterior. Deixa TUDO em disco, fase por fase,
                e retoma de onde parou.
    (o agente)  só a triagem: ler o objeto e dizer quente, morno ou frio, com
                a justificativa. É a única parte que precisa de juízo.
    monta.py    aplica os vereditos, monta o HTML e passa pelos portões.

O agente deixa de tocar no estado. Um jeito a menos de a rodada morrer no meio,
e o único que ainda existe deixa arquivo no disco.

    python3 tools/rodada.py <estado.html>                 # tudo
    python3 tools/rodada.py <estado.html> --refazer       # ignora o checkpoint
    python3 tools/rodada.py <estado.html> --sem-suite     # a suíte já passou

Saída: <trabalho>/base.json com o estado fundido (sem vereditos) e
<trabalho>/triagem.json com os candidatos que esperam julgamento.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import situacao                                    # noqa: E402
from coleta_pncp import coleta                     # noqa: E402

TZ = timezone(timedelta(hours=-3))
RAIZ = Path(__file__).resolve().parent.parent

# Tetos do estado. Existem para a página não virar um arquivo morto de 5 MB que
# o navegador leva dez segundos para desenhar.
MAX_EDITAIS = 400
MAX_MERCADO = 300
MAX_RODADAS = 30
SCORE_MINIMO_FRIO = 30      # frio abaixo disto não entra: conta e some
DIAS_PARA_APOSENTAR = 90    # frio com prazo vencido há mais que isso sai primeiro


# ───────────────────────── checkpoint ─────────────────────────
# Cada fase grava o que produziu. Uma rodada interrompida no minuto 3 não repaga
# os 222 segundos de coleta: ela relê o arquivo e segue. É a diferença entre um
# tropeço e um recomeço.

class Trabalho:
    def __init__(self, dir_: Path, dia: str, refazer: bool):
        self.dir = dir_
        self.dia = dia
        self.refazer = refazer
        self.dir.mkdir(parents=True, exist_ok=True)

    def _p(self, fase: str) -> Path:
        return self.dir / f"{fase}.json"

    def guardado(self, fase: str):
        p = self._p(fase)
        if self.refazer or not p.exists():
            return None
        try:
            d = json.loads(p.read_text(encoding="utf8"))
        except json.JSONDecodeError:
            return None
        # Checkpoint de ontem não serve para a rodada de hoje.
        if d.get("_dia") != self.dia:
            return None
        print(f"    (retomado do checkpoint: {p.name})", flush=True)
        return d.get("_dado")

    def guarda(self, fase: str, dado):
        self._p(fase).write_text(
            json.dumps({"_dia": self.dia, "_dado": dado}, ensure_ascii=False, indent=1),
            encoding="utf8")
        return dado


# ───────────────────────── fases ─────────────────────────

def fase_suite(t: Trabalho, pular: bool) -> None:
    print("[1/4] suíte", flush=True)
    if pular:
        print("    pulada por --sem-suite", flush=True)
        return
    r = subprocess.run([sys.executable, "tools/testes.py", "--rapido"],
                       cwd=RAIZ, capture_output=True, text=True)
    if r.returncode != 0:
        # Coleta sobre filtro quebrado produz radar vazio que ninguém questiona.
        # Parar aqui é barato; publicar um radar vazio custa um dia inteiro.
        print(r.stdout[-3000:], file=sys.stderr)
        raise SystemExit("FALHA: a suíte reprovou. A rodada não continua.")
    print("    verde", flush=True)


def fase_coleta(t: Trabalho) -> dict:
    print("[2/4] coleta do PNCP", flush=True)
    g = t.guardado("coleta")
    if g:
        return g
    ontem = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y%m%d")
    hoje = datetime.now(TZ).strftime("%Y%m%d")
    r = coleta(ontem, hoje, 0)
    c = r["cobertura"]
    print(f"    {c['brutos']:,} de {c['esperados']:,} contratações · "
          f"{c['candidatos']} candidatos · {c['mercado']} para o Mercado", flush=True)
    if c["paginas_perdidas"] or c["brutos"] < c["esperados"]:
        raise SystemExit(
            f"FALHA: varredura incompleta ({c['paginas_perdidas']} página(s) "
            f"perdida(s), {c['esperados'] - c['brutos']} contratação(ões) não "
            "vistas). Rode de novo — o PNCP devolve 503 em rajada e costuma "
            "passar no minuto seguinte.")
    return t.guarda("coleta", r)


def fase_situacao(t: Trabalho, alvos: list[dict], mercado: list[dict]) -> dict:
    """A pergunta autoritativa, e a única que custa rede por edital."""
    print(f"[3/4] conferindo {len(alvos)} editais e {len(mercado)} do mercado "
          "na fonte", flush=True)
    g = t.guardado("situacao")
    if g:
        return g
    achados: dict[str, dict] = {}
    for i, e in enumerate(alvos, 1):
        r = situacao.confere_edital(e)
        achados[e["id"]] = {k: r[k] for k in
                            ("disputa", "situacao", "vencedor", "documento_fecho")
                            if k in r}
        if i % 10 == 0 or i == len(alvos):
            print(f"    editais {i}/{len(alvos)}", flush=True)
        time.sleep(situacao.PAUSA_ENTRE)
    for i, e in enumerate(mercado, 1):
        achados[e["id"]] = situacao.confere_mercado(e)
        if i % 10 == 0 or i == len(mercado):
            print(f"    mercado {i}/{len(mercado)}", flush=True)
        time.sleep(situacao.PAUSA_ENTRE)
    return t.guarda("situacao", achados)


# ───────────────────────── fusão ─────────────────────────

def dias_desde(iso) -> float | None:
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso)[:10]).date()
    except ValueError:
        return None
    return (datetime.now(TZ).date() - d).days


def funde(estado: dict, r: dict, achados: dict, dia: str) -> tuple[dict, list[dict]]:
    """
    O estado de amanhã a partir do de hoje. Regras do PASSO 5 do ROTINAS, aqui
    em código porque instrução se esquece e código não.
    """
    editais = {e["id"]: e for e in (estado.get("editais") or [])}
    mercado = {m["id"]: m for m in (estado.get("mercado") or [])}

    # Campos que a coleta atualiza num edital que já existe. `veredito` e
    # `justificativa` NÃO estão aqui: são do agente, e sobrevivem à rodada
    # seguinte a menos que ele os mude. `status`, `nota` e `auth` também não —
    # esses vivem no banco do artifact e a rodada não os alcança.
    ATUALIZA = ("valor", "encerramento", "abertura", "situacao", "score",
                "frentes", "objeto", "complemento", "modalidade")

    novos = []
    for c in r["candidatos"]:
        if c["id"] in editais:
            editais[c["id"]].update({k: c[k] for k in ATUALIZA if k in c})
        else:
            c = dict(c)
            c["visto_em"] = dia
            editais[c["id"]] = c
            novos.append(c)

    for m in r["mercado"]:
        if m["id"] not in mercado:
            mercado[m["id"]] = dict(m, visto_em=dia)

    # O fato, por cima do palpite.
    for eid, a in achados.items():
        alvo = editais.get(eid) or mercado.get(eid)
        if not alvo:
            continue
        for k in ("disputa", "vencedor", "documento_fecho"):
            if a.get(k):
                alvo[k] = a[k]
        if a.get("situacao"):
            alvo["situacao_item"] = a["situacao"]

    # Tetos. Aposenta primeiro o frio de prazo vencido há muito tempo; se ainda
    # sobrar, o mais antigo. Nunca corta o que ainda está em disputa.
    lista = list(editais.values())
    if len(lista) > MAX_EDITAIS:
        def descarte(e):
            d = dias_desde(e.get("encerramento"))
            velho = e.get("veredito") == "frio" and d is not None and d > DIAS_PARA_APOSENTAR
            return (0 if velho else 1, e.get("publicado_em") or "")
        lista.sort(key=descarte)
        lista = lista[len(lista) - MAX_EDITAIS:]

    lista.sort(key=lambda e: str(e.get("publicado_em") or ""), reverse=True)
    merc = sorted(mercado.values(), key=lambda m: -(m.get("valor") or 0))[:MAX_MERCADO]

    novo = dict(estado)
    novo["editais"] = lista
    novo["mercado"] = merc
    novo["atualizado_em"] = datetime.now(TZ).isoformat(timespec="seconds")
    return novo, novos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("estado", type=Path, help="HTML do artifact lido no PASSO 1")
    ap.add_argument("--trabalho", type=Path, default=Path("trabalho"),
                    help="onde ficam os checkpoints (padrão: ./trabalho)")
    ap.add_argument("--refazer", action="store_true", help="ignora checkpoints")
    ap.add_argument("--sem-suite", action="store_true")
    a = ap.parse_args()

    dia = datetime.now(TZ).date().isoformat()
    inicio = datetime.now(TZ)
    estado = situacao.carrega(a.estado)
    t = Trabalho(a.trabalho, dia, a.refazer)

    fase_suite(t, a.sem_suite)
    r = fase_coleta(t)

    # Quem precisa de conferência: os candidatos de hoje, mais os editais do
    # radar que ainda estavam disputáveis — porque "aberto" de ontem pode ser
    # "homologado" de hoje, e é justamente esse o edital que engana.
    ids_hoje = {c["id"] for c in r["candidatos"]}
    antigos = [e for e in (estado.get("editais") or [])
               if e["id"] not in ids_hoje
               and e.get("disputa") in ("aberto", "indeterminado", "relicita")]
    alvos = r["candidatos"] + antigos
    merc_novo = [m for m in r["mercado"]
                 if m["id"] not in {x["id"] for x in (estado.get("mercado") or [])}]
    achados = fase_situacao(t, alvos, merc_novo)

    print("[4/4] fundindo com o estado anterior", flush=True)
    base, novos = funde(estado, r, achados, dia)

    c = r["cobertura"]
    base["_rodada"] = {
        "data": dia,
        "cobertura": {
            "iniciado_em": inicio.isoformat(timespec="seconds"),
            "concluido_em": datetime.now(TZ).isoformat(timespec="seconds"),
            "rede_direta": True,
            "pncp": {k: c[k] for k in ("brutos", "esperados", "paginas",
                                       "paginas_perdidas", "candidatos",
                                       "modalidades_falhas", "erros")},
            "externas": {"tentadas": 0, "abertas": 0, "candidatos": 0, "falhas": []},
            "triados": 0, "conferidos": len(achados),
            "novos": len(novos), "descartados": 0,
            "mercado": len(merc_novo),
        },
    }

    # De onde monta.py tira o layout. A página é a fonte da verdade: trocando
    # só o miolo, nenhuma correção de layout feita ontem se perde hoje.
    base["_molde"] = str(a.estado.resolve())
    (a.trabalho / "base.json").write_text(
        json.dumps(base, ensure_ascii=False, indent=1), encoding="utf8")

    # A folha de triagem: só o que precisa de julgamento, e só os campos que
    # ajudam a julgar. Sem isto o agente teria de reler o estado inteiro.
    pendentes = [e for e in base["editais"]
                 if not e.get("veredito") or e["id"] in ids_hoje]
    folha = [{k: e.get(k) for k in
              ("id", "orgao", "uf", "municipio", "modalidade", "objeto",
               "complemento", "valor", "sigiloso", "encerramento", "disputa",
               "situacao_item", "score", "frentes", "link", "veredito")}
             for e in pendentes]
    (a.trabalho / "triagem.json").write_text(
        json.dumps(folha, ensure_ascii=False, indent=1), encoding="utf8")

    print(f"\nok  {len(base['editais'])} editais · {len(base['mercado'])} no mercado")
    print(f"    {len(folha)} para triar → {a.trabalho}/triagem.json")
    print(f"    estado fundido → {a.trabalho}/base.json")
    print(f"\nAgora: leia triagem.json, decida veredito e justificativa de cada um,\n"
          f"grave {{id: {{veredito, justificativa}}}} e rode\n"
          f"    python3 tools/monta.py --trabalho {a.trabalho} "
          f"--vereditos <arquivo> --saida busca-editais-fg.html")


if __name__ == "__main__":
    main()
