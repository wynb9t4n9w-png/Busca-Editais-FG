#!/usr/bin/env python3
"""
Gera a versão pública do radar a partir da página do artifact.

O artifact é a fonte da verdade: é lá que o acompanhamento comercial é editado
e onde a senha vive. Esta versão pública é um espelho somente-leitura, servido
pelo GitHub Pages num endereço fixo.

O QUE SAI:

Um edital é informação pública por definição — publicá-lo não vaza nada. Mas o
que a Thutor está fazendo com ele, não. "Participando", ou uma nota dizendo quem
é o contato dentro do órgão, é o funil comercial da casa.

Desde a migração para o banco do artifact, esses campos já não estão no estado —
eles chegam ao artifact em tempo de execução, sob regra de permissão do servidor,
e o espelho público simplesmente não tem como alcançá-los (não há window.claude
no GitHub Pages). O sanitizador virou defesa em profundidade, não a única linha.

Ele continua removendo, por lista de permissão explícita, tudo que não seja
campo de radar, e a aba Acompanhamento, que sem banco não teria o que mostrar.
Fica o radar: quais editais existem, por que são aderentes, quanto valem e
quando fecham.

Uso:
    python3 tools/build_publico.py <artifact.html> [docs/index.html]
"""

import json
import re
import sys
from pathlib import Path

# Campos que a renderização pública realmente usa. Conferido em
# renderRadar/renderPrazos/renderArquivo/renderCobertura.
# Lista de PERMISSÃO, e ela já se pagou: quando os campos "disputa" e
# "vencedor" nasceram, o espelho os descartou por padrão — a página pública
# passou a contar zero contratações diretas e a exibir "sem prazo declarado" no
# lugar delas. O modo de falha certo. Uma lista de proibição teria publicado os
# dois calada, e o mesmo teria acontecido com o próximo campo sensível.
CAMPOS_PUBLICOS = (
    "id", "fonte", "orgao", "unidade", "uf", "municipio", "modalidade",
    "objeto", "valor", "sigiloso", "publicado_em", "abertura", "encerramento",
    "situacao", "link", "score", "frentes", "veredito", "justificativa",
    "visto_em",
    # Fatos públicos de contratação: quem contratou, por quanto, quando. Saem
    # do PNCP e voltar a escondê-los só empobreceria o espelho.
    "disputa", "vencedor", "situacao_item",
)


RESET = (
    "<meta charset=utf8>"
    '<meta name=viewport content="width=device-width,initial-scale=1">'
    "<style>:root{color-scheme:light}"
    "body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;"
    "background:#faf9f5;color:#141413}"
    "img{max-width:100%}"
    "[hidden]:not([hidden=until-found]){display:none!important}</style>"
)

DADOS_RE = re.compile(r"(/\*DADOS\*/)(.*?)(/\*FIM\*/)", re.S)
NAV_RE = re.compile(r'\["radar","prazos","arquivo","cobertura","acompanhamento"\]')
TAB_RE = re.compile(r"[ \t]*<button[^>]*id=\"tab-acompanhamento\"[^>]*>.*?</button>\s*\n?", re.S)
# O painel tem de sair junto com o botão. Sozinho ele é inerte — irPara() já
# não o abre — mas o aria-labelledby continua apontando para um id que deixou
# de existir, e um leitor de tela que procure esse rótulo não acha nada.
PAINEL_RE = re.compile(r"[ \t]*<section[^>]*id=\"p-acompanhamento\"[^>]*>.*?</section>\s*\n?", re.S)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)


def conteudo_autoral(html: str) -> str:
    """Descarta o wrapper injetado pelo host e devolve só o conteúdo da página."""
    marca = "<body>"
    i = html.find(marca)
    if i == -1:
        return html
    corpo = html[i + len(marca):]
    for fim in ("</body></html>", "</body>"):
        j = corpo.rfind(fim)
        if j != -1:
            corpo = corpo[:j]
            break
    return corpo.strip("\n")


def sanitiza(estado: dict) -> dict:
    # Lista de permissão, nunca de proibição: um campo novo e sensível que
    # alguém acrescente ao estado amanhã fica de fora por padrão, em vez de
    # vazar até alguém lembrar de proibi-lo.
    limpo = {k: v for k, v in estado.items() if k not in ("auth",)}
    limpo["editais"] = [
        {k: e[k] for k in CAMPOS_PUBLICOS if k in e}
        for e in estado.get("editais", [])
    ]
    return limpo


def serializa(estado: dict) -> str:
    txt = json.dumps(estado, ensure_ascii=False, separators=(",", ":"))
    return txt.replace("</script", "<\\/script")


def build(origem: Path, destino: Path) -> dict:
    html = origem.read_text(encoding="utf8")
    corpo = conteudo_autoral(html)

    m = DADOS_RE.search(corpo)
    if not m:
        raise SystemExit(f"FALHA: bloco /*DADOS*/ não encontrado em {origem}")

    estado = json.loads(m.group(2))
    limpo = sanitiza(estado)
    corpo = corpo[:m.start(2)] + serializa(limpo) + corpo[m.end(2):]

    corpo, n = TAB_RE.subn("", corpo)
    if n == 0:
        raise SystemExit("FALHA: aba 'Acompanhamento' não encontrada — o layout mudou, revise o script.")

    corpo, n = PAINEL_RE.subn("", corpo)
    if n == 0:
        raise SystemExit(
            "FALHA: o painel 'p-acompanhamento' não foi encontrado. Sem removê-lo, "
            "o espelho fica com um aria-labelledby apontando para um botão que já "
            "não existe — revise o script."
        )

    corpo, n = NAV_RE.subn('["radar","prazos","arquivo","cobertura"]', corpo)
    if n == 0:
        raise SystemExit(
            "FALHA: a lista de abas de irPara() não foi encontrada. Sem esse ajuste, "
            "el(\"tab-acompanhamento\") vira null e todas as outras abas abrem "
            "vazias — foi um erro real da Pauta Thutor. Revise o script."
        )

    titulo = TITLE_RE.search(corpo)
    titulo = titulo.group(1).strip() if titulo else "Busca Editais FG"

    pagina = (
        "<!doctype html>\n"
        '<html lang="pt-BR">\n<head>\n'
        f"{RESET}\n"
        '<meta name="robots" content="noindex,nofollow">\n'
        '<meta name="description" content="Radar diario de editais de licitacao aderentes ao portfolio da Thutor.">\n'
        f'<meta property="og:title" content="{titulo}">\n'
        "</head>\n<body>\n"
        f"{corpo}\n"
        "</body>\n</html>\n"
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(pagina, encoding="utf8")

    editais = limpo.get("editais", [])
    rodadas = limpo.get("rodadas", [])
    return {
        "destino": str(destino),
        "bytes": len(pagina.encode("utf8")),
        "editais": len(editais),
        "quentes": sum(1 for e in editais if e.get("veredito") == "quente"),
        "rodadas": len(rodadas),
        "ultima": rodadas[0].get("data") if rodadas else None,
        "atualizado_em": limpo.get("atualizado_em"),
    }


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    origem = Path(sys.argv[1])
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/index.html")
    i = build(origem, destino)
    print(f"ok  {i['destino']}  ({i['bytes']:,} bytes)")
    print(f"    rodada {i['ultima']} · {i['editais']} editais ({i['quentes']} quentes)")
    print(f"    {i['rodadas']} rodadas no histórico · atualizado_em {i['atualizado_em']}")


if __name__ == "__main__":
    main()
