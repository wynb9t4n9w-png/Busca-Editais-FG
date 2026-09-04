#!/usr/bin/env python3
"""
A situação real de uma contratação, item a item.

A primeira versão do radar deduzia se ainda dava para disputar a partir da
AUSÊNCIA de janela de proposta. Funcionava para o caso que a motivou — um
contrato de R$ 1,5 mi que o CRECI/SC já havia assinado com a UFSC —, mas era
inferência, e inferência erra nas bordas: um Pregão publicado sem prazo
declarado ficava em "indeterminado", que é um jeito educado de dizer "não sei".

O PNCP responde essa pergunta diretamente, e a resposta é melhor que a dedução.
Cada item de cada contratação carrega `situacaoCompraItemNome` e `temResultado`,
e `/itens/{n}/resultados` devolve o fornecedor vencedor com o valor homologado.
Conferido em 03/09/2026 contra os três casos: um edital em disputa devolveu "Em
andamento" com temResultado false; um com prazo vencido e o contrato do CRECI/SC
devolveram "Homologado" com temResultado true.

Duas situações que a dedução não enxergava de jeito nenhum e que interessam
muito: DESERTO (ninguém apareceu) e FRACASSADO (apareceram e foram
desclassificados). Nos dois casos o órgão quer o serviço, não conseguiu comprar,
e costuma relicitar — é a melhor hora de aparecer, e o radar antigo mostrava
isso como um edital qualquer com prazo vencido.

Uso:
    python3 tools/situacao.py <cnpj> <ano> <sequencial>
    python3 tools/situacao.py --do-estado <estado.html|.json>
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from contratos import procura as procura_contrato  # noqa: E402
from perfil import normaliza  # noqa: E402

BASE = "https://pncp.gov.br/api/pncp/v1/orgaos"
PAUSA_429, PAUSA_ENTRE = 12.0, 1.2

# Modalidades em que a lei declara a competição INVIÁVEL. Não é uma disputa que
# terminou; é uma que nunca existiu, porque o fornecedor é singular por premissa
# (Lei 14.133, art. 74). O status do item é irrelevante aqui.
INEXIGIVEL = ("inexigibilidade", "inexigivel", "inaplicabilidade")

# Títulos e tipos de documento que denunciam um desfecho já assinado. O status do
# item é escrituração administrativa, e órgão atualiza tarde: no processo de
# R$ 30,5 milhões da SEDUC-PA o item dizia "Em andamento" com temResultado=False
# enquanto o anexo se chamava "Contrato_n__046.2026_-_FGV.pdf". O papel sabia
# antes do campo.
FECHOU = ("contrato", "termo de contrato", "extrato de contrato", "ratificac",
          "homologac", "adjudicac", "termo de adjudicacao", "ordem de servico",
          "empenho", "ata de registro")

# situacaoCompraItem, conforme o PNCP devolve.
SITUACOES = {
    "em andamento": "em_disputa",
    "homologado": "homologado",
    "anulado": "cancelado",
    "revogado": "cancelado",
    "cancelado": "cancelado",
    "deserto": "deserto",
    "fracassado": "fracassado",
}

# Como cada situação de item vira o campo `disputa` do radar. A ordem importa:
# uma contratação com vários itens fica com o veredito mais "resolvido" entre
# eles, porque basta um item homologado para não haver mais o que disputar ali.
PRIORIDADE = ["homologado", "cancelado", "fracassado", "deserto", "em_disputa"]
PARA_DISPUTA = {
    "inexigivel": "inexigivel",
    "em_disputa": "aberto",
    "homologado": "decidido",
    "cancelado": "cancelado",
    # Deserto e fracassado NÃO são becos sem saída: o órgão quis comprar e não
    # conseguiu. Costuma voltar, e quem já leu o edital chega na frente.
    "deserto": "relicita",
    "fracassado": "relicita",
}


def get(caminho: str) -> tuple[int, object]:
    url = "https://pncp.gov.br" + caminho
    for t in range(4):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                corpo = r.read()
            return r.status, (json.loads(corpo) if corpo.strip() else None)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                return e.code, None
            time.sleep(PAUSA_429 * (t + 1))
        except Exception:
            if t == 3:
                return 0, None
            time.sleep(4 * (t + 1))
    return 429, None


def partes(edital: dict) -> tuple[str, str, str] | None:
    """Extrai cnpj, ano e sequencial do id 'pncp:<cnpj>-1-<seq>/<ano>'."""
    cnpj = edital.get("cnpj")
    m = re.search(r"-(\d+)-(\d+)-(\d{4})$", edital.get("id", ""))
    if not (cnpj and m):
        return None
    return cnpj, m.group(3), m.group(2).lstrip("0") or "0"


def documentos(cnpj: str, ano: str, seq: str) -> tuple[list[str], str | None]:
    """
    Os anexos do processo, e o primeiro que indique desfecho.

    Uma chamada barata que responde o que o status do item às vezes esconde:
    contrato assinado, ratificação, homologação. Devolve (títulos, achado).
    """
    st, arqs = get(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos")
    if st != 200 or not isinstance(arqs, list):
        return [], None
    titulos = []
    achado = None
    for a in arqs:
        rotulo = f"{a.get('tipoDocumentoNome') or ''} {a.get('titulo') or ''}".strip()
        titulos.append(rotulo)
        if achado is None:
            alvo = normaliza(rotulo)
            if any(p in alvo for p in FECHOU):
                achado = rotulo
    return titulos, achado


def confere(cnpj: str, ano: str, seq: str, modalidade: str | None = None) -> dict:
    """A situação de uma contratação, direto da fonte."""
    # A modalidade decide antes de qualquer status: inexigibilidade não é uma
    # disputa em andamento, é uma disputa que a lei declarou inviável.
    if modalidade and any(x in normaliza(modalidade) for x in INEXIGIVEL):
        r = {"situacao": "inexigivel", "disputa": "inexigivel", "itens": 0,
             "motivo": "Lei 14.133 art. 74: competição inviável, fornecedor singular"}
        titulos, fechou = documentos(cnpj, ano, seq)
        if fechou:
            r["documento_fecho"] = fechou
        _vencedor_do_item(cnpj, ano, seq, r)
        return r

    st, itens = get(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens")
    if st != 200 or not isinstance(itens, list) or not itens:
        # Sem itens publicados não há como responder pela via autoritativa.
        # Resta a via indireta: existe contrato assinado com este objeto?
        return {"situacao": "desconhecida", "itens": 0,
                "motivo": f"itens não publicados ou indisponíveis (HTTP {st})"}

    estados = []
    for it in itens:
        nome = (it.get("situacaoCompraItemNome") or "").strip().lower()
        estados.append(next((v for k, v in SITUACOES.items() if k in nome), "desconhecida"))

    situacao = next((p for p in PRIORIDADE if p in estados), "desconhecida")
    r = {"situacao": situacao, "itens": len(itens),
         "disputa": PARA_DISPUTA.get(situacao, "indeterminado"),
         "por_item": estados}

    if situacao == "em_disputa":
        # O status do item diz "Em andamento", mas isso é escrituração. Se o
        # processo já tem contrato ou ratificação anexada, a disputa acabou e
        # ninguém atualizou o campo. Foi assim que um processo de R$ 30,5 mi
        # apareceu como oportunidade com o contrato da FGV no anexo.
        time.sleep(PAUSA_ENTRE)
        titulos, fechou = documentos(cnpj, ano, seq)
        if fechou:
            r["situacao"] = "homologado"
            r["disputa"] = "decidido"
            r["documento_fecho"] = fechou
            r["motivo"] = ("item ainda em andamento, mas o processo já tem "
                           f"documento de fecho anexado: {fechou}")
            _vencedor_do_item(cnpj, ano, seq, r)
        return r

    if situacao != "homologado":
        return r

    _vencedor_do_item(cnpj, ano, seq, r)
    return r


def _vencedor_do_item(cnpj: str, ano: str, seq: str, r: dict) -> None:
    """Quem ganhou, quando o resultado do item já foi publicado."""
    st, itens = get(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens")
    if st != 200 or not isinstance(itens, list):
        return
    for it in itens:
        if not it.get("temResultado"):
            continue
        time.sleep(PAUSA_ENTRE)
        st, res = get(f"/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}"
                      f"/itens/{it['numeroItem']}/resultados")
        if st == 200 and isinstance(res, list) and res:
            v = res[0]
            r["vencedor"] = {
                "fornecedor": v.get("nomeRazaoSocialFornecedor"),
                "cnpj_fornecedor": v.get("niFornecedor"),
                "valor": v.get("valorTotalHomologado"),
                "porte": v.get("porteFornecedorNome"),
                "origem": "resultado do item",
            }
            return


def confere_edital(e: dict) -> dict:
    """A situação de um edital do radar, com a via indireta como reserva."""
    p = partes(e)
    if not p:
        return {"situacao": "desconhecida", "motivo": "id fora do formato esperado"}
    r = confere(*p, modalidade=e.get("modalidade"))
    if r["situacao"] != "desconhecida":
        return r

    # Reserva: o órgão não publicou itens, mas pode ter publicado o contrato.
    c = procura_contrato(e.get("cnpj"), e.get("publicado_em"), e.get("objeto"))
    if c.get("achou"):
        return {"situacao": "homologado", "disputa": "decidido", "itens": 0,
                "vencedor": {"fornecedor": c["fornecedor"],
                             "cnpj_fornecedor": c.get("cnpj_fornecedor"),
                             "valor": c.get("valor"),
                             "assinado_em": c.get("assinado_em"),
                             "origem": "contrato assinado"},
                "motivo": "itens não publicados; encontrado pelo contrato"}
    return r


def confere_mercado(e: dict) -> dict:
    """
    Quem foi contratado numa inexigibilidade — a única pergunta que ela responde.

    Aqui a modalidade é OMITIDA de propósito. `confere` a usa para responder
    "ainda dá para disputar?" e, sendo inexigibilidade, devolve "inexigivel" sem
    abrir item nenhum — o atalho certo para o radar. Só que a aba Mercado não
    pergunta isso: ela já sabe que não houve disputa. Pergunta de quem, e por
    quanto. Sem esta passagem a coluna "Contratado" ficava em "não publicado"
    para sempre, e uma aba sobre quem contrata sem licitar sem o nome de quem
    contratou é meia aba.
    """
    p = partes(e)
    if not p:
        return {}
    r = confere(*p)              # sem `modalidade`: não queremos o atalho
    saida = {}
    if r.get("vencedor"):
        saida["vencedor"] = r["vencedor"]
    if r.get("documento_fecho"):
        saida["documento_fecho"] = r["documento_fecho"]
    if saida:
        return saida

    # Nada pelo item — e é justamente o que acontece com as maiores. Numa
    # inexigibilidade o órgão frequentemente não publica item nenhum: o
    # processo é a justificativa da escolha, não uma disputa a apurar. Sobra o
    # anexo, e ele costuma bastar: o processo de R$ 30,5 mi da SEDUC-PA não tem
    # um item sequer, e traz "Contrato_n__046.2026_-_FGV.pdf" pendurado.
    time.sleep(PAUSA_ENTRE)
    _, fechou = documentos(*p)
    if fechou:
        saida["documento_fecho"] = fechou
    return saida


def do_mercado(mercado: list[dict]) -> None:
    if not mercado:
        return
    print(f"\n=== quem foi contratado nas {len(mercado)} inexigibilidades ===\n",
          flush=True)
    achados = 0
    for i, e in enumerate(mercado, 1):
        r = confere_mercado(e)
        e.update(r)
        nome = (e.get("vencedor") or {}).get("fornecedor")
        if nome:
            achados += 1
        print(f"  [{i:2d}/{len(mercado)}] {e['orgao'][:36]:36} "
              f"{nome[:44] if nome else '— sem resultado publicado'}", flush=True)
        if e.get("documento_fecho") and not nome:
            print(f"                  anexo: {e['documento_fecho'][:56]}", flush=True)
        time.sleep(PAUSA_ENTRE)
    print(f"\n{achados} de {len(mercado)} com fornecedor identificado.")


def carrega(caminho: Path) -> dict:
    txt = caminho.read_text(encoding="utf8")
    if caminho.suffix.lower() == ".json":
        return json.loads(txt)
    m = re.search(r"/\*DADOS\*/(.*?)/\*FIM\*/", txt, re.S)
    if not m:
        raise SystemExit(f"FALHA: bloco /*DADOS*/ não encontrado em {caminho}")
    return json.loads(m.group(1))


def do_estado(estado: dict) -> None:
    # Cada linha sai na hora: o script leva minutos sobre um radar cheio, e sem
    # isso ele parece travado quando a saída é redirecionada — quem espera acaba
    # matando um processo que estava indo bem.
    editais = estado.get("editais") or []
    print(f"=== conferindo {len(editais)} editais na fonte ===\n", flush=True)
    resumo: dict[str, int] = {}
    mudou = 0
    for i, e in enumerate(editais, 1):
        r = confere_edital(e)
        nova = r.get("disputa", "indeterminado")
        antes = e.get("disputa", "?")
        resumo[nova] = resumo.get(nova, 0) + 1
        marca = " " if nova == antes else "~"
        if nova != antes:
            mudou += 1
        venc = r.get("vencedor", {}).get("fornecedor")
        print(f"{marca} [{i:2d}/{len(editais)}] {antes:>13s} → {nova:<13s} {e['orgao'][:36]}",
              flush=True)
        if venc:
            print(f"                  contratado: {venc[:56]}", flush=True)
        if r["situacao"] == "desconhecida":
            print(f"                  {r.get('motivo', '')}", flush=True)
        time.sleep(PAUSA_ENTRE)
    print(f"\n{dict(sorted(resumo.items()))}")
    print(f"{mudou} classificaç{'ões mudaram' if mudou != 1 else 'ão mudou'} "
          "em relação à dedução da coleta.")
    do_mercado(estado.get("mercado") or [])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--do-estado", metavar="ARQUIVO")
    ap.add_argument("resto", nargs="*", help="cnpj ano sequencial [modalidade]")
    a = ap.parse_args()
    if a.do_estado:
        do_estado(carrega(Path(a.do_estado)))
        return
    if len(a.resto) not in (3, 4):
        raise SystemExit(__doc__)
    print(json.dumps(confere(*a.resto), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
