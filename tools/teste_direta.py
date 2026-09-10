#!/usr/bin/env python3
"""
Contratação direta não entra no radar — e não sai da memória.

Dispensa de licitação é a hipótese em que a lei permite contratar SEM
concorrência. Quando o extrato aparece no PNCP a escolha do fornecedor já foi
feita, então exibi-la como oportunidade é ocupar a tela com o que ninguém pode
disputar. O caminho para contratação direta é relacionamento com o órgão, e
essa frente comercial não passa por este sistema.

A metade menos óbvia é a que estes casos protegem de verdade: **a dispensa
continua na memória**. Três dos quatro contratos com vencedor conhecido são
dispensas — é delas que sai a resposta a "quem está ganhando o que a Thutor
vende". Cortá-las na coleta, como se faz com a inexigibilidade, deixaria o
radar limpo e cego. Por isso o corte é no `pescavel`, que roda depois de a
memória ser preenchida, e não na coleta.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rodada import funde                       # noqa: E402

HOJE = "2026-09-11"
def ed(i, mod, disp="aberto", enc="2026-09-30T09:00:00", val=900000.0, org=None, obj=None):
    return {"id":i,"fonte":"PNCP","orgao":org or f"ORGAO {i}","uf":"SP","modalidade":mod,
            "objeto":obj or f"consultoria de cultura organizacional e lideranca {i}","valor":val,
            "sigiloso":False,"publicado_em":"2026-09-11","encerramento":enc,
            "link":"https://pncp.gov.br/app/editais/1/2026/1","score":80,
            "frentes":["cultura"],"disputa":disp,"situacao_item":"em_disputa",
            "vencedor":{"fornecedor":"FUNDACAO QUALQUER","valor":val}} if mod=="Dispensa" else {
            "id":i,"fonte":"PNCP","orgao":org or f"ORGAO {i}","uf":"SP","modalidade":mod,
            "objeto":obj or f"consultoria de cultura organizacional e lideranca {i}","valor":val,
            "sigiloso":False,"publicado_em":"2026-09-11","encerramento":enc,
            "link":"https://pncp.gov.br/app/editais/1/2026/1","score":80,
            "frentes":["cultura"],"disputa":disp,"situacao_item":"em_disputa"}
r={"candidatos":[ed("pncp:a","Pregão - Eletrônico"), ed("pncp:b","Dispensa", val=1500000.0),
                 ed("pncp:c","Concorrência - Eletrônica", val=2000000.0)],
   "cobertura":{"censo":{}}}
novo, novos, fechados, dup, baratos, diretas = funde({"editais":[],"memoria":[]}, r, {}, HOJE)
ids_radar={e["id"] for e in novo["editais"]}
ids_mem={m["id"] for m in novo["memoria"]}
falhas=[]
def ck(n,c,d=""):
    print(f"  {'ok  ' if c else 'FALHOU'} {n}" + ("" if c else f"   <<< {d}"))
    if not c: falhas.append(n)
ck("dispensa NÃO entra no radar", "pncp:b" not in ids_radar, sorted(ids_radar))
ck("pregão e concorrência entram", {"pncp:a","pncp:c"} <= ids_radar, sorted(ids_radar))
ck("dispensa FICA na memória (inteligência de quem ganhou)", "pncp:b" in ids_mem, sorted(ids_mem))
ck("o vencedor sobrevive na memória",
   any(m["id"]=="pncp:b" and m.get("vencedor") for m in novo["memoria"]),
   "vencedor perdido")
ck("contada como direta, não como encerrada", diretas==1 and fechados==0,
   f"diretas={diretas} fechados={fechados}")
# dispensa com prazo aberto tambem sai: a janela nao muda a natureza
r2={"candidatos":[ed("pncp:d","Dispensa", enc="2026-12-01T09:00:00")],"cobertura":{"censo":{}}}
n2,_,f2,_,_,d2 = funde({"editais":[],"memoria":[]}, r2, {}, HOJE)
ck("dispensa com janela em aberto também sai do radar",
   not n2["editais"] and d2==1, f"editais={len(n2['editais'])} diretas={d2}")
print()
if falhas: print("FALHA:", falhas); sys.exit(1)
print("ok  contratação direta some do radar e sobrevive na memória")
