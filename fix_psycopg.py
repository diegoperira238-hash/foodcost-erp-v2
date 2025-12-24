# fix_psycopg.py
import re

print("🔧 CORRIGINDO CONFIGURAÇÃO DO BANCO DE DADOS")
print("="*50)

# Ler o app.py
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Contar ocorrências
psycopg_count = content.count('psycopg://')
psycopg2_count = content.count('psycopg2://')
psycopg3_count = content.count('Psycopg3')

print(f"1. Status atual:")
print(f"   • psycopg:// encontrado: {psycopg_count} vezes")
print(f"   • psycopg2:// encontrado: {psycopg2_count} vezes")
print(f"   • 'Psycopg3' no log: {psycopg3_count} vezes")

# Fazer as correções
if psycopg_count > 0:
    # Correção 1: psycopg:// -> psycopg2://
    content = content.replace('psycopg://', 'psycopg2://')
    print(f"✅ Corrigido: psycopg:// -> psycopg2://")

if psycopg3_count > 0:
    # Correção 2: Psycopg3 -> Psycopg2 no log
    content = content.replace('Psycopg3', 'Psycopg2')
    print(f"✅ Corrigido: Psycopg3 -> Psycopg2")

# Remover linha 45 conflitante (se existir)
lines = content.split('\n')
if 'postgresql+psycopg2://' in lines[44]:  # linha 45 (0-indexed)
    print(f"⚠️  Linha 45 conflitante encontrada e removida")
    # Remover a linha 45 (índice 44)
    del lines[44]
    content = '\n'.join(lines)

# Salvar
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ Correções aplicadas com sucesso!")
print("\n🎯 PRÓXIMOS PASSOS:")
print("1. Verifique o app.py corrigido")
print("2. Execute: git add app.py")
print("3. Execute: git commit -m 'Correção: Usa psycopg2 em vez de psycopg3'")
print("4. Execute: git push origin main")
print("5. O Render fará deploy automático")
print("="*50)

# Mostrar as linhas corrigidas
print("\n📄 LINHAS CORRIGIDAS NO app.py:")
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    for i, line in enumerate(lines[50:65], 51):  # Mostrar linhas 51-65
        if 'psycopg' in line or 'DATABASE' in line:
            print(f"Linha {i}: {line.rstrip()}")