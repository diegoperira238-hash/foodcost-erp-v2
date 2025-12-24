# preparar_deploy.py
import os
import sys

def criar_arquivos_necessarios():
    """Cria todos os arquivos necessários para deploy no Render"""
    
    print("🚀 CRIANDO ARQUIVOS PARA DEPLOY NO RENDER")
    print("=" * 50)
    
    # 1. requirements.txt
    print("1. Criando requirements.txt...")
    with open('requirements.txt', 'w', encoding='utf-8') as f:
        f.write("""Flask==2.3.3
Flask-SQLAlchemy==3.0.5
psycopg2-binary==2.9.7
python-dotenv==1.0.0
gunicorn==20.1.0
Werkzeug==2.3.7
""")
    
    # 2. runtime.txt
    print("2. Criando runtime.txt...")
    with open('runtime.txt', 'w', encoding='utf-8') as f:
        f.write("python-3.11.4\n")
    
    # 3. Procfile
    print("3. Criando Procfile...")
    with open('Procfile', 'w', encoding='utf-8') as f:
        f.write("web: gunicorn app:app\n")
    
    # 4. render.yaml (opcional mas útil)
    print("4. Criando render.yaml...")
    with open('render.yaml', 'w', encoding='utf-8') as f:
        f.write("""services:
  - type: web
    name: foodcost-erp
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: foodcostdb
          property: connectionString
      - key: PYTHON_VERSION
        value: 3.11.4
""")
    
    # 5. .gitignore (se não existir)
    if not os.path.exists('.gitignore'):
        print("5. Criando .gitignore...")
        with open('.gitignore', 'w', encoding='utf-8') as f:
            f.write("""# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Database
*.db
*.sqlite3
database.db

# Backup files
*.backup
*.bak

# Environment
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Arquivos temporários
*.tmp
temp/

# Scripts temporários
corrigir_config_admin.py
criar_usuario.py
verificar_limite.py
corretor_acessos.py
preparar_deploy.py
""")
    
    # 6. README.md
    print("6. Criando README.md...")
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write("""# 🍽️ FoodCost ERP - Sistema de Fichas Técnicas

Sistema completo para gestão de fichas técnicas e custos em restaurantes.

## 🚀 Deploy no Render

1. Conecte este repositório no Render.com
2. Crie um banco de dados PostgreSQL
3. Configure as variáveis de ambiente:
   - `DATABASE_URL`: String de conexão PostgreSQL
   - `CHAVE_MESTRA`: Sua chave secreta
4. O sistema estará pronto!

## 🔐 Acesso Padrão

**Super Admin:**
- Usuário: `bpereira`
- Senha: `chef@26`
""")
    
    print("\n✅ TODOS OS ARQUIVOS FORAM CRIADOS!")
    print("=" * 50)

def verificar_estrutura():
    """Verifica se a estrutura do projeto está completa"""
    
    print("\n🔍 VERIFICANDO ESTRUTURA DO PROJETO")
    print("=" * 50)
    
    arquivos_necessarios = [
        'app.py',
        'requirements.txt',
        'Procfile',
        'runtime.txt',
        '.gitignore',
        'templates/base.html',
        'templates/login.html',
        'templates/index.html',
        'static/css/',
    ]
    
    for arquivo in arquivos_necessarios:
        if os.path.exists(arquivo):
            print(f"✅ {arquivo}")
        else:
            print(f"❌ {arquivo} (FALTANDO)")
    
    print("\n🎯 STATUS DO BANCO DE DADOS:")
    if os.path.exists('database.db'):
        tamanho = os.path.getsize('database.db') / 1024
        print(f"⚠️  database.db encontrado ({tamanho:.1f} KB)")
        print("   Este arquivo NÃO deve ir para o GitHub!")
    else:
        print("✅ database.db não encontrado (bom para produção)")

def instrucoes_git():
    """Mostra instruções para configurar o Git"""
    
    print("\n📦 INSTRUÇÕES PARA GIT")
    print("=" * 50)
    
    print("\n1. Primeiro, REMOVA arquivos que não devem ir para o GitHub:")
    print("   git rm --cached database.db")
    print("   git rm --cached *.backup")
    print("   git rm --cached corrigir_config_admin.py")
    print("   git rm --cached criar_usuario.py")
    print("   git rm --cached verificar_limite.py")
    
    print("\n2. Adicione os novos arquivos:")
    print("   git add requirements.txt")
    print("   git add Procfile")
    print("   git add runtime.txt")
    print("   git add .gitignore")
    print("   git add README.md")
    print("   git add render.yaml")
    
    print("\n3. Se houver conflitos, resolva:")
    print("   git add .")
    print("   git commit -m 'Sistema pronto para produção'")
    
    print("\n4. Configure o remote (SE O REPOSITÓRIO EXISTIR):")
    print("   git remote remove origin")
    print("   git remote add origin https://github.com/diegoperira238-hash/foodcost-erp-v2.git")
    
    print("\n5. Faça push:")
    print("   git push -u origin main")

def instrucoes_render():
    """Mostra instruções para deploy no Render"""
    
    print("\n🌐 INSTRUÇÕES PARA RENDER.COM")
    print("=" * 50)
    
    print("\n1. Acesse: https://render.com")
    print("2. Clique em 'New +' → 'Web Service'")
    print("3. Conecte sua conta do GitHub")
    print("4. Selecione seu repositório: diegoperira238-hash/foodcost-erp-v2")
    print("\n5. Configure o Web Service:")
    print("   • Name: foodcost-erp")
    print("   • Environment: Python 3")
    print("   • Build Command: pip install -r requirements.txt")
    print("   • Start Command: gunicorn app:app")
    print("\n6. Clique em 'Advanced' e adicione:")
    print("   • DATABASE_URL: (deixe em branco por enquanto)")
    print("   • CHAVE_MESTRA: sua_chave_secreta_123")
    print("\n7. Clique em 'Create Web Service'")
    print("\n8. Depois crie um banco PostgreSQL:")
    print("   • Dashboard → 'New +' → 'PostgreSQL'")
    print("   • Name: foodcostdb")
    print("   • Copie a connection string")
    print("   • Volte ao Web Service e atualize DATABASE_URL")

if __name__ == "__main__":
    criar_arquivos_necessarios()
    verificar_estrutura()
    instrucoes_git()
    instrucoes_render()
    
    print("\n" + "=" * 50)
    print("🎉 PRONTO! SIGA OS PASSOS ACIMA.")
    print("=" * 50)