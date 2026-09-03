#!/usr/bin/env python3
"""
Quem ganhou o que já foi decidido.

Boa parte do que o radar encontra é contratação direta — Dispensa ou
Inexigibilidade — cujo extrato o PNCP publica DEPOIS do fato. Em 02/09/2026, 27
das 33 contratações aderentes do dia não tinham janela de proposta nenhuma.
Tratá-las como oportunidade foi o erro que este projeto cometeu no primeiro dia:
o radar exibiu como "super oportunidade" um contrato de R$ 1,5 milhão que o
CRECI/SC já havia assinado com a UFSC na véspera.

Mas jogar essas contratações fora seria trocar um erro por outro. Elas dizem
quais órgãos compram o que a Thutor vende, quanto pagam, e quem está ganhando —
que é justamente a informação que uma consultoria não consegue comprar. A
diferença entre lixo e inteligência aqui é só o rótulo.

Este script cruza um edital já decidido com os contratos assinados pelo mesmo
órgão na mesma época, e devolve o fornecedor e o valor.

Uso:
    python3 tools/contratos.py <cnpj> <AAAAMMDD> "trecho do objeto"
    python3 tools/contratos.py --do-estado <estado.html|.json>
"""

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
BASE = "https://pncp.gov.br/api/consulta/v1/contratos"
# O contrato costuma ser assinado dias antes do extrato aparecer, e às vezes
# depois. A janela cobre os dois lados com folga.
DIAS_ANTES, DIAS_DEPOIS = 45, 20
# Fração de palavras do objeto do edital que precisam aparecer no objeto do
# contrato. Os dois textos saem do mesmo processo administrativo e costumam ser
# quase idênticos; 0.6 tolera a reescrita sem casar coisas diferentes.
LIMIAR_SEMELHANCA = 0.6
PAUSA_429 = 12.0

# Palavras que aparecem em todo objeto de licitação e não distinguem nada.
VAZIAS = {
    "contratacao", "contratar", "empresa", "servicos", "servico", "prestacao",
    "especializada", "especializado", "para", "com", "dos", "das", "que",
    "por", "meio", "objeto", "deste", "desta", "conforme", "termo",
    "referencia", "pessoa", "juridica", "fornecimento", "aquisicao", "visando",
    "atender", "necessidades", "municipio", "municipal", "secretaria",
}


def normaliza(t: str | None) -> str:
    s = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def palavras(t: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", normaliza(t)) if w not in VAZIAS}


def semelhanca(objeto_edital: str, objeto_contrato: str) -> float:
    a, b = palavras(objeto_edital), palavras(objeto_contrato)
    return len(a & b) / len(a) if a else 0.0


def busca(cnpj: str, d1: str, d2: str, pagina: int = 1) -> tuple[dict | None, str]:
    url = (f"{BASE}?dataInicial={d1}&dataFinal={d2}&cnpjOrgao={cnpj}"
           f"&pagina={pagina}&tamanhoPagina=50")
    ultimo = ""
    for t in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                corpo = r.read()
            return (json.loads(corpo) if corpo.strip() else {"data": []}), ""
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return {"data": []}, ""
            ultimo = f"HTTP {e.code}"
            if e.code != 429:
                return None, ultimo
            time.sleep(PAUSA_429 * (t + 1))
        except Exception as e:
            ultimo = str(e)[:120]
            time.sleep(2 * (t + 1))
    return None, ultimo


def procura(cnpj: str, publicado_em: str, objeto: str) -> dict:
    """Devolve o contrato mais parecido, ou um resultado vazio explicando por quê."""
    try:
        ref = datetime.fromisoformat(publicado_em[:10]).date()
    except (ValueError, TypeError):
        return {"achou": False, "motivo": f"data de publicação inválida ({publicado_em!r})"}

    d1 = (ref - timedelta(days=DIAS_ANTES)).strftime("%Y%m%d")
    d2 = min(ref + timedelta(days=DIAS_DEPOIS), datetime.now(TZ).date()).strftime("%Y%m%d")

    d, erro = busca(cnpj, d1, d2)
    if d is None:
        return {"achou": False, "motivo": f"a API não respondeu ({erro})"}

    melhor, nota = None, 0.0
    for c in d.get("data") or []:
        s = semelhanca(objeto, c.get("objetoContrato"))
        if s > nota:
            melhor, nota = c, s

    if melhor is None or nota < LIMIAR_SEMELHANCA:
        return {"achou": False, "examinados": len(d.get("data") or []),
                "melhor_nota": round(nota, 2),
                "motivo": "nenhum contrato do órgão no período casa com este objeto"}

    return {
        "achou": True,
        "semelhanca": round(nota, 2),
        "fornecedor": melhor.get("nomeRazaoSocialFornecedor"),
        "cnpj_fornecedor": melhor.get("niFornecedor"),
        "valor": melhor.get("valorGlobal") or melhor.get("valorInicial"),
        "assinado_em": melhor.get("dataAssinatura"),
        "numero": melhor.get("numeroContratoEmpenho"),
        "sequencial": melhor.get("sequencialContrato"),
        "objeto": (melhor.get("objetoContrato") or "")[:220],
    }


def carrega(caminho: Path) -> dict:
    txt = caminho.read_text(encoding="utf8")
    if caminho.suffix.lower() == ".json":
        return json.loads(txt)
    m = re.search(r"/\*DADOS\*/(.*?)/\*FIM\*/", txt, re.S)
    if not m:
        raise SystemExit(f"FALHA: bloco /*DADOS*/ não encontrado em {caminho}")
    return json.loads(m.group(1))


def do_estado(estado: dict) -> None:
    alvos = [e for e in estado.get("editais", []) if e.get("disputa") == "decidido"]
    if not alvos:
        print("Nenhum edital marcado como 'decidido' no radar — nada a cruzar.")
        return
    print(f"=== {len(alvos)} contratações já decididas: quem ficou com elas ===\n")
    achados = 0
    for e in alvos:
        r = procura(e.get("cnpj"), e.get("publicado_em"), e.get("objeto"))
        cab = f"{e.get('orgao', '')[:52]} · {e.get('uf')}"
        if r["achou"]:
            achados += 1
            v = f"R$ {r['valor']:,.0f}" if r.get("valor") else "valor não informado"
            print(f"  {cab}")
            print(f"    → {r['fornecedor']}  ·  {v}  ·  assinado {r['assinado_em'][:10]}")
            print(f"      {e['objeto'][:110]}")
        else:
            print(f"  {cab}")
            print(f"    → sem contrato correspondente ({r['motivo']})")
        print()
        time.sleep(1.0)
    print(f"{achados} de {len(alvos)} com fornecedor identificado.")
    if achados:
        print("\nIsto não é uma lista de oportunidades perdidas — é o mapa de quem")
        print("compra o que a Thutor vende, quanto paga, e contra quem se concorre.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--do-estado", metavar="ARQUIVO")
    ap.add_argument("resto", nargs="*", help="cnpj AAAAMMDD 'trecho do objeto'")
    a = ap.parse_args()

    if a.do_estado:
        do_estado(carrega(Path(a.do_estado)))
        return
    if len(a.resto) < 3:
        raise SystemExit(__doc__)

    cnpj, data, objeto = a.resto[0], a.resto[1], " ".join(a.resto[2:])
    r = procura(cnpj, f"{data[:4]}-{data[4:6]}-{data[6:]}", objeto)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    if not r["achou"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
