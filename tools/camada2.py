#!/usr/bin/env python3
"""
A camada 2, buscada por código — e não por um agente batendo em portais.

O que mudou, e por quê
──────────────────────
Até 06/09/2026 a camada 2 era um plano em prosa: `fontes_externas.py` listava
quinze portais e o agente da madrugada visitava um por um com WebFetch. Em três
rodadas isso rendeu **zero candidatos**, com metade das fontes devolvendo HTTP
403 ou página vazia. A conclusão fácil seria "os portais bloqueiam robô".

A conclusão certa apareceu ao testar: **eram bloqueios de User-Agent.** O mesmo
endereço que devolve 403 para um cliente genérico devolve 200 para um
User-Agent de navegador. E o Canal do Fornecedor do Sebrae, que parecia uma
página vazia de JavaScript, tem por trás um endpoint que devolve JSON com as
licitações do Sistema inteiro — Nacional e as 27 unidades estaduais.

Daí este arquivo. A camada 2 deixa de ser uma tarefa de leitura e vira uma
coleta como a do PNCP: determinística, testável, e capaz de rodar sem que
ninguém precise interpretar uma página.

O que foi investigado, portal a portal, em 06/09/2026
─────────────────────────────────────────────────────
    Sebrae (Canal do Fornecedor)  JSON de todo o Sistema. FUNCIONA — está aqui.
    SESI-SP                       lista dez PDFs cujos nomes são só números
                                  ("PSDA 532-2026BB.pdf"); o objeto só existe
                                  dentro do arquivo. Exigiria abrir PDF por PDF
                                  todo dia para um rendimento improvável.
    SENAI-SC                      publica planilha .ods — de CONTRATOS de 2022.
                                  Histórico assinado, não edital aberto.
    Senac DN, Sesc DN, Senac-ES   403 e desafio de Cloudflare mesmo com
                                  User-Agent de navegador. Precisam de
                                  navegador de verdade, o que é outro custo.
    SENAI-SP, SENAI-MS, CNI       o proxy de saída recusou a conexão.

Uma ressalva honesta sobre o Sebrae, porque ele é o que mais promete e o que
menos entrega por esta via: consultoria e instrutoria no Sistema Sebrae são
contratadas por CREDENCIAMENTO (o SGF), não por licitação avulsa. As subáreas
1.5 Cultura e Clima, 1.6 Liderança, 1.10 Planejamento Estratégico de Pessoal,
7.2 Planejamento Estratégico e 7.3 Gestão de Processos são o portfólio da
Thutor com outro nome — e quem não está credenciado não é chamado. Este script
pega o que sobra em licitação; a porta principal é o credenciamento, e ela se
abre uma vez, não todo dia.

    python3 tools/camada2.py                 # colhe e mostra os candidatos
    python3 tools/camada2.py --saida x.json
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perfil import LIMIAR_CANDIDATO, avalia          # noqa: E402

TZ = timezone(timedelta(hours=-3))

# A descoberta que destravou a camada. Um cliente sem isto leva 403 de metade
# dos portais do Sistema S; com isto, os mesmos endereços respondem 200. Não é
# disfarce: é o cabeçalho que qualquer navegador manda, e sem ele os servidores
# assumem que a requisição é de um raspador de conteúdo.
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

TENTATIVAS, PAUSA = 3, 4.0


def pega(url: str, timeout: int = 60) -> tuple[int, str]:
    """Uma página, com User-Agent de navegador e repetição em espera crescente."""
    ultimo = 0
    for t in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9",
                "X-Requested-With": "XMLHttpRequest",
            })
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            ultimo = e.code
            if e.code in (403, 429, 503) and t < TENTATIVAS - 1:
                time.sleep(PAUSA * (t + 1))
                continue
            return e.code, ""
        except Exception:
            if t < TENTATIVAS - 1:
                time.sleep(PAUSA * (t + 1))
                continue
            return ultimo or 0, ""
    return ultimo or 0, ""


def _data_dotnet(v) -> str | None:
    """`/Date(1790046000000)/` — o formato do ASP.NET, que ninguém mais usa."""
    m = re.search(r"/Date\((-?\d+)", str(v or ""))
    if not m:
        return None
    try:
        return datetime.fromtimestamp(int(m.group(1)) / 1000, TZ).isoformat(timespec="seconds")
    except (ValueError, OSError, OverflowError):
        return None


# ───────────────────────── as fontes ─────────────────────────

SEBRAE_GRID = ("https://scf3.sebrae.com.br/PortalCf/Home/GetLicitacoesGrid"
               "?draw=1&start=0&length=500")
SEBRAE_DETALHE = "https://scf3.sebrae.com.br/PortalCf/Licitacoes/Detalhe/{}"


def sebrae() -> dict:
    """
    O Canal do Fornecedor: as licitações abertas de todo o Sistema Sebrae.

    A grade da home traz só o que está publicado e em andamento, que é
    exatamente a pergunta do radar. Medido em 06/09/2026: seis licitações
    abertas no Sistema inteiro — energia solar no TO, CFTV no PA, quick massage
    para a Feira do Empreendedor em SP. Nenhuma aderente, e isso não é defeito
    da fonte: é o que sobra depois que consultoria vai toda para o
    credenciamento.
    """
    st, corpo = pega(SEBRAE_GRID)
    if st != 200 or not corpo.strip():
        return {"id": "sebrae-scf", "nome": "Sebrae — Canal do Fornecedor",
                "abriu": False, "erro": f"HTTP {st}", "itens": []}
    try:
        dados = json.loads(corpo).get("aaData") or []
    except json.JSONDecodeError as e:
        return {"id": "sebrae-scf", "nome": "Sebrae — Canal do Fornecedor",
                "abriu": False, "erro": f"JSON inválido: {e}", "itens": []}

    itens = []
    for x in dados:
        if (x.get("SituacaoDescricao") or "").lower() != "publicado":
            continue
        numero = (x.get("Numero") or "").strip()
        # "PE/006-SEBRAE-TO-2026" carrega a unidade no próprio número, e é a
        # única pista de UF que a grade oferece.
        uf = None
        m = re.search(r"SEBRAE-([A-Z]{2})-", numero)
        if m:
            uf = m.group(1)
        itens.append({
            "id": f"sebrae:{x.get('Id')}",
            "fonte": "Sebrae/SCF",
            "orgao": f"SEBRAE{'/' + uf if uf else ''}",
            "uf": uf,
            "modalidade": x.get("TipoDescricao") or x.get("SituacaoDescricao"),
            "objeto": " ".join((x.get("Objeto") or "").split()),
            "numero": numero,
            "valor": 0,          # a grade não publica valor estimado
            "sigiloso": True,    # e sem valor o radar trata como incógnita
            "abertura": _data_dotnet(x.get("DataAbertura")),
            "encerramento": _data_dotnet(x.get("DataEncerramento")),
            "publicado_em": (_data_dotnet(x.get("DataPublicacao")) or "")[:10] or None,
            "link": SEBRAE_DETALHE.format(x.get("Id")),
        })
    return {"id": "sebrae-scf", "nome": "Sebrae — Canal do Fornecedor",
            "abriu": True, "erro": None, "itens": itens}


# Os portais que NÃO rendem item, e o motivo medido em 06/09/2026. Continuam
# sendo sondados toda noite de propósito, por dois motivos: um portal que hoje
# devolve 403 pode responder amanhã, e o registro de falhas é o que faz alguém
# perceber que uma fonte morreu — abandonar em silêncio é como perder cliente
# por não ligar. A sonda é barata: uma requisição por fonte.
SONDAS = (
    ("sesi-sp", "SESI-SP — transparência",
     "https://transparencia.sesisp.org.br/licitacoes/licitacoes-editais",
     "abre, mas lista só nomes de PDF sem objeto ('PSDA 532-2026BB.pdf'); "
     "o que interessa está dentro do arquivo"),
    ("senai-sc", "SENAI-SC — transparência",
     "https://transparencia.sc.senai.br/licitacoes-e-editais",
     "a planilha publicada é de CONTRATOS de 2022, não de editais abertos"),
    ("senac-es", "Senac-ES", "https://es.senac.br/licitacoes",
     "desafio de Cloudflare: responde 200 com 'verificando sua requisição'"),
    ("senac-dn", "Senac — Departamento Nacional",
     "https://www.senac.br/transparencia/licitacoes.aspx",
     "HTTP 403 mesmo com User-Agent de navegador"),
    ("sesc-dn", "Sesc — Departamento Nacional", "https://www.sesc.com.br/licitacoes/",
     "HTTP 403 mesmo com User-Agent de navegador"),
    ("senai-sp", "SENAI-SP — transparência",
     "https://transparencia.sp.senai.br/licitacoes/licitacoes-editais",
     "o proxy de saída recusou a conexão"),
    ("cni", "Sistema Indústria — CNI",
     "https://www.portaldaindustria.com.br/cni/canais/licitacoes/",
     "tempo esgotado"),
    ("bec-sp", "BEC/SP", "https://www.bec.sp.gov.br/",
     "home com estatísticas; a lista fica atrás de formulário de busca"),
)


def sonda(id_: str, nome: str, url: str, nota: str) -> dict:
    """Bate na porta e registra o que aconteceu. Não extrai nada."""
    st, corpo = pega(url, timeout=40)
    abriu = st == 200 and len(corpo) > 2000
    return {"id": id_, "nome": nome, "abriu": abriu, "itens": [],
            "erro": None if abriu else f"HTTP {st}" if st else "sem resposta",
            "nota": nota}


FONTES = (sebrae,) + tuple(
    (lambda i=i, n=n, u=u, o=o: sonda(i, n, u, o)) for i, n, u, o in SONDAS)


def colhe(min_score: int = 0) -> dict:
    inicio = datetime.now(TZ)
    tentadas = abertas = 0
    falhas: list[str] = []
    sem_candidato: list[str] = []
    candidatos: list[dict] = []
    brutos = 0

    for fn in FONTES:
        r = fn()
        tentadas += 1
        if not r["abriu"]:
            falhas.append(f"{r['nome']}: {r['erro']}"
                          + (f" — {r['nota']}" if r.get("nota") else ""))
            continue
        abertas += 1
        if r.get("nota"):
            # Abriu, mas já se sabe que não rende item por esta via.
            sem_candidato.append(f"{r['nome']}: {r['nota']}")
            continue
        brutos += len(r["itens"])
        achou = 0
        for it in r["itens"]:
            a = avalia(it["objeto"], it.get("valor"), it.get("modalidade"), "")
            if a["score"] < max(min_score, LIMIAR_CANDIDATO):
                continue
            achou += 1
            candidatos.append({**it, "score": a["score"], "frentes": a["frentes"],
                               "achados": a["achados"],
                               # Não há como conferir situação no PNCP: a fonte é
                               # outra. Fica "aberto" porque a grade só devolve o
                               # que está publicado e em andamento.
                               "disputa": "aberto", "situacao_item": "em_disputa",
                               "situacao": "Publicado"})
        if not achou:
            sem_candidato.append(f"{r['nome']} ({len(r['itens'])} abertos, nenhum do tema)")

    candidatos.sort(key=lambda c: -c["score"])
    return {
        "cobertura": {
            "fonte": "camada 2 (código)",
            "tentadas": tentadas, "abertas": abertas,
            "brutos": brutos, "candidatos": len(candidatos),
            "falhas": falhas, "sem_candidato": sem_candidato,
            "iniciado_em": inicio.isoformat(timespec="seconds"),
            "concluido_em": datetime.now(TZ).isoformat(timespec="seconds"),
        },
        "candidatos": candidatos,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", type=Path)
    a = ap.parse_args()

    r = colhe()
    c = r["cobertura"]
    print(f"ok  {c['abertas']}/{c['tentadas']} fonte(s) abriram · "
          f"{c['brutos']} licitação(ões) aberta(s) · {c['candidatos']} candidato(s)")
    for f in c["falhas"]:
        print(f"    falhou: {f}")
    for s in c["sem_candidato"]:
        print(f"    sem tema: {s}")
    for cand in r["candidatos"][:10]:
        print(f"    [{cand['score']:>2}] {cand['orgao']} · {cand['numero']}")
        print(f"         {cand['objeto'][:150]}")
    if a.saida:
        a.saida.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf8")
        print(f"    → {a.saida}")


if __name__ == "__main__":
    main()
