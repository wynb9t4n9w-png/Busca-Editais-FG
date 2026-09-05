#!/usr/bin/env python3
"""
O que o radar aprendeu, e o que ele deveria passar a procurar.

A Pauta Thutor tem um dossiê de fontes que melhora sozinho: ele olha quais
veículos de fato renderam notícia de quais clientes e transforma isso numa
camada de busca dirigida por evidência, em vez de suposição. A lista fixa do
prompt envelhece; o dossiê não, porque é derivado do histórico a cada execução.

Aqui a mesma ideia tem material melhor. A coleta é determinística e o histórico
guarda, de cada edital, o veredito e o desfecho — então dá para perguntar coisas
que lá não dá: quais órgãos voltam a comprar o que a Thutor vende, quais
palavras apareceram nos editais que interessaram e ainda não estão no léxico,
qual ruído se repete a ponto de merecer veto, e quem está ganhando.

Nada aqui é aplicado automaticamente. O script PROPÕE, com o número que sustenta
cada proposta, e quem edita tools/perfil.py é uma pessoa — um filtro que se
reescreve sozinho é um filtro que ninguém consegue auditar depois.

Uso:
    python3 tools/aprende.py <estado.html|estado.json>
    python3 tools/aprende.py <estado> --min 3
"""

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from perfil import APOIO, CONTEXTO, NUCLEO, VETOS, normaliza  # noqa: E402

INTERESSA = {"quente", "morno"}

# Palavras que aparecem em qualquer objeto de licitação e não distinguem nada.
RUIDO = {
    "contratacao", "contratar", "empresa", "servico", "servicos", "prestacao",
    "especializada", "especializado", "para", "com", "dos", "das", "que", "por",
    "meio", "objeto", "deste", "desta", "conforme", "termo", "referencia",
    "pessoa", "juridica", "fornecimento", "visando", "atender", "necessidades",
    "municipio", "municipal", "secretaria", "futura", "eventual", "presente",
    "seus", "suas", "sera", "serao", "sendo", "demais", "conforme", "anexo",
    "edital", "processo", "licitacao", "publico", "publica", "administracao",
    "realizacao", "execucao", "aquisicao", "compra", "itens", "item", "lote",
    "valor", "prazo", "condicoes", "acordo", "forma", "todos", "toda", "pelo",
    "pela", "nos", "nas", "aos", "seu", "sua", "ate", "ser", "tem", "quando",
    "onde", "como", "mais", "menos", "outros", "outras", "entre", "sobre",
}


def carrega(caminho: Path) -> dict:
    txt = caminho.read_text(encoding="utf8")
    if caminho.suffix.lower() == ".json":
        return json.loads(txt)
    m = re.search(r"/\*DADOS\*/(.*?)/\*FIM\*/", txt, re.S)
    if not m:
        raise SystemExit(f"FALHA: bloco /*DADOS*/ não encontrado em {caminho}")
    return json.loads(m.group(1))


def termos_conhecidos() -> set[str]:
    """Tudo que perfil.py já procura, para não propor o que já existe."""
    vistos = set(CONTEXTO)
    for d in (NUCLEO, APOIO):
        for lista in d.values():
            vistos.update(lista)
    # Palavras soltas dentro de termos compostos também contam como conhecidas.
    soltas = set()
    for t in vistos:
        soltas.update(t.split())
    return vistos | soltas


def palavras(texto: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]{5,}", normaliza(texto)) if w not in RUIDO}


def lift(dentro: int, n_dentro: int, fora: int, n_fora: int) -> float:
    """
    Quantas vezes a palavra é mais frequente entre o que interessa do que entre
    o resto. Frequência crua elegeria "servicos"; a razão elege o que discrimina.
    Suavizado para não explodir com contagem baixa.
    """
    p = (dentro + 0.5) / (n_dentro + 1)
    q = (fora + 0.5) / (n_fora + 1)
    return p / q


def relatorio(estado: dict, minimo: int) -> None:
    # A memória, não o radar. O radar guarda só o que ainda dá para disputar, e
    # aprender só com ele seria comparar os últimos três dias contra os últimos
    # três dias para sempre — um órgão que comprou em agosto e volta em novembro
    # jamais apareceria como recorrente, que é a prospecção mais valiosa daqui.
    editais = estado.get("memoria") or estado.get("editais") or []
    rodadas = estado.get("rodadas") or []
    if not editais:
        print("Nenhum edital no radar ainda. Volte depois de algumas rodadas.")
        return

    print(f"=== O QUE O RADAR APRENDEU ===")
    print(f"Base: {len(editais)} editais em {len(rodadas)} rodada(s).")
    if len(rodadas) < 5:
        print("ATENÇÃO: poucas rodadas. Tudo abaixo é indício, não conclusão —")
        print("uma palavra que apareceu duas vezes em três dias não aprendeu nada.")
    print()

    bons = [e for e in editais if e.get("veredito") in INTERESSA]
    ruins = [e for e in editais if e.get("veredito") == "frio"]

    # --- 1. órgãos que voltam ---------------------------------------------
    print("--- ÓRGÃOS QUE COMPRAM O QUE A THUTOR VENDE ---")
    print("Quem aparece mais de uma vez comprou o tema mais de uma vez. É lista")
    print("de prospecção direta, não de espera pelo próximo edital.")
    orgaos = Counter((e.get("orgao"), e.get("uf")) for e in bons if e.get("orgao"))
    recorrentes = [(o, n) for o, n in orgaos.most_common() if n >= 2]
    if recorrentes:
        for (nome, uf), n in recorrentes:
            print(f"  {n}x  {nome[:56]} · {uf}")
    else:
        print(f"  nenhum órgão ainda apareceu duas vezes ({len(orgaos)} distintos).")
    print()

    # --- 2. vocabulário que o filtro não conhece ---------------------------
    print("--- VOCABULÁRIO QUE tools/perfil.py AINDA NÃO PROCURA ---")
    print("Palavras que discriminam o que interessou do que não interessou.")
    print("Candidatas a entrar em APOIO; as muito específicas, em NUCLEO.")
    conhecidos = termos_conhecidos()
    dentro, fora = Counter(), Counter()
    for e in bons:
        dentro.update(palavras(e.get("objeto")))
    for e in ruins:
        fora.update(palavras(e.get("objeto")))
    candidatas = []
    for w, n in dentro.items():
        if n < minimo or w in conhecidos:
            continue
        candidatas.append((lift(n, len(bons), fora.get(w, 0), len(ruins)), n, w))
    candidatas.sort(reverse=True)
    if candidatas:
        for l, n, w in candidatas[:14]:
            print(f"  {w:28s} {n}x nos que interessaram, {fora.get(w, 0)}x nos frios "
                  f"(discrimina {l:.1f}x)")
    else:
        print(f"  nada acima de {minimo} ocorrências que o léxico já não cubra.")
    print()

    # --- 3. ruído recorrente ------------------------------------------------
    print("--- RUÍDO QUE SE REPETE (candidatos a veto) ---")
    print("Palavras frequentes só entre os frios. Antes de vetar, confira que a")
    print("palavra não aparece em nenhum edital bom: veto errado some em silêncio.")
    ja_vetado = " ".join(VETOS)
    sujeira = []
    for w, n in fora.items():
        if n < max(minimo, 3) or w in dentro or w in ja_vetado:
            continue
        sujeira.append((n, w))
    sujeira.sort(reverse=True)
    if sujeira:
        for n, w in sujeira[:12]:
            print(f"  {w:28s} {n}x — e nunca num edital que interessou")
    else:
        print("  nada recorrente o bastante ainda.")
    print()

    # --- 4. quem ganha ------------------------------------------------------
    print("--- QUEM ESTÁ GANHANDO ---")
    venc = defaultdict(lambda: [0, 0.0])
    for e in editais:
        v = e.get("vencedor") or {}
        if v.get("fornecedor"):
            venc[v["fornecedor"]][0] += 1
            venc[v["fornecedor"]][1] += v.get("valor") or 0
    if venc:
        for nome, (n, total) in sorted(venc.items(), key=lambda x: -x[1][1])[:12]:
            print(f"  R$ {total:>13,.0f}  {n}x  {nome[:52]}")
        fundacoes = sum(n for nome, (n, _) in venc.items()
                        if re.search(r"funda|universidade|instituto|servico nacional",
                                     normaliza(nome)))
        if fundacoes:
            print(f"\n  {fundacoes} de {sum(n for n, _ in venc.values())} contratos foram para")
            print("  fundação, universidade ou entidade do Sistema S. Se isso se")
            print("  confirmar ao longo das semanas, é uma característica do mercado")
            print("  — e uma decisão de posicionamento, não um detalhe.")
    else:
        print("  nenhum vencedor identificado ainda. Rode tools/situacao.py.")
    print()

    # --- 5. de onde vêm -----------------------------------------------------
    print("--- DE ONDE VÊM OS EDITAIS QUE INTERESSAM ---")
    esferas = Counter(e.get("esfera") for e in bons if e.get("esfera"))
    ufs = Counter(e.get("uf") for e in bons if e.get("uf"))
    mods = Counter(e.get("modalidade") for e in bons if e.get("modalidade"))
    nomes = {"F": "federal", "E": "estadual", "M": "municipal"}
    if esferas:
        print("  esfera:     " + ", ".join(f"{nomes.get(k, k)} {v}" for k, v in esferas.most_common()))
    if ufs:
        print("  UF:         " + ", ".join(f"{k} {v}" for k, v in ufs.most_common(8)))
    if mods:
        print("  modalidade: " + ", ".join(f"{k} {v}" for k, v in mods.most_common(5)))
    fontes = Counter(e.get("fonte") for e in bons if e.get("fonte"))
    print("  fonte:      " + ", ".join(f"{k} {v}" for k, v in fontes.most_common()))
    externos = sum(v for k, v in fontes.items() if (k or "").upper() != "PNCP")
    if externos == 0 and len(rodadas) >= 3:
        print()
        print("  Nenhum edital veio da camada 2 em várias rodadas. Ou o Sistema S")
        print("  não está publicando o nosso tema, ou a leitura dos portais não")
        print("  está funcionando. Rode tools/camada2.py e leia as falhas")
        print("  antes de concluir a primeira hipótese.")
    print()

    # --- 6. o que fazer com isto -------------------------------------------
    print("--- O QUE FAZER COM ISTO ---")
    print("  1. Léxico: leve as palavras da seção 2 para tools/perfil.py, e")
    print("     acrescente um caso de ouro em tools/teste_perfil.py com um objeto")
    print("     real que a mudança passa a capturar. Termo sem teste regride sem aviso.")
    print("  2. Vetos: os da seção 3 vão para VETOS — sempre delimitados por \\b se")
    print("     tiverem menos de sete letras. Um 'opera' sem \\b já derrubou o melhor")
    print("     edital de um dia inteiro.")
    print("  3. Órgãos recorrentes: viram prospecção ativa, não espera.")
    print("  4. Rode a suíte. Se um caso de ouro quebrar, a mudança está errada —")
    print("     não o teste.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("estado")
    ap.add_argument("--min", type=int, default=2,
                    help="ocorrências mínimas para uma palavra ser proposta (padrão 2)")
    a = ap.parse_args()
    relatorio(carrega(Path(a.estado)), a.min)


if __name__ == "__main__":
    main()
