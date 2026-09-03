#!/usr/bin/env python3
"""
O contrato com a API do PNCP.

Este é o teste que protege contra a pior falha possível deste projeto, e ela é
silenciosa: se o PNCP renomear `objetoCompra`, mudar `valorTotalEstimado` de
número para texto ou parar de informar `totalRegistros`, nada estoura. A coleta
roda, os filtros não encontram nada, o radar amanhece vazio — e um radar vazio é
indistinguível de um dia sem oportunidade. Ninguém sente falta do que nunca
apareceu na lista.

O validador não pega isso: ele confere que a coleta viu tudo o que a API
prometeu, e uma API que promete zero cumpre a promessa.

Por isso este teste fala com a API DE VERDADE, não com um dublê. Um dublê
congela a resposta de hoje e passa a confirmar a suposição de ontem — que é
exatamente o que se quer detectar. Sem rede, o teste avisa e sai sem reprovar:
falta de rede não é regressão.

    python3 tools/teste_coleta.py
    python3 tools/teste_coleta.py --data 20260902
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
from coleta_pncp import BASE, MODALIDADES, identifica, link  # noqa: E402
from perfil import avalia  # noqa: E402

TZ = ZoneInfo("America/Sao_Paulo")
PAUSA_429 = 12.0   # o rate limit do PNCP pede espera de segundos, não de milissegundos
PAUSA_ENTRE = 1.5  # ritmo educado ao percorrer as modalidades

# Campos de que o projeto depende. A coluna do meio diz onde eles são usados —
# se um deles sumir, é isso que quebra.
CAMPOS = [
    ("objetoCompra",            str,   "todo o filtro de tools/perfil.py"),
    ("valorTotalEstimado",      float, "a nota de valor e o corte de ticket"),
    ("modalidadeNome",          str,   "a nota de modalidade"),
    ("numeroControlePNCP",      str,   "a identidade do edital entre rodadas"),
    ("dataPublicacaoPncp",      str,   "a data que aparece no radar"),
    ("dataEncerramentoProposta", str,  "a aba Prazos inteira"),
    ("situacaoCompraNome",      str,   "o estado do edital"),
]
# Blocos aninhados: (caminho, chaves obrigatórias)
BLOCOS = [
    ("orgaoEntidade", ("cnpj", "razaoSocial")),
    ("unidadeOrgao", ("ufSigla", "nomeUnidade")),
]
ENVELOPE = ("data", "totalRegistros", "totalPaginas")


# Sondado em 03/09/2026: a API aceita tamanhoPagina entre 10 e 50. Fora disso
# devolve HTTP 400 — inclusive para 1, que seria o natural numa sondagem.
def busca(modalidade: int, dia: str, tam: int = 10) -> tuple[dict | None, str]:
    """
    Uma amostra de uma modalidade, com paciência para o rate limit.

    O 429 aparece rápido quando se percorrem as onze modalidades em sequência —
    foi o que este próprio teste provocou na primeira execução. Insistir no
    mesmo ritmo só renova a recusa, e reportá-la como "a modalidade sumiu" seria
    um alarme falso das piores: aquele que ensina a ignorar o alarme.
    """
    url = (f"{BASE}?dataInicial={dia}&dataFinal={dia}"
           f"&codigoModalidadeContratacao={modalidade}&pagina=1&tamanhoPagina={tam}")
    ultimo = ""
    for tentativa in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                corpo = r.read()
            return (json.loads(corpo) if corpo.strip()
                    else {"data": [], "totalRegistros": 0}), ""
        except urllib.error.HTTPError as e:
            if e.code == 204:
                return {"data": [], "totalRegistros": 0}, ""
            ultimo = f"HTTP {e.code}"
            if e.code != 429:
                return None, ultimo
            time.sleep(PAUSA_429 * (tentativa + 1))
        except Exception as e:
            ultimo = str(e)[:120]
            time.sleep(2 * (tentativa + 1))
    return None, ultimo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", help="AAAAMMDD; padrão: ontem")
    a = ap.parse_args()
    dia = a.data or (datetime.now(TZ).date() - timedelta(days=1)).strftime("%Y%m%d")

    falhas: list[str] = []
    print(f"--- conversando com o PNCP sobre {dia} ---")

    # Pregão eletrônico é a modalidade mais movimentada: se algum dia tiver
    # registros, é esse.
    d, erro = busca(6, dia)
    if d is None:
        print(f"aviso: a API não respondeu ({erro}).")
        print("       Sem rede não há regressão a apurar — teste encerrado sem reprovar.")
        return

    for k in ENVELOPE:
        if k not in d:
            falhas.append(f"o envelope da resposta perdeu '{k}' — a paginação de "
                          "tools/coleta_pncp.py depende dele.")
    itens = d.get("data") or []
    print(f"ok   envelope: {d.get('totalRegistros')} registros, "
          f"{d.get('totalPaginas')} páginas, {len(itens)} nesta amostra")

    if not itens:
        print("aviso: nenhum registro nesse dia (feriado ou fim de semana?).")
        print("       Rode com --data num dia útil para conferir os campos.")
        if falhas:
            _encerra(falhas)
        return

    # --- os campos que o projeto lê ---------------------------------------
    print(f"\n--- campos, em {len(itens)} registros reais ---")
    for campo, tipo, onde in CAMPOS:
        presentes = [i for i in itens if campo in i]
        if not presentes:
            falhas.append(f"campo '{campo}' sumiu de TODOS os registros — quebra {onde}.")
            print(f"FALHOU {campo:26s} ausente")
            continue
        # Nulo é legítimo (valor sigiloso, prazo em aberto); tipo errado, não.
        errados = [i for i in presentes
                   if i[campo] is not None and not isinstance(i[campo], tipo)
                   and not (tipo is float and isinstance(i[campo], int))]
        if errados:
            amostra = repr(errados[0][campo])[:60]
            falhas.append(f"campo '{campo}' mudou de tipo (esperado {tipo.__name__}, "
                          f"veio {amostra}) — afeta {onde}.")
            print(f"FALHOU {campo:26s} tipo inesperado")
        else:
            nulos = sum(1 for i in presentes if i[campo] is None)
            print(f"ok     {campo:26s} {len(presentes)}/{len(itens)} presentes"
                  + (f", {nulos} nulos" if nulos else ""))

    for bloco, chaves in BLOCOS:
        amostra = next((i[bloco] for i in itens if isinstance(i.get(bloco), dict)), None)
        if amostra is None:
            falhas.append(f"o bloco '{bloco}' sumiu — sem ele não há órgão nem UF no radar.")
            print(f"FALHOU {bloco:26s} ausente")
            continue
        faltando = [k for k in chaves if k not in amostra]
        if faltando:
            falhas.append(f"o bloco '{bloco}' perdeu {faltando}.")
            print(f"FALHOU {bloco:26s} sem {faltando}")
        else:
            print(f"ok     {bloco:26s} {list(chaves)}")

    # --- as funções que dependem do formato --------------------------------
    print("\n--- o que o projeto monta a partir disso ---")
    reg = itens[0]
    ident, url = identifica(reg), link(reg)
    print(f"ok     id     {ident}")
    print(f"ok     link   {url}")
    if not ident.startswith("pncp:") or ident == "pncp:":
        falhas.append(f"identifica() devolveu um id degenerado ({ident!r}) — sem id "
                      "estável, o mesmo edital reaparece como novo todo dia.")
    if not url.startswith("https://pncp.gov.br/app/editais/"):
        falhas.append(f"link() não montou a página do edital ({url!r}).")

    # --- as modalidades ainda existem? -------------------------------------
    print("\n--- modalidades declaradas em tools/coleta_pncp.py ---")
    vivas, mortas = [], []
    for m in sorted(MODALIDADES):
        r, e = busca(m, dia)
        (mortas if r is None else vivas).append((m, MODALIDADES[m], e))
        time.sleep(PAUSA_ENTRE)
    for m, nome, e in mortas:
        falhas.append(f"modalidade {m} ({nome}) não respondeu: {e}")
    print(f"ok     {len(vivas)} de {len(MODALIDADES)} modalidades responderam")
    if mortas:
        print("FALHOU " + ", ".join(f"{m} {n}" for m, n, _ in mortas))

    # --- o filtro ainda encontra alguma coisa? -----------------------------
    # Não se exige candidato numa amostra de 10 registros; exige-se que a
    # avaliação atravesse dado real sem estourar.
    print("\n--- o filtro contra os registros reais ---")
    try:
        notas = [avalia(i.get("objetoCompra"), i.get("valorTotalEstimado"),
                        i.get("modalidadeNome"), i.get("informacaoComplementar"))
                 for i in itens]
        print(f"ok     {len(notas)} objetos avaliados sem erro "
              f"(maior nota da amostra: {max(n['score'] for n in notas)})")
    except Exception as e:
        falhas.append(f"tools/perfil.py estourou com um objeto real: {e}")
        print(f"FALHOU perfil.avalia: {e}")

    _encerra(falhas)


def _encerra(falhas: list[str]) -> None:
    print()
    if falhas:
        print(f"FALHA: a API do PNCP não está mais como o projeto espera "
              f"({len(falhas)} problema(s)).")
        for f in falhas:
            print(f"  - {f}")
        print()
        print("Isto NÃO é um teste chato: enquanto não for corrigido, a coleta roda,")
        print("não acha nada, e o radar amanhece vazio sem ninguém desconfiar.")
        raise SystemExit(1)
    print("ok  a API responde no formato que tools/coleta_pncp.py e tools/perfil.py esperam.")


if __name__ == "__main__":
    main()
