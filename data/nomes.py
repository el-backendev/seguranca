"""
Reconciliacao de nomes de municipio entre a SSP-SP (nomes abreviados, ex.
'S.PAULO', 'S.BERNARDO DO CAMPO') e o IBGE (nomes por extenso, ex.
'Sao Paulo', 'Sao Bernardo do Campo').

Estrategia deterministica (sem adivinhar): remove acentos, pontuacao e as
"stopwords" de ligacao e de santo (SAO/SANTA/SANTO e abreviacoes S./STO./STA.),
restando um conjunto de tokens significativos ("fingerprint"). Os 645
municipios de SP tem fingerprints unicos, entao o casamento e 1-para-1.
"""
import re
import unicodedata


def base(t: str) -> str:
    n = unicodedata.normalize("NFKD", str(t))
    s = "".join(c for c in n if not unicodedata.combining(c)).upper()
    s = s.replace("'", " ").replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Palavras ignoradas no fingerprint: ligacoes e marcadores de "santo".
STOP = {
    "SAO", "SANTA", "SANTO", "S", "STO", "STA",
    "D", "DO", "DA", "DOS", "DAS", "DE",
}


# Casos em que a abreviacao/ortografia da SSP difere do IBGE e nao e
# resolvido pelas stopwords. Mapeia fingerprint(SSP) -> fingerprint(IBGE).
# Sao municipios reais, apenas grafados de forma diferente.
ALIAS = {
    "CUNHA EUCLIDES PTA": "CUNHA EUCLIDES PAULISTA",  # Euclides da Cunha Paulista
    "FLORINIA": "FLORINEA",                            # Florinia -> Florinea
}


def fingerprint(t: str) -> str:
    toks = [w for w in base(t).split() if w not in STOP]
    fp = " ".join(sorted(toks))
    return ALIAS.get(fp, fp)
