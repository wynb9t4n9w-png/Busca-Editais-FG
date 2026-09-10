"""
O cadastro de fontes: quem compra, onde publica, e o que já foi medido.

Este arquivo existe porque a pergunta "deveríamos caçar mais fontes?" só tem
resposta com número, e o número mais barato de todos é este: **o comprador
publica no PNCP ou não?** Se publica, a camada 1 já o alcança e um raspador
para o portal dele seria um caminho novo até um lugar onde o radar já está. Se
não publica, aí — e só aí — a camada 2 tem trabalho.

A lista de vigilância abaixo não é uma lista de desejos. É um conjunto de
compradores grandes o bastante para que a AUSÊNCIA deles no PNCP seja
informação: se a ANVISA some por duas semanas, ou ela parou de comprar o nosso
tema, ou parou de publicar onde olhamos. As duas hipóteses exigem ação
diferente, e sem o censo elas se parecem.

Cada CNPJ aqui é conferido contra o que a varredura realmente traz. Um CNPJ
errado não some em silêncio: ele aparece como "nunca visto" para sempre, o que
é indistinguível de um comprador que sumiu. Por isso o campo `conferido_em`.
"""

# ───────────────────── o que a lei manda publicar no PNCP ─────────────────────
#
# Lei 14.133/2021: administração direta, autarquias (inclusive as agências
# reguladoras, que são autarquias em regime especial) e fundações públicas,
# nas três esferas. Estatais regidas pela Lei 13.303/2016 não eram alcançadas
# no desenho original — mas a varredura já trouxe várias delas, entre elas a
# Agência de Fomento do ERJ, que declara no próprio complemento estar sujeita
# à 13.303. Medição vence texto de lei: o que vale é quem aparece.

VIGILANCIA = {
    # agências reguladoras federais — autarquias em regime especial
    "03112386000111": ("ANVISA", "agência"),
    "02334719000190": ("ANEEL", "agência"),
    "02030715000112": ("ANATEL", "agência"),
    "02313673000197": ("ANP", "agência"),
    "03589068000146": ("ANS", "agência"),
    "04898488000177": ("ANTT", "agência"),
    "00375972000160": ("ANAC", "agência"),
    "07822836000110": ("ANA", "agência"),
    # estatais federais de porte
    "33000167000101": ("Petrobras", "estatal federal"),
    "33657248000189": ("BNDES", "estatal federal"),
    "34028316000103": ("Correios", "estatal federal"),
    "00360305000104": ("Caixa Econômica Federal", "estatal federal"),
    "00000000000191": ("Banco do Brasil", "estatal federal"),
    "00001180000126": ("Eletrobras", "estatal federal"),
    "33683111000107": ("Serpro", "estatal federal"),
    "42422253000101": ("Dataprev", "estatal federal"),
    "00348003000110": ("Embrapa", "estatal federal"),
    # estatais estaduais de porte
    "43776517000180": ("Sabesp", "estatal estadual"),
    "17281106000103": ("Cemig", "estatal estadual"),
    "92660757000138": ("Corsan", "estatal estadual"),
    "61695227000193": ("Metrô-SP", "estatal estadual"),
    "60444437000146": ("CPTM", "estatal estadual"),
}

# ───────────── quem NÃO publica no PNCP, e por isso tem camada 2 ─────────────
#
# O Sistema S não é administração pública: são entidades privadas de serviço
# social autônomo, com regulamento próprio de licitação. Nada do que elas
# compram passa pelo PNCP, e é exatamente esse o buraco que tools/camada2.py
# tapa. Não é opinião: é a razão de a camada 2 existir.
FORA_DO_PNCP = (
    "Sistema S — Sesi, Senai, Sesc, Senac, Sebrae, Senar, Sest/Senat: "
    "entidades privadas de serviço social autônomo, regulamento próprio, "
    "não publicam no PNCP. Coberto por tools/camada2.py.",
)
