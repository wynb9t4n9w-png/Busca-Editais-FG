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
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import situacao                                    # noqa: E402
import camada2                                     # noqa: E402
from coleta_pncp import coleta, coleta_abertas     # noqa: E402

TZ = timezone(timedelta(hours=-3))
RAIZ = Path(__file__).resolve().parent.parent

# Tetos do estado. Existem para a página não virar um arquivo morto de 5 MB que
# o navegador leva dez segundos para desenhar.
MAX_EDITAIS = 400
MAX_RODADAS = 30

# A memória do aprendizado, e por que ela precisa existir.
#
# Quando o radar passou a guardar só o que ainda dá para disputar, o edital
# some no dia em que o certame fecha. Isso é certo para a TELA e errado para o
# MECANISMO: tools/aprende.py descobre vocabulário e órgãos recorrentes
# comparando o que interessou com o que não interessou, e sem histórico ele
# compara três dias contra três dias para sempre. Um órgão que comprou em
# agosto e volta em novembro nunca seria reconhecido, que é exatamente a
# prospecção mais valiosa que este projeto pode produzir.
#
# A memória NÃO é o arquivo que foi removido: ela não aparece na página, não
# tem veredito exibido, não conta como oportunidade e não pode ser confundida
# com uma. É o caderno do filtro, e só o aprendizado a lê.
MAX_MEMORIA = 3000
CAMPOS_MEMORIA = ("id", "orgao", "cnpj", "uf", "municipio", "modalidade",
                  "objeto", "valor", "publicado_em", "encerramento",
                  "veredito", "score", "frentes", "vencedor")
SCORE_MINIMO_FRIO = 30      # frio abaixo disto não entra: conta e some

# O radar guarda só o que ainda dá para pescar. Decidido, encerrado e cancelado
# saem; o prazo vencido também. A ferramenta existe para converter oportunidade
# em vitória no certame, e um arquivo de disputas terminadas não ajuda nisso —
# ocupa a tela e faz o dia parecer cheio quando está vazio.
DISPUTAVEL = ("aberto", "indeterminado", "relicita")

# Formato do checkpoint. Suba quando a forma do que as fases gravam mudar: um
# checkpoint do formato velho retomado por código novo estoura num KeyError no
# meio da rodada, que é o pior lugar para descobrir isso. Subiu para 2 quando a
# coleta deixou de devolver "mercado" e passou a devolver
# "inexigiveis_descartados".
VERSAO_CHECKPOINT = 3


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
        # Checkpoint de ontem não serve para a rodada de hoje; de outro formato,
        # tampouco — e esse é o que quebra em silêncio.
        if d.get("_dia") != self.dia or d.get("_versao") != VERSAO_CHECKPOINT:
            return None
        print(f"    (retomado do checkpoint: {p.name})", flush=True)
        return d.get("_dado")

    def guarda(self, fase: str, dado):
        self._p(fase).write_text(
            json.dumps({"_dia": self.dia, "_versao": VERSAO_CHECKPOINT,
                        "_dado": dado}, ensure_ascii=False, indent=1),
            encoding="utf8")
        return dado


# ───────────────────────── fases ─────────────────────────

def fase_suite(t: Trabalho, pular: bool) -> None:
    print("[1/6] suíte", flush=True)
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
    print("[2/6] coleta por publicação", flush=True)
    g = t.guardado("coleta")
    if g:
        return g
    ontem = (datetime.now(TZ) - timedelta(days=1)).strftime("%Y%m%d")
    hoje = datetime.now(TZ).strftime("%Y%m%d")
    r = coleta(ontem, hoje, 0)
    c = r["cobertura"]
    print(f"    {c['brutos']:,} de {c['esperados']:,} contratações · "
          f"{c['candidatos']} candidatos · "
          f"{c['inexigiveis_descartados']} inexigibilidade(s) fora", flush=True)
    if c["paginas_perdidas"] or c["brutos"] < c["esperados"]:
        raise SystemExit(
            f"FALHA: varredura incompleta ({c['paginas_perdidas']} página(s) "
            f"perdida(s), {c['esperados'] - c['brutos']} contratação(ões) não "
            "vistas). Rode de novo — o PNCP devolve 503 em rajada e costuma "
            "passar no minuto seguinte.")
    return t.guarda("coleta", r)


def fase_abertas(t: Trabalho) -> dict:
    """
    A outra metade do açude: tudo com prazo de proposta aberto, publicado quando
    for. Fase própria porque são ~27 mil registros e uns 10 minutos, e um
    tropeço aqui não pode custar a coleta por publicação que já deu certo.
    """
    print("[3/6] varredura por prazo aberto", flush=True)
    g = t.guardado("abertas")
    if g:
        return g
    r = coleta_abertas(0)
    c = r["cobertura"]
    print(f"    {c['brutos']:,} com proposta aberta até {c['ate']} · "
          f"{c['candidatos']} candidatos · "
          f"{c['inexigiveis_descartados']} inexigibilidade(s) fora", flush=True)
    # Sem portão de completude aqui, de propósito: um edital que escapou hoje
    # continua aberto e volta amanhã. O portão duro é o da varredura por
    # publicação, onde a página perdida some para sempre.
    if c["erros"]:
        print(f"    {len(c['erros'])} aviso(s): {c['erros'][:2]}", flush=True)
    return t.guarda("abertas", r)


def fase_camada2(t: Trabalho) -> dict:
    """
    O que não está no PNCP. Era um plano em prosa para o agente visitar quinze
    portais com WebFetch, e rendeu zero em três rodadas — metade das fontes
    devolvendo 403. O 403 era bloqueio de User-Agent, não política de robô, e
    com o cabeçalho de navegador o Canal do Fornecedor do Sebrae devolve JSON
    com as licitações de todo o Sistema. Virou coleta, como a do PNCP.
    """
    print("[4/6] camada 2 (fora do PNCP)", flush=True)
    g = t.guardado("camada2")
    if g:
        return g
    try:
        r = camada2.colhe()
    except Exception as e:                       # rede lá fora não derruba a rodada
        print(f"    aviso: camada 2 falhou inteira ({e}). O PNCP segue.", flush=True)
        return t.guarda("camada2", {"cobertura": {"tentadas": 0, "abertas": 0,
                                                  "candidatos": 0, "brutos": 0,
                                                  "falhas": [str(e)[:160]],
                                                  "sem_candidato": []},
                                    "candidatos": []})
    c = r["cobertura"]
    print(f"    {c['abertas']}/{c['tentadas']} fonte(s) · {c['brutos']} abertas · "
          f"{c['candidatos']} candidato(s)", flush=True)
    for f in c["falhas"]:
        print(f"    falhou: {f}", flush=True)
    return t.guarda("camada2", r)


def fase_situacao(t: Trabalho, alvos: list[dict]) -> dict:
    """A pergunta autoritativa, e a única que custa rede por edital."""
    # O checkpoint vale por edital, não em bloco. Retomar em bloco parecia
    # certo até o filtro mudar no meio do dia: a coleta trouxe um candidato novo,
    # o cache da conferência era do conjunto antigo, e o edital entrou no radar
    # SEM situacao_item — pego pelo validador, mas só depois de montar a página.
    # Conferir o que falta é tão barato quanto e não tem esse buraco.
    achados: dict[str, dict] = dict(t.guardado("situacao") or {})
    faltam = [e for e in alvos if e["id"] not in achados]
    print(f"[5/6] conferindo {len(faltam)} de {len(alvos)} editais no PNCP "
          f"({len(alvos) - len(faltam)} já conferidos)", flush=True)
    if not faltam:
        return achados
    alvos = faltam
    for i, e in enumerate(alvos, 1):
        r = situacao.confere_edital(e)
        achados[e["id"]] = {k: r[k] for k in
                            ("disputa", "situacao", "vencedor", "documento_fecho")
                            if k in r}
        if i % 10 == 0 or i == len(alvos):
            print(f"    editais {i}/{len(alvos)}", flush=True)
        time.sleep(situacao.PAUSA_ENTRE)
    return t.guarda("situacao", achados)


# ───────────────────────── fusão ─────────────────────────

# Duas publicações da mesma disputa não têm o mesmo texto.
#
# Primeira tentativa: comparar as primeiras palavras do objeto. Falhou na tela,
# e a tela mostrou por quê — o SAAE de Lagoa da Prata aparecia duas vezes na
# faixa de urgência, porque uma publicação começa em "CONTRATAÇÃO DE EMPRESA
# ESPECIALIZADA NA PRESTAÇÃO DE..." e a outra em "Prestação de Serviços
# Técnicos...". Mesmo edital, aberturas diferentes.
#
# O que separa de verdade, medido sobre o radar de 06/09/2026:
#
#   SAAE Lagoa da Prata   mesmo valor, cobertura de palavras 0,91  -> é o mesmo
#   Caçu                  mesmo valor, cobertura 1,00              -> é o mesmo
#   Campo Belo            cobertura 1,00, valores 0 e 25.400       -> DOIS lotes
#   Comando da Marinha    cobertura 0,88, R$ 588 mil e R$ 4,17 mi  -> DOIS cursos
#
# O valor é o que impede a fusão errada, e errar aqui é caro na direção que
# importa: unir duas disputas distintas esconde uma oportunidade, e oportunidade
# escondida não reclama. Por isso a exigência é dupla — mesmo valor E cobertura
# alta — e não uma ou outra.
COBERTURA_MESMA_DISPUTA = 0.85


def _palavras(s: str) -> set:
    s = unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z]{4,}", s))


def _mesma_disputa(a: dict, b: dict) -> bool:
    if a.get("cnpj") != b.get("cnpj"):
        return False
    if round(a.get("valor") or 0, 2) != round(b.get("valor") or 0, 2):
        return False
    pa, pb = _palavras(a.get("objeto")), _palavras(b.get("objeto"))
    if not pa or not pb:
        return False
    # Cobertura do MENOR, não Jaccard: uma publicação traz o objeto completo
    # (2.859 caracteres) e a outra o resumo (383). O Jaccard desse par é 0,17 e
    # esconderia a igualdade; a cobertura do menor é 0,91 e a revela.
    return len(pa & pb) / min(len(pa), len(pb)) >= COBERTURA_MESMA_DISPUTA


def _melhor(a: dict, b: dict) -> dict:
    """
    Entre duas publicações da mesma disputa, fica a mais informativa.

    "Mais informativa" é a de objeto mais longo, e isso não é estética: o mesmo
    edital do SAAE de Lagoa da Prata pontuava 52 com o objeto curto e 78 com o
    completo, porque metade dos termos de núcleo só existe no texto inteiro.
    Triar pelo resumo é decidir sem ler.
    """
    ma, mb = len(a.get("objeto") or ""), len(b.get("objeto") or "")
    vencedor, perdedor = (a, b) if ma >= mb else (b, a)
    # O veredito e a nota do agente sobrevivem, venham de qual publicação vier.
    for campo in ("veredito", "justificativa", "visto_em"):
        if not vencedor.get(campo) and perdedor.get(campo):
            vencedor[campo] = perdedor[campo]
    outros = vencedor.setdefault("tambem_publicado_como", [])
    for x in [perdedor.get("link")] + (perdedor.get("tambem_publicado_como") or []):
        if x and x != vencedor.get("link") and x not in outros:
            outros.append(x)
    return vencedor


def dedup(editais: list[dict]) -> tuple[list[dict], int]:
    from collections import defaultdict
    baldes: dict[tuple, list[dict]] = defaultdict(list)
    for e in editais:
        baldes[(e.get("cnpj"), round(e.get("valor") or 0, 2))].append(e)

    saida, unidas = [], 0
    for grupo in baldes.values():
        restantes: list[dict] = []
        for e in grupo:
            for j, ja in enumerate(restantes):
                if _mesma_disputa(ja, e):
                    restantes[j] = _melhor(ja, e)
                    unidas += 1
                    break
            else:
                restantes.append(e)
        saida.extend(restantes)
    return saida, unidas


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

    # O fato, por cima do palpite.
    for eid, a in achados.items():
        alvo = editais.get(eid)
        if not alvo:
            continue
        for k in ("disputa", "vencedor", "documento_fecho"):
            if a.get(k):
                alvo[k] = a[k]
        if a.get("situacao"):
            alvo["situacao_item"] = a["situacao"]

    # ── só fica o que ainda dá para disputar ──
    # Este corte vem DEPOIS de o situacao.py falar, e essa ordem não é detalhe:
    # o `disputa` que a coleta deduz é palpite, e em 03/09/2026 ele escondeu dois
    # editais ainda disputáveis como se já tivessem dono. Cortar por palpite
    # perderia oportunidade real — o erro que este projeto mais teme, porque some
    # sem reclamar. Aqui já é o fato lido item a item na fonte.
    def pescavel(e) -> bool:
        if e.get("disputa") not in DISPUTAVEL:
            return False
        d = dias_desde(e.get("encerramento"))
        return d is None or d <= 0          # sem prazo declarado, ou ainda por vir

    lista, duplicatas = dedup(list(editais.values()))

    # Antes de qualquer corte, o que passou por aqui vai para a memória. É o
    # último ponto em que os editais que fecharam hoje ainda existem.
    memoria = {m["id"]: m for m in (estado.get("memoria") or [])}
    for e in lista:
        memoria[e["id"]] = {k: e[k] for k in CAMPOS_MEMORIA if k in e}

    antes = len(lista)
    lista = [e for e in lista if pescavel(e)]
    fechados = antes - len(lista)

    # O teto virou quase teórico depois do corte acima, mas continua: um dia com
    # centenas de disputáveis não pode transformar a página num arquivo de 5 MB.
    lista.sort(key=lambda e: str(e.get("publicado_em") or ""), reverse=True)
    lista = lista[:MAX_EDITAIS]

    novo = dict(estado)
    novo["editais"] = lista
    novo["memoria"] = sorted(memoria.values(),
                             key=lambda m: str(m.get("publicado_em") or ""),
                             reverse=True)[:MAX_MEMORIA]
    # Estado de antes da decisão de 06/09/2026 ainda carrega "mercado". Some
    # aqui, uma vez, sem exigir purga manual de ninguém.
    novo.pop("mercado", None)
    novo["atualizado_em"] = datetime.now(TZ).isoformat(timespec="seconds")
    return novo, novos, fechados, duplicatas


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
    ab = fase_abertas(t)

    # As duas varreduras se sobrepõem bastante; o `id` decide, e a de publicação
    # tem precedência porque é a que carrega a conta de cobertura.
    ja = {c["id"] for c in r["candidatos"]}
    novos_abertos = [c for c in ab["candidatos"] if c["id"] not in ja]
    r["candidatos"] = r["candidatos"] + novos_abertos
    print(f"    {len(novos_abertos)} candidato(s) que só a varredura por prazo "
          f"aberto enxergou", flush=True)

    c2 = fase_camada2(t)
    ja = {c["id"] for c in r["candidatos"]}
    r["candidatos"] += [c for c in c2["candidatos"] if c["id"] not in ja]

    # Quem precisa de conferência: os candidatos de hoje, mais os editais do
    # radar que ainda estavam disputáveis — porque "aberto" de ontem pode ser
    # "homologado" de hoje, e é justamente esse o edital que engana.
    ids_hoje = {c["id"] for c in r["candidatos"]}
    antigos = [e for e in (estado.get("editais") or [])
               if e["id"] not in ids_hoje
               and e.get("disputa") in ("aberto", "indeterminado", "relicita")]
    alvos = r["candidatos"] + antigos
    # Só o que tem id do PNCP vai para a conferência na fonte: um edital do
    # Sebrae não existe lá, e pedir por ele devolveria "desconhecida" — o que
    # depois reprovaria a rodada por cobertura de conferência.
    alvos = [e for e in alvos if str(e.get("id", "")).startswith("pncp:")]
    achados = fase_situacao(t, alvos)

    print("[6/6] fundindo com o estado anterior", flush=True)
    base, novos, fechados, duplicatas = funde(estado, r, achados, dia)

    c = r["cobertura"]
    base["_rodada"] = {
        "data": dia,
        "cobertura": {
            # O início é o da COLETA, não o desta invocação. Numa rodada retomada
            # do checkpoint o relógio de parede marca segundos, e o validador
            # reprova por "duração curta demais" um trabalho que de fato levou os
            # quatro minutos — só que na tentativa anterior. O carimbo da coleta
            # atravessa o checkpoint junto com os dados e conta a verdade.
            "iniciado_em": c.get("iniciado_em") or inicio.isoformat(timespec="seconds"),
            "concluido_em": datetime.now(TZ).isoformat(timespec="seconds"),
            "rede_direta": True,
            "pncp": {k: c[k] for k in ("brutos", "esperados", "paginas",
                                       "paginas_perdidas", "candidatos",
                                       "modalidades_falhas", "erros")},
            "externas": {k: c2["cobertura"].get(k) for k in
                         ("tentadas", "abertas", "candidatos", "falhas",
                          "sem_candidato")},
            # Quantos editais do radar têm situação conferida na fonte — não
            # quantos ESTA rodada conferiu. Um edital já decidido não precisa de
            # reconferência, e continua conferido: a prova é o `situacao_item`
            # que ele carrega. Contar só o desta rodada reprovava a rodada por um
            # trabalho que já tinha sido feito.
            "abertas": {k: ab["cobertura"][k] for k in
                        ("brutos", "candidatos", "dias", "inexigiveis_descartados")},
            "triados": 0,
            "conferidos": sum(1 for e in base["editais"]
                              if (e.get("situacao_item") or "").strip()),
            "novos": len(novos), "descartados": 0,
            "inexigiveis_descartados": c["inexigiveis_descartados"],
            "fechados_removidos": fechados,
            "duplicatas_unidas": duplicatas,
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

    print(f"\nok  {len(base['editais'])} editais disputáveis no radar")
    print(f"    {c['inexigiveis_descartados']} inexigibilidade(s) descartada(s) · "
          f"{fechados} disputa(s) encerrada(s) removida(s) · "
          f"{duplicatas} duplicata(s) unida(s)")
    print(f"    {len(folha)} para triar → {a.trabalho}/triagem.json")
    print(f"    estado fundido → {a.trabalho}/base.json")
    print(f"\nAgora: leia triagem.json, decida veredito e justificativa de cada um,\n"
          f"grave {{id: {{veredito, justificativa}}}} e rode\n"
          f"    python3 tools/monta.py --trabalho {a.trabalho} "
          f"--vereditos <arquivo> --saida busca-editais-fg.html")


if __name__ == "__main__":
    main()
