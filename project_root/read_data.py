import fitz

doc = fitz.open('../docs/03_01_2024___Projeto_Pedagogico_de_Curso___ADS_Paracambi__1_.pdf')
with open('ads_matrix.txt', 'w', encoding='utf-8') as f:
    for p in [16, 17]:
        f.write(f"\n=== PAGE {p} ===\n{doc[p-1].get_text()}\n")
print("Done")
