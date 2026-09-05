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

Duas rodadas de investigação, e a segunda desmentiu a primeira
────────────────────────────────────────────────────────────
Na primeira passada, seis portais foram anotados como sem serventia. Na
segunda, três deles renderam — e renderam porque a primeira anotação tinha
sido escrita a partir da primeira página que respondeu, não do que o portal
de fato publica. Fica registrado assim de propósito, com o engano à vista:

    Sebrae (Canal do Fornecedor)  JSON de todo o Sistema. 6 abertas.
    SESI-SP e SENAI-SP            "só nomes de PDF sem objeto" — ERRADO. Cada
                                  PDF está dentro de um <article> com objeto
                                  por extenso e data de abertura das propostas.
                                  57 abertas com sessão à frente.
    Sistema FIESC (SC)            "planilha .ods de CONTRATOS de 2022" — ERRADO
                                  para a fonte certa: a mesma página aponta
                                  para transparencia.fiesc.com.br, que tem API
                                  JSON. 32 em andamento.
    Sesc DN                       "HTTP 403" — era falta de Sec-Fetch-*. 15
                                  abertas, em página WordPress comum.
    Senac-ES                      "desafio de Cloudflare" — mesma causa. Traz
                                  os 57 processos do ano; a data da sessão
                                  separa o aberto do encerrado.
    Senac DN                      bloqueado de verdade, pelo sistema de
                                  proteção do próprio Senac, com mensagem
                                  explícita. Continua sondado, não resolvido.
    CNI                           nunca respondeu (502 e tempo esgotado).
    BEC/SP                        exige sessão ASP.NET — e é redundante: o
                                  Estado de SP publica no PNCP.

Navegador de verdade não é saída aqui: o Chromium instalado nesta máquina não
atravessa o proxy de saída (ERR_PROXY_CONNECTION_FAILED na porta do ambiente,
conexão reinicializada na porta que o proxy declara). A rotina das 02:00 roda
no mesmo lugar, então o que não abrir por HTTP não abre.

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
import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perfil import LIMIAR_CANDIDATO, avalia          # noqa: E402

TZ = timezone(timedelta(hours=-3))

# A descoberta que destravou a camada. Um cliente sem isto leva 403 de metade
# dos portais do Sistema S; com isto, os mesmos endereços respondem 200. Não é
# disfarce: é o cabeçalho que qualquer navegador manda, e sem ele os servidores
# assumem que a requisição é de um raspador de conteúdo.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# O conjunto que um Chrome manda numa navegação. Não é disfarce: é o cabeçalho
# de verdade, e o que se descobriu em 06/09/2026 é que a diferença entre 403 e
# 200 não estava no User-Agent sozinho — estava nos Sec-Fetch-*. Sesc DN saiu de
# 403 para 200 e Senac-ES saiu de desafio de Cloudflare para a página inteira só
# por causa deles. Accept-Encoding fica DE FORA de propósito: urllib não
# descomprime, e pedir gzip aqui devolveria bytes ilegíveis.
NAVEGADOR = {
    "User-Agent": UA,
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "image/avif,image/webp,*/*;q=0.8"),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# Para os endpoints que respondem JSON a uma chamada de página (o do Sebrae).
AJAX = {"Accept": "application/json, text/javascript, */*;q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"}

TENTATIVAS, PAUSA = 3, 4.0


def pega(url: str, timeout: int = 60, extra: dict | None = None,
         exige: tuple[str, ...] = ()) -> tuple[int, str]:
    """
    Uma página, com cabeçalho de navegador e repetição em espera crescente.

    `exige` são marcas que o corpo PRECISA conter para a resposta valer. Existe
    por causa de duas coisas observadas em 06/09/2026 em es.senac.br, e as duas
    devolvem HTTP 200:

      · uma leitura curta — 12 KB de uma página de 739 KB, cortada no meio de
        um Transfer-Encoding chunked;
      · um interstício anti-robô — 11,9 KB de JavaScript ofuscado que termina
        em `</html>` como qualquer página honesta.

    As duas viram, sem esta conferência, "a fonte abriu e não tinha nenhum
    edital". É o modo de falha silenciosa que este projeto existe para não ter,
    e é por isso que a marca exigida é conteúdo do miolo, não o fim do arquivo:
    `</html>` o disfarce também tem.
    """
    ultimo = 0
    for t in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={**NAVEGADOR, **(extra or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corpo = r.read().decode("utf-8", errors="replace")
            if any(marca not in corpo for marca in exige):
                ultimo = -1
                if t < TENTATIVAS - 1:
                    time.sleep(PAUSA * (t + 1))
                    continue
                return -1, ""
            return r.status, corpo
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


def _texto(s: str) -> str:
    """HTML para texto corrido, do jeito grosseiro que basta aqui."""
    s = re.sub(r"<br\s*/?>", " | ", s or "")
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s)).split())


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
    st, corpo = pega(SEBRAE_GRID, extra=AJAX)
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


SESC_DN = "https://www.sesc.com.br/licitacoes/licitacoes-em-andamento-v2/"


def sesc_dn() -> dict:
    """
    Sesc — Departamento Nacional. A lista existe no HTML; o difícil era chegar.

    Até 06/09/2026 esta fonte estava marcada como "HTTP 403 mesmo com
    User-Agent de navegador" e sondada sem esperança. O 403 caiu com os
    cabeçalhos Sec-Fetch-*, e a página de capa revelou que as abas
    (Em andamento / Concluídas / Canceladas) são três páginas WordPress
    separadas — nada de JavaScript, nada de endpoint escondido. A de interesse é
    uma só: as em andamento.

    Só entra quem está com "Situação: Aberta". "Suspensa" fica de fora porque
    não dá para mandar proposta em certame suspenso, e o radar só guarda o que
    ainda dá para pescar.

    A data em laranja de cada bloco NÃO é usada como encerramento: medido em
    06/09/2026, itens marcados "Aberta" trazem datas de 2025 e de 2026 sem
    ordem, o que a desqualifica como prazo. Vai como referência e o edital
    entra sem prazo declarado, que é o que se sabe de verdade.
    """
    nome = "Sesc — Departamento Nacional"
    st, corpo = pega(SESC_DN, exige=("sesc-licitacao__link", "</html>"))
    if st != 200:
        return {"id": "sesc-dn", "nome": nome, "abriu": False, "itens": [],
                "erro": "resposta sem o conteúdo esperado (leitura curta ou interstício anti-robô)" if st == -1 else f"HTTP {st}"}

    # As modalidades são <h2 class="sesc-section__title"> e valem para todos os
    # blocos que vierem depois, até o próximo título.
    titulos = [(m.start(), _texto(m.group(1))) for m in
               re.finditer(r'<h2[^>]*sesc-section__title[^>]*>(.*?)</h2>', corpo, re.S)]

    itens = []
    for m in re.finditer(r'<div class="[^"]*\bsesc-licitacao\b[^"]*"(.*?)(?=<div class="[^"]*\bsesc-licitacao\b|</main)',
                         corpo, re.S):
        bloco = m.group(1)
        num = re.search(r'sesc-licitacao__link.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                        bloco, re.S)
        textos = re.findall(r'sesc-licitacao__texto[^"]*"[^>]*>(.*?)</p>', bloco, re.S)
        if not num or not textos:
            continue
        meta = _texto(textos[1]) if len(textos) > 1 else ""
        sit = re.search(r"Situação:\s*([^|]+)", meta)
        situacao = (sit.group(1).strip() if sit else "")
        if situacao.lower() != "aberta":
            continue
        data = re.search(r'sesc-licitacao__texto__orange[^>]*>\s*([\d/]+)\s*<', bloco)
        numero = _texto(num.group(2))
        modal = [t for pos, t in titulos if pos < m.start()]
        itens.append({
            "id": f"sesc-dn:{numero}",
            "fonte": "Sesc/DN",
            "orgao": "Sesc — Departamento Nacional",
            "uf": None,
            "modalidade": modal[-1] if modal else None,
            "objeto": _texto(textos[0]),
            "numero": numero,
            "valor": 0,
            "sigiloso": True,
            "referencia": data.group(1) if data else None,
            "encerramento": None,
            "publicado_em": None,
            "situacao": f"Aberta · {meta}"[:180],
            "link": num.group(1),
        })
    return {"id": "sesc-dn", "nome": nome, "abriu": True, "erro": None, "itens": itens}


SENAC_ES = "https://es.senac.br/licitacoes"


def senac_es() -> dict:
    """
    Senac-ES. O "desafio de Cloudflare" era falta de Sec-Fetch-*.

    A página traz os 57 processos do ano inteiro num acordeão, abertos e
    encerrados no mesmo lugar e sem campo de situação. O que separa um do outro
    é a data no cabeçalho de cada processo, que é a data da sessão de abertura
    — conferido item a item contra o corpo do edital ("Data da Reunião de
    Abertura: A partir das 09h00 do dia 19/05/2026" bate com o 19/05/2026 do
    cabeçalho). Então a regra é a mais simples que existe: sessão no futuro,
    ainda dá para disputar; sessão no passado, acabou.

    Medido em 06/09/2026: dos 57, um só tem sessão à frente. Não é fonte
    volumosa — é fonte de exceção, e o custo dela é uma requisição por noite.
    """
    nome = "Senac-ES"
    st, corpo = pega(SENAC_ES, exige=('id="heading-licitacao-', "</html>"))
    if st != 200:
        return {"id": "senac-es", "nome": nome, "abriu": False, "itens": [],
                "erro": "resposta sem o conteúdo esperado (leitura curta ou interstício anti-robô)" if st == -1 else f"HTTP {st}"}

    grupos = {m.group(1): _texto(m.group(2)) for m in re.finditer(
        r'id="heading-licitacao-(\d+)".*?<button[^>]*>(.*?)</button>', corpo, re.S)}

    hoje = datetime.now(TZ).date()
    itens = []
    for m in re.finditer(
            r'id="heading-processo-(\d+)".*?<span>(.*?)</span>(.*?)</button>'
            r'(.*?)(?=<div class="accordion-item">|</div>\s*</div>\s*</div>\s*</div>)',
            corpo, re.S):
        proc, titulo, cauda, corpo_proc = m.groups()
        d = re.search(r"(\d{2})/(\d{2})/(\d{4})", cauda)
        if not d:
            continue
        try:
            sessao = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        except ValueError:
            continue
        if sessao < hoje:
            continue
        pai = re.search(r'data-bs-parent="#accordion-processos-(\d+)"', corpo_proc)
        objeto = _texto(titulo)
        # O objeto do cabeçalho é o título; o do corpo é o texto do aviso, bem
        # mais rico. Perfil pontua o que lê, então vale juntar os dois.
        detalhe = _texto(corpo_proc)[:1500]
        itens.append({
            "id": f"senac-es:{proc}",
            "fonte": "Senac/ES",
            "orgao": "SENAC — Departamento Regional do Espírito Santo",
            "uf": "ES",
            "modalidade": grupos.get(pai.group(1)) if pai else None,
            "objeto": (objeto + " — " + detalhe).strip(" —"),
            "numero": objeto[:80],
            "valor": 0,
            "sigiloso": True,
            "encerramento": sessao.isoformat(),
            "publicado_em": None,
            "situacao": f"Sessão em {d.group(0)}",
            "link": SENAC_ES,
        })
    return {"id": "senac-es", "nome": nome, "abriu": True, "erro": None, "itens": itens}


# O mesmo sistema serve a transparência do SESI-SP e a do SENAI-SP. Um endereço
# por entidade, o mesmo HTML dos dois lados.
SP_HOSTS = (("sesi-sp", "SESI-SP", "transparencia.sesisp.org.br"),
            ("senai-sp", "SENAI-SP", "transparencia.sp.senai.br"))
SP_GRID = ("https://{}/LicitacoesEEditais/GetPartialLicitacoes"
           "?Ordem=Mais%20recentes%20primeiro&Tamanho=200&Ano={}")


def _sp(id_: str, entidade: str, host: str) -> dict:
    """
    SESI-SP e SENAI-SP. A anotação anterior sobre estas duas fontes estava
    errada, e o erro custou três semanas de fonte fechada à toa.

    O que estava escrito aqui era "lista só nomes de PDF sem objeto
    ('PSDA 532-2026BB.pdf')". É o que se vê parando no primeiro link da página.
    Duas linhas de HTML acima de cada link existe um <article class="edital">
    com número, entidade, resumo, status, objeto por extenso e — o que decide
    tudo — a Data de Abertura das Propostas. A página só mostra dez por vez, e
    a mesma partial que o site chama por AJAX aceita Tamanho=200.

    Medido em 06/09/2026: 200 processos de 2026 por entidade, 262 marcados
    "Aberto/Em Execução", e 25 no SESI-SP com abertura de proposta ainda por
    vir. A lição para as outras fontes: "abre mas não tem nada útil" é uma
    conclusão que precisa de prova, não de impressão.

    O status "Aberto/Em Execução" mistura edital aberto com contrato em
    andamento; é a data de abertura das propostas que separa um do outro, e é
    por isso que ela é obrigatória aqui. Sem data, o registro não entra.

    Limite conhecido: a consulta é por ano do processo. Na virada do ano, um
    edital de dezembro com sessão em janeiro fica de fora por um dia — some do
    ano velho antes de o novo existir. Buscar dois anos dobraria 3 MB de
    resposta por entidade toda noite para cobrir uma janela de 24 horas.
    """
    nome = f"{entidade} — transparência"
    ano = datetime.now(TZ).year
    st, corpo = pega(SP_GRID.format(host, ano), timeout=90, extra=AJAX,
                     exige=('<article class="edital">',))
    if st != 200:
        return {"id": id_, "nome": nome, "abriu": False, "itens": [],
                "erro": "resposta sem o conteúdo esperado" if st == -1 else f"HTTP {st}"}

    hoje = datetime.now(TZ).date()
    itens = []
    for bloco in corpo.split('<article class="edital">')[1:]:
        def campo(marca_: str, fecha: str = "</span>") -> str:
            m = re.search(rf'id="{marca_}"[^>]*>(.*?){fecha}', bloco, re.S)
            return _texto(m.group(1)) if m else ""

        if not campo("Status").lower().startswith("aberto"):
            continue
        d = re.search(r"Data de Abertura das Propostas.*?<li[^>]*>\s*(\d{2})/(\d{2})/(\d{4})",
                      bloco, re.S)
        if not d:
            continue
        try:
            sessao = date(int(d.group(3)), int(d.group(2)), int(d.group(1)))
        except ValueError:
            continue
        if sessao < hoje:
            continue

        numero = campo("NumeroTipo", "</div>").strip("| ")
        doc = re.search(r'href="(/licitacoes/DocumentosSap[^"]+)"', bloco)
        itens.append({
            "id": f"{id_}:{numero}",
            "fonte": entidade,
            "orgao": f"{entidade} — Departamento Regional de São Paulo",
            "uf": "SP",
            "modalidade": numero.split("|")[-1].strip() or None,
            "objeto": " — ".join(x for x in (campo("Resumo", "</h3>"), campo("Objeto")) if x),
            "numero": numero,
            "valor": 0,
            "sigiloso": True,
            "encerramento": sessao.isoformat(),
            "publicado_em": None,
            "situacao": campo("Status"),
            "link": f"https://{host}{html.unescape(doc.group(1))}" if doc
                    else f"https://{host}/licitacoes/licitacoes-editais",
        })
    return {"id": id_, "nome": nome, "abriu": True, "erro": None, "itens": itens}


FIESC_API = "https://transparencia.fiesc.com.br/api/licitacoes/?status=A&current=1"


def fiesc() -> dict:
    """
    Sistema FIESC: SESI/SC, SENAI/SC, IEL/SC e a federação, numa API só.

    Segunda anotação errada corrigida na mesma noite. Estava escrito que o
    SENAI-SC "publica planilha .ods — de CONTRATOS de 2022"; é verdade, e é
    irrelevante, porque no meio da mesma página há um link chamado "Acesse os
    processos de contratação do SENAI/SC" que leva a transparencia.fiesc.com.br
    — e lá existe /api/licitacoes/, JSON paginado, com objeto por extenso, data
    de abertura e status. `status=A` são os em andamento.

    Medido em 06/09/2026: 32 processos em andamento no Sistema FIESC inteiro.

    Os dois enganos (este e o do SESI-SP) têm a mesma forma: uma fonte foi
    julgada pela primeira página que respondeu. Por isso a sonda registra o
    motivo por escrito — para que dê para reler o motivo e descobrir que ele
    era fraco.
    """
    nome = "Sistema FIESC (SESI/SENAI/IEL-SC)"
    hoje = datetime.now(TZ).date()
    itens, url, paginas = [], FIESC_API, 0
    while url and paginas < 12:
        st, corpo = pega(url, timeout=60, extra=AJAX)
        if st != 200:
            if itens:
                break          # o que já veio vale; a falha fica no registro
            return {"id": "fiesc", "nome": nome, "abriu": False, "itens": [],
                    "erro": f"HTTP {st}"}
        try:
            pagina = json.loads(corpo)
        except json.JSONDecodeError as e:
            return {"id": "fiesc", "nome": nome, "abriu": False, "itens": [],
                    "erro": f"JSON inválido: {e}"}
        for x in pagina.get("results") or []:
            abertura = (x.get("data_abertura") or "")[:10]
            if not abertura or abertura < hoje.isoformat():
                continue
            empresas = ", ".join(e.get("nome") or "" for e in (x.get("empresas") or []))
            itens.append({
                "id": f"fiesc:{x.get('id')}",
                "fonte": "FIESC/SC",
                "orgao": empresas or "Sistema FIESC",
                "uf": "SC",
                "modalidade": x.get("modalidade"),
                "objeto": " ".join((x.get("objeto") or "").split()),
                "numero": str(x.get("numero") or x.get("titulo") or ""),
                "valor": 0,
                "sigiloso": True,
                "encerramento": abertura,
                "publicado_em": None,
                "situacao": x.get("status"),
                "link": "https://transparencia.fiesc.com.br/",
            })
        url, paginas = pagina.get("next"), paginas + 1
    return {"id": "fiesc", "nome": nome, "abriu": True, "erro": None, "itens": itens}


# Os portais que NÃO rendem item, e o motivo medido em 06/09/2026. Continuam
# sendo sondados toda noite de propósito, por dois motivos: um portal que hoje
# devolve 403 pode responder amanhã, e o registro de falhas é o que faz alguém
# perceber que uma fonte morreu — abandonar em silêncio é como perder cliente
# por não ligar. A sonda é barata: uma requisição por fonte.
SONDAS = (
    ("senac-dn", "Senac — Departamento Nacional",
     "https://www.senac.br/transparencia/licitacoes.aspx",
     "403 do próprio sistema de proteção do Senac ('Acesso Bloqueado — "
     "sua solicitação foi bloqueada pelas políticas de segurança'), e não do "
     "Cloudflare; o conjunto completo de cabeçalhos de navegador não abre"),
    ("cni", "Sistema Indústria — CNI",
     "https://www.portaldaindustria.com.br/cni/canais/licitacoes/",
     "502 do proxy de saída e tempo esgotado, alternando; nunca respondeu"),
    ("bec-sp", "BEC/SP", "https://www.bec.sp.gov.br/",
     "a consulta de pregões exige sessão ASP.NET ('falha de comunicação com o "
     "sistema / sessão expirou'); e o Estado de São Paulo publica no PNCP, "
     "então a camada 1 já cobre o que sairia daqui"),
)


def sonda(id_: str, nome: str, url: str, nota: str) -> dict:
    """Bate na porta e registra o que aconteceu. Não extrai nada."""
    st, corpo = pega(url, timeout=40)
    abriu = st == 200 and len(corpo) > 2000
    return {"id": id_, "nome": nome, "abriu": abriu, "itens": [],
            "erro": None if abriu else f"HTTP {st}" if st else "sem resposta",
            "nota": nota}


FONTES = ((sebrae, sesc_dn, senac_es, fiesc)
          + tuple((lambda i=i, e=e, h=h: _sp(i, e, h)) for i, e, h in SP_HOSTS)
          ) + tuple(
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
