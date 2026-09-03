#!/usr/bin/env python3
"""
Testa a página pública num navegador de verdade, e confere o que ela não leva.

São dois testes num arquivo só, porque são as duas maneiras de a publicação dar
errado sem ninguém perceber.

A primeira é funcional, e vem de um erro real da Pauta Thutor: ao remover a aba
administrativa, a função irPara() continuou percorrendo a lista antiga de abas
e chamando el("tab-acompanhamento").setAttribute(...). Sem aquele botão o el()
devolve null, a função estoura no meio, e as outras abas abrem — porém vazias.
Um teste que só olhasse a primeira aba não pegaria isso. Este clica em todas.

A segunda é de vazamento, e é específica deste projeto: o repositório é
público, e um edital é informação pública, mas o estágio comercial de cada
edital e as anotações da equipe não são. Se tools/build_publico.py deixar
"status" ou "nota" passarem, o concorrente lê o funil da Thutor de graça — e
nada na tela denuncia isso, porque a aba que mostraria esses campos foi
removida. Só olhando o JSON embutido dá para saber.

Uso:
    python3 tools/teste_pagina.py [docs/index.html]
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ABAS = ("radar", "prazos", "arquivo", "cobertura")
CONTEUDO_MINIMO = 200  # bytes de innerHTML; painel vazio fica perto de zero

# Campos que NÃO podem chegar à página pública.
PROIBIDOS_ESTADO = ("auth",)
PROIBIDOS_EDITAL = ("status", "nota")

SONDA = """
<script>
window.__erros = [];
window.addEventListener("error", function(e){ window.__erros.push(String(e.message)); });
window.addEventListener("load", function(){
  setTimeout(function(){
    var linhas = [];
    ["radar","prazos","arquivo","cobertura"].forEach(function(k){
      var b = document.getElementById("tab-" + k);
      if (b) { try { b.click(); } catch (e) { window.__erros.push("click " + k + ": " + e.message); } }
      var p = document.getElementById("p-" + k);
      linhas.push([
        k,
        b ? "botao-ok" : "SEM-BOTAO",
        p ? (p.hidden ? "OCULTO" : "visivel") : "SEM-PAINEL",
        p ? p.innerHTML.length : -1
      ].join(","));
    });
    var d = document.createElement("div");
    d.id = "__sonda";
    d.textContent = linhas.join(";") + "|" + (window.__erros.join(" ~ ") || "nenhum");
    document.body.appendChild(d);
  }, 200);
});
</script>
"""


def acha_chromium() -> str | None:
    for padrao in ("chromium*/chrome-linux/chrome", "chromium*/chrome-linux/headless_shell"):
        for c in sorted(Path("/opt/pw-browsers").glob(padrao)):
            return str(c)
    return None


def confere_vazamento(html: str) -> list[str]:
    """Lê o JSON embutido e procura o que não deveria ter atravessado."""
    m = re.search(r"/\*DADOS\*/(.*?)/\*FIM\*/", html, re.S)
    if not m:
        return ["bloco /*DADOS*/ não encontrado na página gerada"]
    try:
        estado = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        return [f"o JSON embutido não parseia: {e}"]

    problemas = []
    for campo in PROIBIDOS_ESTADO:
        if campo in estado:
            problemas.append(
                f"o bloco '{campo}' foi para a página pública — ele carrega o hash "
                "da senha de administrador."
            )
    vazando: dict[str, int] = {}
    for e in estado.get("editais", []):
        for campo in PROIBIDOS_EDITAL:
            if campo in e:
                vazando[campo] = vazando.get(campo, 0) + 1
    for campo, n in vazando.items():
        problemas.append(
            f"o campo '{campo}' sobreviveu em {n} edital(is) — é o funil comercial "
            "da Thutor num repositório público."
        )
    if "<button" in html and 'id="tab-acompanhamento"' in html:
        problemas.append("o botão da aba Acompanhamento continua na página pública.")
    return problemas


def confere_estilo(html: str) -> list[str]:
    """
    A página pública precisa levar o próprio CSS.

    Isto já falhou uma vez, e falhou em silêncio: o `<style>` estava no
    `<head>` do arquivo do artifact, e build_publico.py descarta tudo antes de
    `<body>` — porque o host do artifact injeta o `<head>` dele. O espelho saiu
    com todo o conteúdo certo e nenhuma regra de estilo, e nada na saída dos
    scripts denunciou: o validador aprovou, o gerador aprovou, e o teste de
    navegação aprovou, porque as abas continuavam funcionando. Só olhando a
    página se via que ela tinha virado texto cru.
    """
    problemas = []
    if "<style" not in html:
        problemas.append(
            "a página pública saiu sem nenhum bloco <style> — o CSS ficou para "
            "trás. No arquivo do artifact, o estilo precisa vir DEPOIS de "
            "<body>, porque o host injeta o próprio <head> e build_publico.py "
            "descarta tudo o que vem antes."
        )
    if "fonts.googleapis.com" not in html:
        problemas.append("o link da fonte não atravessou para a página pública.")
    if "--teal" not in html:
        problemas.append("os tokens de cor do sistema visual Thutor não estão na página.")
    return problemas


def main() -> None:
    pagina = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "docs" / "index.html"
    if not pagina.exists():
        raise SystemExit(f"FALHA: {pagina} não existe. Rode tools/build_publico.py antes.")

    html = pagina.read_text(encoding="utf8")
    falhou = 0

    print("--- vazamento de dados internos ---")
    problemas = confere_vazamento(html) + confere_estilo(html)
    for p in problemas:
        print(f"FALHOU {p}")
    falhou += len(problemas)
    if not problemas:
        print("ok   nem auth, nem status, nem nota atravessaram; o estilo veio junto.")

    print("\n--- navegação num navegador real ---")
    chrome = acha_chromium()
    if not chrome:
        print("aviso: Chromium não encontrado; teste de navegador pulado.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            alvo = Path(tmp) / "sonda.html"
            alvo.write_text(html.replace("</body>", SONDA + "</body>"), encoding="utf8")
            r = subprocess.run(
                [chrome, "--headless", "--no-sandbox", "--disable-gpu",
                 "--virtual-time-budget=9000", "--dump-dom", alvo.as_uri()],
                capture_output=True, text=True,
            )

        m = re.search(r'id="__sonda"[^>]*>(.*?)</div>', r.stdout, re.S)
        if not m:
            print("FALHOU a sonda não rodou — a página quebrou antes de carregar.")
            print(r.stdout[-500:])
            falhou += 1
        else:
            corpo, erros = m.group(1).split("|", 1)
            for linha in corpo.split(";"):
                aba, botao, visivel, tamanho = linha.split(",")
                tamanho = int(tamanho)
                probs = []
                if botao != "botao-ok":
                    probs.append("botão da aba não existe")
                if visivel != "visivel":
                    probs.append(f"painel {visivel.lower()} depois do clique")
                if tamanho < CONTEUDO_MINIMO:
                    probs.append(f"painel praticamente vazio ({tamanho} bytes)")
                falhou += bool(probs)
                print(f"{'ok  ' if not probs else 'FALHOU'} aba {aba:<10} {tamanho:>6} bytes"
                      + ("  <<< " + "; ".join(probs) if probs else ""))
            if erros.strip() != "nenhum":
                falhou += 1
                print(f"FALHOU erros de JavaScript: {erros.strip()}")

    print()
    if falhou:
        print(f"{falhou} problema(s). A página pública não está pronta para publicar.")
        raise SystemExit(1)
    print(f"{len(ABAS)} abas funcionando, sem erro de JavaScript, sem vazamento.")


if __name__ == "__main__":
    main()
