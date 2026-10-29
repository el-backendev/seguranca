import os
import pandas as pd
from collections import Counter
from nomes import fingerprint

AQUI = os.path.dirname(os.path.abspath(__file__))
pop = pd.read_csv(os.path.join(AQUI, "populacao_mulheres_sp.csv"))
oco = pd.read_csv(os.path.join(AQUI, "ocorrencias_mulher_sp.csv"))

fps = Counter(fingerprint(m) for m in pop["municipio"])
dups = [k for k, v in fps.items() if v > 1]
print("fingerprints IBGE duplicados:", len(dups), dups[:10])

pk = {fingerprint(m): m for m in pop["municipio"]}
om = sorted(oco["municipio"].unique())
nm = [m for m in om if fingerprint(m) not in pk]
print("SSP municipios:", len(om), "sem match:", len(nm))
print("exemplos sem match:", nm[:30])
