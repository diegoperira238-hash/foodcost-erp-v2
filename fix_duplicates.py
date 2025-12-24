# fix_duplicates.py
print("🔧 REMOVENDO FUNÇÕES DUPLICADAS DO app.py")
print("="*60)

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar as linhas problemáticas
health_check_lines = []
page_not_found_lines = []
internal_error_lines = []
main_blocks = []

for i, line in enumerate(lines):
    if 'def health_check():' in line:
        health_check_lines.append(i)
    elif 'def page_not_found(' in line:
        page_not_found_lines.append(i)
    elif 'def internal_server_error(' in line:
        internal_error_lines.append(i)
    elif "if __name__ == '__main__':" in line:
        main_blocks.append(i)

print(f"✅ Análise encontrada:")
print(f"   • health_check(): {len(health_check_lines)} ocorrências")
print(f"   • page_not_found(): {len(page_not_found_lines)} ocorrências")
print(f"   • internal_server_error(): {len(internal_error_lines)} ocorrências")
print(f"   • main blocks: {len(main_blocks)} ocorrências")

# Remover duplicatas - manter apenas a PRIMEIRA de cada
lines_to_remove = []

# Para health_check: manter a PRIMEIRA (linha ~2102), remover outras
if len(health_check_lines) > 1:
    print(f"📝 Mantendo health_check na linha {health_check_lines[0]+1}, removendo outras...")
    for line_num in health_check_lines[1:]:
        # Encontrar o @app.route correspondente
        start = line_num
        while start > 0 and '@app.route' not in lines[start-1]:
            start -= 1
        
        # Encontrar fim da função
        end = line_num + 1
        while end < len(lines) and lines[end].strip() and not (lines[end].startswith('@app.route') or lines[end].startswith('def ') or lines[end].startswith('if __name__')):
            end += 1
        
        print(f"   Removendo linhas {start+1}-{end+1}")
        lines_to_remove.extend(range(start, end))

# Para page_not_found: manter a PRIMEIRA (~2165), remover outras
if len(page_not_found_lines) > 1:
    print(f"📝 Mantendo page_not_found na linha {page_not_found_lines[0]+1}, removendo outras...")
    for line_num in page_not_found_lines[1:]:
        # Encontrar o @app.errorhandler correspondente
        start = line_num
        while start > 0 and '@app.errorhandler' not in lines[start-1]:
            start -= 1
        
        # Encontrar fim da função
        end = line_num + 1
        while end < len(lines) and lines[end].strip() and not (lines[end].startswith('@app.errorhandler') or lines[end].startswith('def ') or lines[end].startswith('if __name__')):
            end += 1
        
        print(f"   Removendo linhas {start+1}-{end+1}")
        lines_to_remove.extend(range(start, end))

# Para internal_server_error: manter a PRIMEIRA (~2168), remover outras
if len(internal_error_lines) > 1:
    print(f"📝 Mantendo internal_server_error na linha {internal_error_lines[0]+1}, removendo outras...")
    for line_num in internal_error_lines[1:]:
        # Encontrar o @app.errorhandler correspondente
        start = line_num
        while start > 0 and '@app.errorhandler' not in lines[start-1]:
            start -= 1
        
        # Encontrar fim da função
        end = line_num + 1
        while end < len(lines) and lines[end].strip() and not (lines[end].startswith('@app.errorhandler') or lines[end].startswith('def ') or lines[end].startswith('if __name__')):
            end += 1
        
        print(f"   Removendo linhas {start+1}-{end+1}")
        lines_to_remove.extend(range(start, end))

# Para main blocks: manter o ÚLTIMO (o correto), remover anteriores
if len(main_blocks) > 1:
    print(f"📝 Mantendo main block na linha {main_blocks[-1]+1}, removendo anteriores...")
    for i, line_num in enumerate(main_blocks[:-1]):  # Todos exceto o último
        # Encontrar início do bloco
        start = line_num
        
        # Encontrar fim do bloco (até próxima linha não indentada ou EOF)
        end = line_num + 1
        while end < len(lines) and (lines[end].startswith(' ') or lines[end].startswith('\t') or not lines[end].strip()):
            end += 1
        
        print(f"   Removendo main block duplicado nas linhas {start+1}-{end+1}")
        lines_to_remove.extend(range(start, end))

# Remover as linhas (em ordem reversa para não bagunçar índices)
lines_to_remove = sorted(set(lines_to_remove), reverse=True)
for line_num in lines_to_remove:
    if line_num < len(lines):
        del lines[line_num]

# Salvar o arquivo corrigido
with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\n✅ {len(lines_to_remove)} linhas duplicadas removidas!")
print("\n🎯 PRÓXIMOS PASSOS:")
print("1. git add app.py")
print("2. git commit -m 'Remove funções duplicadas do final do arquivo'")
print("3. git push origin main")
print("4. O Render fará deploy automático")
print("="*60)

# Mostrar o final do arquivo corrigido
print("\n📄 FINAL DO app.py APÓS CORREÇÃO:")
with open('app.py', 'r', encoding='utf-8') as f:
    all_lines = f.readlines()
    # Mostrar últimas 50 linhas
    for i in range(max(0, len(all_lines)-50), len(all_lines)):
        print(f"{i+1:4d}: {all_lines[i].rstrip()}")