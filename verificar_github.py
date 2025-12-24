# verificar_github.py
import requests
import json

print("🔍 VERIFICANDO STATUS NO GITHUB")
print("="*60)

# URL do arquivo no GitHub
github_url = "https://raw.githubusercontent.com/diegoperira238-hash/foodcost-erp-v2/main/templates/config_admin.html"

try:
    print(f"1. Baixando template do GitHub...")
    response = requests.get(github_url, timeout=10)
    
    if response.status_code == 200:
        content = response.text
        
        # Verificar se tem a correção
        if "sum(attribute='max_maquinas') or 0" in content:
            print("✅ Template CORRIGIDO no GitHub!")
        elif "sum(attribute='max_maquinas')" in content:
            print("❌ Template SEM correção no GitHub!")
            print("   Precisa adicionar 'or 0'")
        else:
            print("⚠️  Não encontrou o padrão. Template diferente.")
        
        # Contar linhas
        lines = content.split('\n')
        print(f"📊 Template tem {len(lines)} linhas")
        
    else:
        print(f"❌ Erro ao acessar GitHub: {response.status_code}")
        
except Exception as e:
    print(f"❌ Erro: {e}")

print("\n🎯 AÇÕES NECESSÁRIAS:")
print("1. git add templates/config_admin.html")
print("2. git commit -m 'Fix template'")
print("3. git push origin main")
print("="*60)