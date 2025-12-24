# fix_before_first_request.py
import re

print("🔧 CORRIGINDO before_first_request (DEPRECIADO NO FLASK 2.3+)")
print("="*60)

# Ler o app.py
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Encontrar todas as ocorrências
pattern = r'@app\.before_first_request\s*\n\s*def (\w+)\(\):'
matches = list(re.finditer(pattern, content, re.MULTILINE))

if not matches:
    print("❌ Nenhum before_first_request encontrado. Verifique manualmente.")
    # Procurar de outra forma
    if '@app.before_first_request' in content:
        print("⚠️  Encontrado texto, mas não no padrão esperado.")
        # Mostrar contexto
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if '@app.before_first_request' in line:
                print(f"\nLinha {i+1}: {line}")
                # Mostrar algumas linhas ao redor
                for j in range(max(0, i-2), min(len(lines), i+3)):
                    print(f"  {j+1}: {lines[j]}")
else:
    print(f"✅ Encontrado {len(matches)} before_first_request a corrigir")
    
    for match in matches:
        func_name = match.group(1)
        print(f"\n📌 Função encontrada: {func_name}()")
        
        # Substituir
        old_decorator = match.group(0)
        new_decorator = f"""# Substituído before_first_request (depreciado no Flask 2.3+)
first_request_done = False

@app.before_request
def {func_name}():
    global first_request_done
    if not first_request_done:
        # Código que rodava apenas na primeira requisição
"""
        
        print(f"📝 Substituindo...")
        
        # Encontrar a função completa
        func_start = match.end()
        # Procurar o início do corpo da função
        lines = content[func_start:].split('\n')
        indent_level = None
        func_body_lines = []
        
        for i, line in enumerate(lines):
            if i == 0:
                # Primeira linha após o def
                if ':' in line:
                    # Encontrar nível de indentação
                    match_indent = re.match(r'^(\s+)', line)
                    if match_indent:
                        indent_level = len(match_indent.group(1))
                continue
            
            if indent_level is not None:
                if line.startswith(' ' * indent_level):
                    func_body_lines.append(line)
                else:
                    break
        
        # Reconstruir a função
        old_function = old_decorator + '\n' + '\n'.join([f'def {func_name}():'] + func_body_lines)
        
        # Nova função com a correção
        new_function = new_decorator + '\n' + '\n'.join([f'{" " * 8}{line.lstrip()}' for line in func_body_lines]) + '\n        first_request_done = True'
        
        print(f"📋 Substituição pronta")
        
        # Fazer a substituição
        content = content.replace(old_function, new_function)

# Salvar o arquivo
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n" + "="*60)
print("✅ Correção aplicada!")
print("\n🎯 PRÓXIMOS PASSOS:")
print("1. Verifique o app.py corrigido")
print("2. Execute: git add app.py")
print("3. Execute: git commit -m 'Correção: before_first_request para Flask 2.3+'")
print("4. Execute: git push origin main")
print("5. O Render fará deploy automático")
print("="*60)

# Mostrar as linhas corrigidas
print("\n📄 ÁREA CORRIGIDA NO app.py (linhas ~2063):")
with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    start_line = max(0, 2060)  # Mostrar um pouco antes
    end_line = min(len(lines), 2080)  # Mostrar um pouco depois
    for i in range(start_line, end_line):
        if i < len(lines):
            print(f"Linha {i+1}: {lines[i].rstrip()}")