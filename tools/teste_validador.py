#!/usr/bin/env python3
"""
Os cenários que o portão precisa barrar.

Um validador que nunca reprova nada não é um portão, é um enfeite — e um
enfeite que dá a sensação de segurança é pior do que não ter nada. Este arquivo
existe para provar que ele reprova, e que reprova pelo motivo certo.

O primeiro cenário reproduz o incidente real da Pauta Thutor: uma execução de
56 segundos que não pesquisou nada e mesmo assim foi registrada como
SUCCEEDED. O segundo é o que este projeto tem e aquele não tinha — a API do
PNCP informa quantos registros existem no período, então dá para provar que a
varredura viu tudo, em vez de apenas confiar no relógio.

    python3 tools/teste_validador.py
"""

import copy
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
VALIDADOR = Path(__file__).parent / "valida_rodada.py"
HOJE = datetime.now(TZ)


def base() -> dict:
    """Uma rodada íntegra: tudo o que segue são estragos aplicados sobre ela."""
    ini = HOJE.replace(hour=2, minute=0, second=0, microsecond=0)
    return {
        "versao": 1,
        "atualizado_em": HOJE.isoformat(timespec="seconds"),
        "editais": [{
            "id": "pncp:00000000000191-1-000042-2026",
            "fonte": "PNCP",
            "orgao": "MUNICIPIO DE EXEMPLO",
            "uf": "PR", "municipio": "Exemplo",
            "modalidade": "Pregão - Eletrônico",
            "objeto": "Contratação de consultoria para pesquisa de clima organizacional",
            "valor": 480000.0, "sigiloso": False,
            "publicado_em": (HOJE - timedelta(days=1)).date().isoformat(),
            "encerramento": (HOJE + timedelta(days=12)).isoformat(timespec="seconds"),
            "link": "https://pncp.gov.br/app/editais/00000000000191/2026/42",
            "score": 84, "frentes": ["cultura"], "disputa": "aberto",
            "situacao_item": "em_disputa",
            "veredito": "quente",
            "justificativa": "Pesquisa de clima e cultura organizacional é a frente principal da casa.",
            "visto_em": HOJE.date().isoformat(),
        }],
        "rodadas": [{
            "data": HOJE.date().isoformat(),
            "cobertura": {
                "iniciado_em": ini.isoformat(timespec="seconds"),
                "concluido_em": (ini + timedelta(minutes=18)).isoformat(timespec="seconds"),
                "rede_direta": True,
                "pncp": {"brutos": 5453, "esperados": 5453, "paginas": 124,
                         "paginas_perdidas": 0, "candidatos": 24,
                         "modalidades_falhas": [], "erros": []},
                "externas": {"tentadas": 15, "abertas": 9, "candidatos": 2, "falhas": []},
                "triados": 26, "conferidos": 1, "novos": 12, "descartados": 14,
            },
        }],
    }


def roda(estado: dict) -> tuple[int, str]:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf8") as f:
        json.dump(estado, f, ensure_ascii=False)
        caminho = f.name
    r = subprocess.run([sys.executable, str(VALIDADOR), caminho],
                       capture_output=True, text=True)
    Path(caminho).unlink(missing_ok=True)
    return r.returncode, r.stdout + r.stderr


# (nome, estraga, deve_reprovar, trecho esperado na saída)
def _incidente_56s(e):
    c = e["rodadas"][0]["cobertura"]
    ini = datetime.fromisoformat(c["iniciado_em"])
    c["concluido_em"] = (ini + timedelta(seconds=56)).isoformat(timespec="seconds")

def _pagina_perdida(e):
    c = e["rodadas"][0]["cobertura"]["pncp"]
    c["paginas_perdidas"] = 2
    c["brutos"] = 5353

def _conta_nao_fecha(e):
    e["rodadas"][0]["cobertura"]["pncp"]["brutos"] = 4900   # esperados seguem 5453

def _feriado(e):
    # Dia magro em que a conta FECHA: 7 de setembro cai numa segunda, e o PNCP
    # publica pouco. A varredura está completa — reprovar aqui seria um alarme
    # falso semanal, do tipo que ensina a ignorar o alarme.
    p = e["rodadas"][0]["cobertura"]["pncp"]
    p["brutos"] = p["esperados"] = 180
    p["candidatos"] = 2

def _sem_esperados_e_vazio(e):
    # Aqui não há como conferir completude: a API não disse quanto havia. É o
    # único caso em que o piso cego decide, e é como uma fonte muda de resposta
    # sem avisar.
    p = e["rodadas"][0]["cobertura"]["pncp"]
    p["esperados"] = 0
    p["brutos"] = 12
    p["candidatos"] = 0

def _sem_esperados_mas_cheio(e):
    p = e["rodadas"][0]["cobertura"]["pncp"]
    p["esperados"] = 0

def _modalidade_caiu(e):
    e["rodadas"][0]["cobertura"]["pncp"]["modalidades_falhas"] = ["Concorrência - Eletrônica"]

def _sem_camada2(e):
    e["rodadas"][0]["cobertura"].pop("externas")

def _camada2_rasa(e):
    e["rodadas"][0]["cobertura"]["externas"] = {"tentadas": 2, "abertas": 2, "candidatos": 0}

def _triagem_incompleta(e):
    e["rodadas"][0]["cobertura"]["triados"] = 9   # 24 + 2 candidatos colhidos

def _rodada_de_ontem(e):
    e["rodadas"][0]["data"] = (HOJE - timedelta(days=1)).date().isoformat()

def _sem_cobertura(e):
    e["rodadas"][0].pop("cobertura")

def _auth_voltou(e):
    e["auth"] = {"usuario": "thutor", "salt": "s", "hash": "h"}

def _status_no_estado(e):
    e["editais"][0]["status"] = "participando"

def _nota_no_estado(e):
    e["editais"][0]["nota"] = "contato: fulano na diretoria"

def _quente_ja_contratado(e):
    # O caso exato de 03/09/2026: Dispensa sem janela de proposta, contrato já
    # assinado, e o radar chamando de oportunidade quente.
    e["editais"][0]["disputa"] = "decidido"
    e["editais"][0]["encerramento"] = None

def _quente_com_prazo_vencido(e):
    e["editais"][0]["disputa"] = "encerrado"
    e["editais"][0]["encerramento"] = (HOJE - timedelta(days=5)).isoformat(timespec="seconds")

def _sem_disputa(e):
    e["editais"][0].pop("disputa")

def _sem_conferencia(e):
    # O radar publicando a dedução da coleta como se fosse a situação real.
    e["editais"][0].pop("situacao_item")

def _conferencia_parcial(e):
    e["rodadas"][0]["cobertura"]["conferidos"] = 0

def _morno_ja_contratado(e):
    # Isto PRECISA passar: contratação decidida é inteligência de mercado
    # legítima, desde que não se venda como oportunidade.
    e["editais"][0]["disputa"] = "decidido"
    e["editais"][0]["encerramento"] = None
    e["editais"][0]["veredito"] = "morno"
    e["editais"][0]["vencedor"] = {"fornecedor": "UNIVERSIDADE FEDERAL DE SANTA CATARINA",
                                   "valor": 1500000.0, "assinado_em": "2026-09-01"}

def _sem_veredito(e):
    e["editais"][0]["veredito"] = None

def _quente_sem_justificativa(e):
    e["editais"][0]["justificativa"] = ""

def _id_duplicado(e):
    e["editais"].append(copy.deepcopy(e["editais"][0]))

def _link_quebrado(e):
    e["editais"][0]["link"] = "pncp.gov.br/editais/42"

def _data_no_futuro(e):
    e["editais"][0]["publicado_em"] = (HOJE + timedelta(days=3)).date().isoformat()


CASOS = [
    ("rodada íntegra", None, False, "ok"),
    ("incidente das 56 segundos", _incidente_56s, True, "não aconteceu"),
    ("página do PNCP perdida", _pagina_perdida, True, "se perderam"),
    ("colheu menos do que a API prometeu", _conta_nao_fecha, True, "não foram vistas"),
    ("feriado: pouco volume, conta fechada", _feriado, False, "ok"),
    ("esperados sumiu e veio quase nada", _sem_esperados_e_vazio, True, "não tenha respondido"),
    ("esperados sumiu mas veio volume normal", _sem_esperados_mas_cheio, False, "ok"),
    ("modalidade inteira falhou", _modalidade_caiu, True, "por inteiro"),
    ("camada 2 não rodou", _sem_camada2, True, "obrigatória"),
    ("camada 2 visitou 2 fontes", _camada2_rasa, True, "fontes externas visitadas"),
    ("triagem deixou candidatos para trás", _triagem_incompleta, True, "nem lidos"),
    ("rodada é de ontem", _rodada_de_ontem, True, "não de hoje"),
    ("cobertura ausente", _sem_cobertura, True, "prova"),
    ("auth voltou ao estado", _auth_voltou, True, "voltou a carregar"),
    ("status escrito no estado", _status_no_estado, True, "não pertence ao estado"),
    ("nota escrita no estado", _nota_no_estado, True, "não pertence ao estado"),
    ("quente numa contratação direta", _quente_ja_contratado, True, "ainda pode disputar"),
    ("quente com prazo vencido", _quente_com_prazo_vencido, True, "ainda pode disputar"),
    ("campo disputa ausente", _sem_disputa, True, "disputa"),
    ("situação não conferida na fonte", _sem_conferencia, True, "conferida na fonte"),
    ("conferência não cobriu o radar", _conferencia_parcial, True, "conferidos na fonte"),
    ("morno já contratado, com vencedor", _morno_ja_contratado, False, "ok"),
    ("edital sem veredito", _sem_veredito, True, "veredito"),
    ("quente sem justificativa", _quente_sem_justificativa, True, "sem justificativa"),
    ("id duplicado", _id_duplicado, True, "duplicado"),
    ("link sem esquema", _link_quebrado, True, "link inválido"),
    ("publicado no futuro", _data_no_futuro, True, "futuro"),
]


def main() -> None:
    falhas = []
    for nome, estraga, deve_reprovar, trecho in CASOS:
        estado = base()
        if estraga:
            estraga(estado)
        codigo, saida = roda(estado)
        reprovou = codigo != 0
        ok = reprovou == deve_reprovar and trecho in saida
        print(f"  {'ok ' if ok else 'ERRO'} {nome:42s} saída {codigo}")
        if not ok:
            falhas.append(
                f"{nome}: esperava {'reprovar' if deve_reprovar else 'aprovar'} "
                f"com {trecho!r}, veio código {codigo}.\n"
                + "\n".join("      " + l for l in saida.strip().splitlines()[:6])
            )

    print()
    if falhas:
        print(f"FALHA: {len(falhas)} cenário(s) fora do esperado.")
        for f in falhas:
            print(f"  - {f}")
        raise SystemExit(1)
    print(f"ok  {len(CASOS)} cenários, incluindo a reprodução do incidente de "
          "29/08/2026 e a conta de cobertura que ele não tinha como fazer.")


if __name__ == "__main__":
    main()
