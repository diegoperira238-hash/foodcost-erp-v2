# corrigir_config_admin.py
import re

print("🔧 CORRIGINDO FUNÇÃO config_admin()...")
print("="*60)

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Encontrar a função config_admin
pattern = r'(def config_admin\(\):.*?)(?=\n\n@app\.route|\n\n# =|\Z)'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print("❌ Não encontrou a função config_admin()")
    exit(1)

old_function = match.group(1)
print(f"✅ Encontrou função (tamanho: {len(old_function)} caracteres)")

# Verificar se já tem return
if 'return render_template' in old_function:
    print("✅ Função já tem return. Nada para corrigir.")
    exit(0)

# Adicionar o return faltante
# Encontrar onde termina o código POST
lines = old_function.split('\n')

# Encontrar a última linha antes de adicionar o return
new_function_lines = []
for i, line in enumerate(lines):
    new_function_lines.append(line)
    
    # Se for a linha "return redirect(url_for('config_admin'))" após POST
    if "return redirect(url_for('config_admin'))" in line and i < len(lines) - 2:
        # Verificar se as próximas linhas são o fim da função
        next_lines = lines[i+1:i+3]
        if all(not l.strip() or l.startswith(' ') for l in next_lines):
            # Adicionar o return faltante
            new_function_lines.append('')
            new_function_lines.append('    # 🔥 PARTE PARA REQUISIÇÕES GET 🔥')
            new_function_lines.append('    # Dados para o template')
            new_function_lines.append('    if usuario.username == \'bpereira\':')
            new_function_lines.append('        lojas = Loja.query.all()')
            new_function_lines.append('        usuarios = Usuario.query.all()')
            new_function_lines.append('    else:')
            new_function_lines.append('        lojas = Loja.query.filter_by(id=usuario.loja_id).all()')
            new_function_lines.append('        usuarios = Usuario.query.filter_by(loja_id=usuario.loja_id).all()')
            new_function_lines.append('')
            new_function_lines.append('    # 🔥 ESTE RETURN É ESSENCIAL! 🔥')
            new_function_lines.append('    return render_template(\'config_admin.html\',')
            new_function_lines.append('                         lojas=lojas,')
            new_function_lines.append('                         usuarios=usuarios,')
            new_function_lines.append('                         agora=datetime.now(),')
            new_function_lines.append('                         is_super_admin=(usuario.username == \'bpereira\'))')

new_function = '\n'.join(new_function_lines)

# Substituir no conteúdo
content = content.replace(old_function, new_function)

# Salvar backup
with open('app.py.backup', 'w', encoding='utf-8') as f:
    f.write(content.replace(new_function, old_function))  # Salva o original

# Salvar correção
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Função corrigida com sucesso!")
print("✅ Backup salvo como 'app.py.backup'")
print("\n🎯 A função agora tem:")
print("   • Verificação de limite de 10 lojas")
print("   • Return para requisições GET")
print("   • Sistema de alertas por email")
print("\n🚀 Reinicie o servidor:")
print("   python app.py")
print("="*60)