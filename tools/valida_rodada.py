#!/usr/bin/env python3
"""
O portão. Confere se a rodada do dia realmente aconteceu, antes de publicar.

Este arquivo existe por causa de um incidente na Pauta Thutor, o projeto irmão:
em 29/08/2026 o disparo automático terminou em 56 segundos, não pesquisou nada,
não publicou nada — e foi registrado como SUCCEEDED. O jornal seguiu mostrando
a notícia da véspera e ninguém percebeu, porque uma execução que falha em
silêncio é indistinguível de uma que deu certo.

Aqui o portão pode ser bem mais rigoroso do que lá, e a razão é a arquitetura:
a coleta do PNCP é determinística, feita por script, e a própria API informa
quantos registros existem no período. Então não se pergunta "a coleta demorou o
bastante?" — pergunta-se "você viu tudo o que existia?". A conta fecha ou não
fecha.

Uso:
    python3 tools/valida_rodada.py <estado.html|estado.json>

Sai com código 1 e explica cada problema. Nunca edite este arquivo para fazer
uma rodada passar: o portão só vale enquanto ninguém o abaixa.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

VEREDITOS = {"quente", "morno", "frio"}

# Ainda dá para disputar? O radar não fazia essa pergunta, e por não fazer
# exibiu como "super oportunidade" um contrato de R$ 1,5 milhão que o CRECI/SC
# já havia assinado com a UFSC na véspera de o extrato aparecer no PNCP.
# Medido em 02/09/2026: 27 das 33 contratações aderentes do dia não tinham
# janela de proposta nenhuma. O erro não era raro — era a regra.
DISPUTA = {"aberto", "indeterminado", "decidido", "encerrado", "relicita",
           "cancelado", "inexigivel"}
# "relicita" (deserto ou fracassado) É disputável, e das melhores: o órgão quis
# comprar, não conseguiu, e costuma voltar. Quem já leu o edital chega na frente.
#
# "inexigivel" nunca é. Não é uma disputa que terminou — é uma que a lei declarou
# inviável (art. 74 da 14.133), com o fornecedor escolhido antes de o processo
# abrir. O radar chegou a exibir como oportunidade um processo de R$ 30,5 milhões
# da SEDUC-PA cujo próprio anexo se chamava "Contrato_046.2026_-_FGV.pdf", porque
# o status do item ainda dizia "Em andamento".
DISPUTAVEL = {"aberto", "indeterminado", "relicita"}

# O acompanhamento comercial — em que estágio está cada edital e as anotações da
# equipe — NÃO vive mais no estado. Ele vive no banco do artifact, sob regra de
# permissão do servidor. Antes o validador precisava vigiar esses campos para
# que a coleta não os sobrescrevesse; hoje a coleta não tem como alcançá-los,
# porque reescreve a página e não o banco. Uma instrução no prompt virou um fato
# da arquitetura, e é por isso que estas checagens sumiram em vez de afrouxar.
CAMPOS_PROIBIDOS = ("auth", "status", "nota")

# A API do PNCP informa totalRegistros por modalidade. Se colhemos menos do que
# ela prometeu, alguma página se perdeu — e cada página são 50 contratações que
# nunca chegaram ao radar. A tolerância é pequena de propósito.
TOLERANCIA_COLETA = 0.99
# Piso absoluto, usado SÓ quando não dá para conferir a completude pela própria
# fonte. Ele não é uma expectativa de volume: volume baixo é resultado legítimo
# em feriado, e 7 de setembro cai numa segunda.
PISO_CEGO = 40
# Uma rodada honesta lê o PNCP inteiro e ainda visita os portais externos.
DURACAO_MINIMA_S = 300
DURACAO_CONFORTAVEL_S = 900
MAX_RODADAS = 30

falhas: list[str] = []
avisos: list[str] = []


def falha(m: str) -> None:
    falhas.append(m)


def aviso(m: str) -> None:
    avisos.append(m)


def carrega(caminho: Path) -> dict:
    txt = caminho.read_text(encoding="utf8")
    if caminho.suffix.lower() == ".json":
        return json.loads(txt)
    m = re.search(r"/\*DADOS\*/(.*?)/\*FIM\*/", txt, re.S)
    if not m:
        print(f"FALHA: bloco /*DADOS*/ não encontrado em {caminho}")
        raise SystemExit(1)
    return json.loads(m.group(1))


def quando(v: str | None):
    if not v:
        return None
    try:
        d = datetime.fromisoformat(v)
    except ValueError:
        return None
    return d.replace(tzinfo=TZ) if d.tzinfo is None else d


def valida_pncp(p: dict, hoje) -> None:
    """
    A pergunta certa não é "veio bastante coisa?" — é "veio tudo o que havia?".

    A API do PNCP informa, por modalidade, quantos registros existem no período
    (totalRegistros), e a coleta soma isso em `esperados`. Com esse número a
    completude é verificável, e o volume deixa de ser sintoma de nada: 5.849
    contratações numa quarta e 180 num feriado são as duas corretas, desde que
    a conta feche.

    Isso é o oposto do que a Pauta Thutor consegue fazer. Lá o único sinal
    disponível é o relógio, então o portão pergunta se a coleta demorou o
    bastante — uma aproximação, que erra nos dois sentidos. Aqui a fonte diz
    quanto havia, e o portão confere.

    O piso absoluto sobrou para o único caso em que a verificação não existe:
    `esperados` ausente ou zerado, que é como uma API muda de resposta sem
    avisar.
    """
    if not isinstance(p, dict):
        falha("cobertura.pncp ausente. Sem ela não há prova de que a camada 1 rodou.")
        return

    brutos = p.get("brutos")
    esperados = p.get("esperados")
    if not isinstance(brutos, int):
        falha("cobertura.pncp.brutos ausente ou não é um número inteiro.")
        return

    if isinstance(esperados, int) and esperados > 0:
        if brutos < esperados * TOLERANCIA_COLETA:
            perdidos = esperados - brutos
            falha(
                f"a API prometeu {esperados:,} contratações e só {brutos:,} chegaram "
                f"— {perdidos:,} não foram vistas. Rode a coleta de novo: cada página "
                "perdida são até 50 oportunidades que nunca entraram no radar."
            )
        elif brutos < 1500 and hoje.weekday() < 5:
            # Não é falha: a conta fechou. É só digno de nota, porque um dia útil
            # magro costuma ser feriado — e, se não for, alguma coisa mudou na fonte.
            aviso(
                f"{brutos:,} contratações num dia útil, bem abaixo das ~5.800 "
                "habituais. A conta com a API fechou, então a varredura está "
                "completa: provavelmente é feriado. Se não for, desconfie da fonte."
            )
    else:
        # Sem `esperados` não há como provar completude — resta o piso cego.
        aviso("cobertura.pncp.esperados ausente ou zerado — sem ele não dá para "
              "provar que a varredura foi completa, só que ela trouxe alguma coisa.")
        if brutos < PISO_CEGO:
            falha(
                f"a camada 1 viu {brutos} contratações e não informou quantas "
                f"existiam. Abaixo de {PISO_CEGO} sem essa conta, o mais provável "
                "é que a API não tenha respondido — não que o Brasil tenha parado "
                "de licitar."
            )

    perdidas = p.get("paginas_perdidas")
    if isinstance(perdidas, int) and perdidas > 0:
        falha(f"{perdidas} página(s) do PNCP se perderam mesmo após a repescagem. "
              "Repita a coleta antes de publicar.")

    if p.get("modalidades_falhas"):
        falha("modalidades que falharam por inteiro: "
              f"{p['modalidades_falhas']}. A varredura está incompleta.")

    cand = p.get("candidatos")
    if not isinstance(cand, int):
        falha("cobertura.pncp.candidatos ausente.")
    elif cand == 0 and brutos > 2000:
        aviso(f"{brutos:,} contratações e nenhum candidato. É possível num dia "
              "fraco, mas confira se o filtro de tools/perfil.py não regrediu — "
              "a média observada é de algumas dezenas por dia.")


def valida_externas(e: dict) -> None:
    if not isinstance(e, dict):
        falha(
            "cobertura.externas ausente. A camada 2 (Sistema S, estatais e bancos) "
            "é obrigatória: é lá que estão os editais mais aderentes, e o PNCP "
            "não os alcança."
        )
        return
    tentadas = e.get("tentadas")
    if not isinstance(tentadas, int):
        falha("cobertura.externas.tentadas ausente ou não é inteiro.")
    elif tentadas < 8:
        falha(
            f"apenas {tentadas} fontes externas visitadas. O registro em "
            "tools/fontes_externas.py tem 15; visite todas, e anote as que não "
            "abriram em cobertura.externas.falhas em vez de pulá-las calado."
        )
    abertas = e.get("abertas")
    if isinstance(abertas, int) and isinstance(tentadas, int) and tentadas:
        if abertas == 0:
            falha("nenhuma fonte externa abriu. Ou a rede está bloqueada para o "
                  "ambiente, ou a camada 2 não rodou de verdade. Diga qual.")
        elif abertas < tentadas / 2:
            aviso(f"só {abertas} de {tentadas} fontes externas abriram. Portal de "
                  "licitação bloqueia robô com frequência; caia para WebSearch "
                  "nas que falharam.")


def valida_edital(e: dict, onde: str, ids: set[str], hoje) -> None:
    for campo in ("id", "fonte", "orgao", "objeto", "link"):
        if not (e.get(campo) or "").strip():
            falha(f"{onde}: campo '{campo}' vazio.")

    eid = e.get("id")
    if eid in ids:
        falha(f"{onde}: id '{eid}' duplicado no radar.")
    ids.add(eid)

    link = (e.get("link") or "").strip()
    if link and not link.startswith(("http://", "https://")):
        falha(f"{onde}: link inválido ('{link[:60]}').")

    # A prova de que a conferência na fonte aconteceu. Sem ela, o campo
    # `disputa` é só a dedução da coleta — que, medida em 03/09/2026, errou 3
    # das 17 classificações, e duas delas escondendo edital ainda disputável.
    if not (e.get("situacao_item") or "").strip():
        falha(f"{onde}: sem 'situacao_item'. A situação não foi conferida na "
              "fonte — rode tools/situacao.py antes de publicar.")

    if e.get("disputa") not in DISPUTA:
        falha(f"{onde}: disputa '{e.get('disputa')}' inválida (esperado um de "
              f"{sorted(DISPUTA)}). Sem esse campo o radar volta a tratar contrato "
              "assinado como oportunidade.")
    elif e.get("veredito") == "quente" and e["disputa"] not in DISPUTAVEL:
        falha(
            f"{onde}: veredito 'quente' num edital '{e['disputa']}'. Quente significa "
            "que a Thutor ainda pode disputar — e não dá para disputar contratação "
            "direta sem janela de proposta, nem prazo que já venceu. Rebaixe para "
            "morno e diga na justificativa que serve como referência de mercado."
            if e["disputa"] != "inexigivel" else
            f"{onde}: veredito 'quente' numa INEXIGIBILIDADE. O art. 74 da Lei "
            "14.133 só a autoriza quando a competição é inviável e o fornecedor é "
            "singular — não há disputa para entrar, com ou sem contrato assinado. "
            "Rebaixe para morno: vale como inteligência de mercado, e das boas."
        )

    if e.get("veredito") not in VEREDITOS:
        falha(f"{onde}: veredito '{e.get('veredito')}' inválido "
              f"(esperado um de {sorted(VEREDITOS)}). Todo edital no radar passou "
              "pela triagem — sem veredito, não passou.")

    for campo in CAMPOS_PROIBIDOS:
        if campo in e:
            falha(f"{onde}: campo '{campo}' não pertence ao estado — ele vive no "
                  "banco do artifact.")

    just = (e.get("justificativa") or "").strip()
    if e.get("veredito") in ("quente", "morno") and len(just) < 20:
        falha(f"{onde}: veredito '{e.get('veredito')}' sem justificativa. "
              "Quem abrir o radar precisa saber por que este edital está aqui.")

    v = e.get("valor")
    if v is not None and not isinstance(v, (int, float)):
        falha(f"{onde}: valor '{v}' não é numérico.")
    elif isinstance(v, (int, float)) and v < 0:
        falha(f"{onde}: valor negativo.")

    pub = e.get("publicado_em")
    if pub:
        try:
            d = datetime.fromisoformat(pub).date()
            if d > hoje:
                falha(f"{onde}: publicado_em {d} está no futuro.")
        except ValueError:
            falha(f"{onde}: publicado_em '{pub}' em formato inválido.")

    fim = quando(e.get("encerramento"))
    if fim and fim.date() < hoje - timedelta(days=180):
        aviso(f"{onde}: prazo encerrou em {fim.date()}, há mais de seis meses. "
              "A poda descrita em ROTINAS.md não está rodando.")


def valida(estado: dict) -> None:
    hoje = datetime.now(TZ).date()

    for campo in CAMPOS_PROIBIDOS:
        if campo in estado:
            falha(
                f"o estado voltou a carregar '{campo}'. Esse campo foi movido para o "
                "banco do artifact justamente para que a coleta não o alcançasse — "
                "escrevê-lo aqui de novo reabre o risco de apagar análise da equipe."
            )

    rodadas = estado.get("rodadas") or []
    if not rodadas:
        falha("nenhuma rodada registrada no estado.")
        return

    r = rodadas[0]
    if r.get("data") != hoje.isoformat():
        falha(f"a rodada na posição 0 é de {r.get('data')}, não de hoje "
              f"({hoje.isoformat()}). O radar mostraria a varredura anterior.")
    if len(rodadas) > 1 and rodadas[1].get("data") == r.get("data"):
        falha("há duas rodadas com a mesma data — a de hoje substitui, não duplica.")
    if len(rodadas) > MAX_RODADAS:
        aviso(f"{len(rodadas)} rodadas guardadas (máximo {MAX_RODADAS}). "
              "Descarte as mais antigas para o estado não crescer sem limite.")

    cob = r.get("cobertura")
    if not isinstance(cob, dict):
        falha("a rodada não tem bloco 'cobertura'. Sem ele não há prova de que a "
              "varredura aconteceu.")
    else:
        valida_pncp(cob.get("pncp"), hoje)
        valida_externas(cob.get("externas"))

        ini, fim = quando(cob.get("iniciado_em")), quando(cob.get("concluido_em"))
        if ini is None or fim is None:
            falha("cobertura.iniciado_em / concluido_em ausentes ou inválidos.")
        else:
            dur = (fim - ini).total_seconds()
            if dur < DURACAO_MINIMA_S:
                falha(
                    f"a rodada durou {dur:.0f}s. Só a varredura do PNCP leva de 4 a "
                    f"9 minutos medidos; abaixo de {DURACAO_MINIMA_S}s ela não "
                    "aconteceu. Foi assim que o incidente de 29/08/2026 passou."
                )
            elif dur < DURACAO_CONFORTAVEL_S:
                aviso(f"a rodada durou {dur/60:.1f} min. A coleta começa às 02:00 e "
                      "há a manhã inteira de folga — não há prêmio por terminar cedo.")

        pncp = cob.get("pncp") or {}
        ext = cob.get("externas") or {}
        cands = (pncp.get("candidatos") or 0) + (ext.get("candidatos") or 0)
        conferidos = cob.get("conferidos")
        if not isinstance(conferidos, int):
            falha("cobertura.conferidos ausente. Registre quantos editais tiveram a "
                  "situação conferida item a item em tools/situacao.py.")
        elif conferidos < len(estado.get("editais") or []):
            falha(
                f"{conferidos} editais conferidos na fonte, mas {len(estado.get('editais') or [])} "
                "estão no radar. A dedução da coleta erra nas bordas — em 03/09/2026 "
                "ela escondeu dois editais ainda disputáveis como se já tivessem dono."
            )

        triados = cob.get("triados")
        if not isinstance(triados, int):
            falha("cobertura.triados ausente. Registre quantos candidatos passaram "
                  "pela triagem.")
        elif triados < cands:
            falha(
                f"{cands} candidatos foram colhidos e só {triados} triados. "
                f"Os {cands - triados} restantes não foram nem lidos — e um deles "
                "pode ser o contrato do ano. Volte e termine a triagem."
            )

    # O histórico por fonte é o que faz a camada 2 melhorar sozinha: ele decide
    # a ordem de visita das rodadas seguintes. Some sem barulho se uma rodada
    # gravar o estado sem ele, e aí a camada volta a ser uma lista fixa.
    fontes = estado.get("fontes")
    if len(rodadas) > 1 and not fontes:
        aviso("o estado não tem 'fontes'. Sem esse acumulado, o plano da camada 2 "
              "volta a ser uma lista fixa, e a ordem de visita para de aprender.")
    elif isinstance(fontes, dict):
        sem_tentativa = [k for k, v in fontes.items()
                         if not isinstance(v, dict) or "tentativas" not in v]
        if sem_tentativa:
            falha(f"fontes sem contagem de tentativas: {sem_tentativa[:5]}. "
                  "Cada fonte precisa de tentativas, aberturas, editais e "
                  "falhas_seguidas para o plano poder ordenar.")

    editais = estado.get("editais")
    if editais is None:
        falha("a lista 'editais' sumiu do estado.")
        return

    ids: set[str] = set()
    for i, e in enumerate(editais):
        valida_edital(e, f"edital {i + 1} ({(e.get('id') or '?')[:40]})", ids, hoje)



def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)

    estado = carrega(Path(sys.argv[1]))
    valida(estado)

    for a in avisos:
        print(f"aviso: {a}")

    if falhas:
        print()
        print(f"FALHA: a rodada não passou na validação ({len(falhas)} problema(s)).")
        for f in falhas:
            print(f"  - {f}")
        print()
        print("Não publique. Corrija e rode de novo.")
        raise SystemExit(1)

    r = (estado.get("rodadas") or [{}])[0]
    cob = r.get("cobertura") or {}
    pncp = cob.get("pncp") or {}
    ext = cob.get("externas") or {}
    editais = estado.get("editais") or []
    quentes = sum(1 for e in editais if e.get("veredito") == "quente")
    decididos = sum(1 for e in editais if e.get("disputa") == "decidido")
    com_vencedor = sum(1 for e in editais if e.get("vencedor"))

    print(f"ok  rodada {r.get('data')} · {len(editais)} editais no radar "
          f"({quentes} quentes, {decididos} já contratados"
          + (f", {com_vencedor} com fornecedor identificado" if com_vencedor else "") + ")")
    print(f"    PNCP: {pncp.get('brutos', 0):,} de {pncp.get('esperados', 0):,} "
          f"contratações · {pncp.get('candidatos', 0)} candidatos")
    print(f"    externas: {ext.get('abertas', 0)}/{ext.get('tentadas', 0)} fontes "
          f"abertas · {ext.get('candidatos', 0)} candidatos")
    print(f"    triados {cob.get('triados', 0)} · conferidos na fonte "
          f"{cob.get('conferidos', 0)} · novos no radar {cob.get('novos', 0)}")
    if avisos:
        print(f"    {len(avisos)} aviso(s) acima, nenhum bloqueante.")


if __name__ == "__main__":
    main()
