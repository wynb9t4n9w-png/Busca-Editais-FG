#!/usr/bin/env python3
"""
Varre o PNCP e devolve os candidatos do dia.

O Portal Nacional de Contratações Públicas concentra, por força da Lei
14.133/2021, tudo que a administração direta contrata — União, estados,
municípios, tribunais, universidades, autarquias. São cerca de 5.800
contratações por dia útil, e a API pública devolve todas, com o objeto, o
valor estimado e o prazo de proposta.

Por que não usar o buscador do próprio PNCP: ele foi testado em 03/09/2026 com
o termo "educação corporativa" e devolveu, entre os primeiros resultados,
"aquisição de materiais de higiene e limpeza". A busca textual dele é rasa
demais para servir de filtro. Baixar tudo e filtrar aqui custa uns três
minutos e não erra.

Uso:
    python3 tools/coleta_pncp.py                      # ontem e hoje
    python3 tools/coleta_pncp.py 20260901 20260903
    python3 tools/coleta_pncp.py --saida cand.json --min-score 20

Saída: JSON com {"cobertura": {...}, "candidatos": [...]}. A cobertura é a
prova de que a varredura aconteceu — é ela que o validador confere.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from perfil import avalia, LIMIAR_CANDIDATO  # noqa: E402

TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
TAM_PAGINA = 50

# Todas as modalidades em que um serviço de consultoria pode aparecer. Leilão
# (1 e 13) é venda de bem público: fica de fora e não é omissão.
MODALIDADES = {
    2: "Diálogo Competitivo", 3: "Concurso", 4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial", 6: "Pregão - Eletrônico",
    7: "Pregão - Presencial", 8: "Dispensa", 9: "Inexigibilidade",
    10: "Manifestação de Interesse", 11: "Pré-qualificação", 12: "Credenciamento",
}

TENTATIVAS = 4
PAUSA_BASE = 2.0
# Espera antes da repescagem: o 503 do PNCP costuma ser pico de carga, e
# insistir na hora só repete o erro.
PAUSA_REPESCA = 20.0
TETO_PAGINAS = 400  # trava de segurança; nenhuma modalidade chegou perto disso


def busca(modalidade: int, d1: str, d2: str, pagina: int) -> dict:
    """Uma página da API, com repetição em espera crescente."""
    url = (f"{BASE}?dataInicial={d1}&dataFinal={d2}"
           f"&codigoModalidadeContratacao={modalidade}"
           f"&pagina={pagina}&tamanhoPagina={TAM_PAGINA}")
    ultimo = ""
    for t in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                corpo = r.read()
                # 200 com corpo vazio acontece nas modalidades raras: é "nada
                # nesse período", não uma resposta corrompida.
                if not corpo.strip():
                    return {"data": [], "totalPaginas": 0, "totalRegistros": 0}
                return json.loads(corpo)
        except urllib.error.HTTPError as e:
            # 204 = sem conteúdo para essa modalidade no período. Não é erro.
            if e.code == 204:
                return {"data": [], "totalPaginas": 0, "totalRegistros": 0}
            ultimo = f"HTTP {e.code}"
        except Exception as e:  # rede, timeout, JSON quebrado
            ultimo = str(e)[:120]
        if t < TENTATIVAS - 1:
            time.sleep(PAUSA_BASE * (2 ** t))
    return {"data": [], "totalPaginas": 0, "totalRegistros": 0, "_erro": ultimo}


def colhe_modalidade(modalidade: int, d1: str, d2: str) -> dict:
    """Todas as páginas de uma modalidade. Devolve os registros brutos."""
    primeira = busca(modalidade, d1, d2, 1)
    if primeira.get("_erro"):
        return {"modalidade": modalidade, "erro": primeira["_erro"],
                "brutos": [], "paginas": 0, "total": 0}

    total = primeira.get("totalRegistros") or 0
    paginas = min(primeira.get("totalPaginas") or 0, TETO_PAGINAS)
    brutos = list(primeira.get("data") or [])
    erros = []

    perdidas: list[int] = []
    for p in range(2, paginas + 1):
        d = busca(modalidade, d1, d2, p)
        if d.get("_erro"):
            perdidas.append(p)
            continue
        brutos.extend(d.get("data") or [])

    # Repescagem. O PNCP devolve 503/504 esporádicos sob carga, e uma página de
    # 50 contratações que se perde em silêncio é uma oportunidade que nunca
    # existiu para quem lê o radar. Vale esperar e insistir.
    if perdidas:
        time.sleep(PAUSA_REPESCA)
        ainda: list[int] = []
        for p in perdidas:
            d = busca(modalidade, d1, d2, p)
            if d.get("_erro"):
                ainda.append(p)
                erros.append(f"p{p}: {d['_erro']}")
            else:
                brutos.extend(d.get("data") or [])
        perdidas = ainda

    return {"modalidade": modalidade, "brutos": brutos, "paginas": paginas,
            "total": total, "erros": erros, "perdidas": perdidas}


def identifica(reg: dict) -> str:
    """Chave estável de um edital, para não republicar o mesmo duas vezes."""
    ctrl = reg.get("numeroControlePNCP")
    if ctrl:
        return "pncp:" + ctrl.replace("/", "-")
    org = (reg.get("orgaoEntidade") or {}).get("cnpj", "?")
    return f"pncp:{org}-{reg.get('anoCompra')}-{reg.get('sequencialCompra')}"


def link(reg: dict) -> str:
    """A página do edital no PNCP. O formato /app/editais/CNPJ/ANO/SEQ é estável."""
    org = (reg.get("orgaoEntidade") or {}).get("cnpj")
    ano, seq = reg.get("anoCompra"), reg.get("sequencialCompra")
    if org and ano and seq:
        return f"https://pncp.gov.br/app/editais/{org}/{ano}/{seq}"
    return reg.get("linkSistemaOrigem") or "https://pncp.gov.br/app/editais"


def converte(reg: dict, aval: dict) -> dict:
    """Do registro cru do PNCP para o formato do radar."""
    org = reg.get("orgaoEntidade") or {}
    uni = reg.get("unidadeOrgao") or {}
    return {
        "id": identifica(reg),
        "fonte": "PNCP",
        "orgao": (org.get("razaoSocial") or "").strip(),
        "cnpj": org.get("cnpj"),
        "unidade": (uni.get("nomeUnidade") or "").strip(),
        "uf": uni.get("ufSigla"),
        "municipio": uni.get("municipioNome"),
        "esfera": org.get("esferaId"),
        "poder": org.get("poderId"),
        "modalidade": reg.get("modalidadeNome"),
        "objeto": " ".join((reg.get("objetoCompra") or "").split()),
        "complemento": " ".join((reg.get("informacaoComplementar") or "").split())[:600],
        "valor": reg.get("valorTotalEstimado") or 0,
        "sigiloso": aval["sigiloso"],
        "srp": bool(reg.get("srp")),
        "publicado_em": (reg.get("dataPublicacaoPncp") or "")[:10],
        "abertura": reg.get("dataAberturaProposta"),
        "encerramento": reg.get("dataEncerramentoProposta"),
        "situacao": reg.get("situacaoCompraNome"),
        "numero": reg.get("numeroCompra"),
        "processo": reg.get("processo"),
        "link": link(reg),
        "score": aval["score"],
        "frentes": aval["frentes"],
        "achados": aval["achados"],
    }


def coleta(d1: str, d2: str, min_score: int, trabalhadores: int = 4) -> dict:
    inicio = datetime.now(TZ)
    resultados = []
    with ThreadPoolExecutor(max_workers=trabalhadores) as pool:
        for r in pool.map(lambda m: colhe_modalidade(m, d1, d2), MODALIDADES):
            resultados.append(r)

    brutos = 0
    paginas = 0
    paginas_perdidas = 0
    esperados = 0
    modalidades_falhas: list[str] = []
    erros: list[str] = []
    por_modalidade: dict[str, int] = {}
    candidatos: list[dict] = []
    vistos: set[str] = set()

    for r in resultados:
        nome = MODALIDADES[r["modalidade"]]
        if r.get("erro"):
            erros.append(f"{nome}: {r['erro']}")
            modalidades_falhas.append(nome)
            continue
        erros.extend(f"{nome}/{e}" for e in r.get("erros", []))
        paginas_perdidas += len(r.get("perdidas") or [])
        esperados += r.get("total") or 0
        brutos += len(r["brutos"])
        paginas += r["paginas"]
        por_modalidade[nome] = len(r["brutos"])

        for reg in r["brutos"]:
            aval = avalia(reg.get("objetoCompra"), reg.get("valorTotalEstimado"),
                          reg.get("modalidadeNome"), reg.get("informacaoComplementar"))
            if aval["score"] < max(min_score, LIMIAR_CANDIDATO):
                continue
            cand = converte(reg, aval)
            if cand["id"] in vistos:      # a mesma compra pode voltar em duas páginas
                continue
            vistos.add(cand["id"])
            candidatos.append(cand)

    candidatos.sort(key=lambda c: (-c["score"], -(c["valor"] or 0)))
    fim = datetime.now(TZ)

    return {
        "cobertura": {
            "fonte": "PNCP",
            "periodo": [d1, d2],
            "modalidades": len(MODALIDADES),
            "paginas": paginas,
            "paginas_perdidas": paginas_perdidas,
            "brutos": brutos,
            "esperados": esperados,
            "modalidades_falhas": modalidades_falhas,
            "candidatos": len(candidatos),
            "min_score": max(min_score, LIMIAR_CANDIDATO),
            "por_modalidade": por_modalidade,
            "erros": erros,
            "iniciado_em": inicio.isoformat(timespec="seconds"),
            "concluido_em": fim.isoformat(timespec="seconds"),
        },
        "candidatos": candidatos,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("datas", nargs="*", help="AAAAMMDD inicial e final (padrão: ontem e hoje)")
    p.add_argument("--saida", default="candidatos.json")
    p.add_argument("--min-score", type=int, default=LIMIAR_CANDIDATO)
    p.add_argument("--trabalhadores", type=int, default=4)
    a = p.parse_args()

    hoje = datetime.now(TZ).date()
    if len(a.datas) == 2:
        d1, d2 = a.datas
    elif len(a.datas) == 1:
        d1 = d2 = a.datas[0]
    else:
        d1 = (hoje - timedelta(days=1)).strftime("%Y%m%d")
        d2 = hoje.strftime("%Y%m%d")

    r = coleta(d1, d2, a.min_score, a.trabalhadores)
    c = r["cobertura"]

    Path(a.saida).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf8")

    dur = (datetime.fromisoformat(c["concluido_em"]) -
           datetime.fromisoformat(c["iniciado_em"])).total_seconds()
    perda = c["esperados"] - c["brutos"]
    print(f"ok  {d1}–{d2}: {c['brutos']:,} de {c['esperados']:,} contratações "
          f"em {c['paginas']} páginas, {dur:.0f}s")
    if c["paginas_perdidas"] or perda > 0:
        print(f"    ATENÇÃO: {c['paginas_perdidas']} página(s) perdida(s), "
              f"{perda} contratação(ões) não vistas")
    if c["modalidades_falhas"]:
        print(f"    modalidades que falharam inteiras: {c['modalidades_falhas']}")
    print(f"    {c['candidatos']} candidatos (score ≥ {c['min_score']}) → {a.saida}")
    if c["erros"]:
        print(f"    {len(c['erros'])} erro(s) de rede: {c['erros'][:3]}")
    for cand in r["candidatos"][:8]:
        v = f"R$ {cand['valor']:,.0f}" if cand["valor"] else "sigiloso"
        print(f"    {cand['score']:3d} · {v:>16s} · {cand['uf']} · {','.join(cand['frentes'])}")
        print(f"          {cand['objeto'][:120]}")


if __name__ == "__main__":
    main()
