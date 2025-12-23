# verificar_limite.py
import sqlite3
from datetime import datetime

print("🔍 VERIFICAÇÃO DE LIMITE DO SISTEMA")
print("="*60)

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Contar lojas
c.execute('SELECT COUNT(*) FROM lojas')
total_lojas = c.fetchone()[0]

print(f"📊 TOTAL DE LOJAS: {total_lojas}/10")

if total_lojas > 10:
    print(f"❌ CRÍTICO: Sistema com {total_lojas} lojas! Excedeu limite em {total_lojas - 10}")
    
    # Listar todas as lojas
    c.execute('SELECT id, nome, ativo, licenca_ativa FROM lojas ORDER BY id')
    lojas = c.fetchall()
    
    print("\n📋 LISTA DE LOJAS (ordenadas por ID):")
    for i, loja in enumerate(lojas):
        status = "✅ ATIVA" if loja[2] else "❌ INATIVA"
        licenca = "🔑 ATIVA" if loja[3] else "🔒 BLOQUEADA"
        
        if i < 10:
            print(f"  {i+1:2d}. [MANTIDA] {loja[1]} (ID: {loja[0]}) | Loja: {status} | Licença: {licenca}")
        else:
            print(f"  {i+1:2d}. [EXCESSO] {loja[1]} (ID: {loja[0]}) | Loja: {status} | Licença: {licenca}")
    
    print(f"\n⚠️  RECOMENDAÇÃO:")
    print(f"   As lojas de 1 a 10 serão mantidas ativas")
    print(f"   As lojas de 11 a {total_lojas} serão BLOQUEADAS automaticamente")
    
    # Perguntar se quer bloquear automaticamente
    resposta = input("\n🚨 Deseja bloquear automaticamente as lojas excedentes? (s/n): ")
    
    if resposta.lower() == 's':
        # Bloquear lojas excedentes
        for i, loja in enumerate(lojas):
            if i >= 10:
                c.execute('''
                    UPDATE lojas 
                    SET ativo = 0, licenca_ativa = 0 
                    WHERE id = ?
                ''', (loja[0],))
                print(f"   ✅ Loja {loja[1]} (ID: {loja[0]}) BLOQUEADA")
        
        conn.commit()
        print(f"\n✅ {total_lojas - 10} lojas excedentes foram bloqueadas!")
        
elif total_lojas == 10:
    print("✅ SISTEMA NO LIMITE MÁXIMO (10/10)")
    print("   Não é possível criar novas lojas")
    
    c.execute('SELECT nome, ativo FROM lojas')
    for loja in c.fetchall():
        status = "✅ ATIVA" if loja[1] else "❌ INATIVA"
        print(f"   • {loja[0]} - {status}")
    
else:
    vagas = 10 - total_lojas
    print(f"✅ Vagas disponíveis: {vagas}")
    
    if vagas <= 2:
        print(f"⚠️  ATENÇÃO: Apenas {vagas} vaga(s) restante(s)!")

conn.close()

print("\n" + "="*60)
print("🎯 POLÍTICA DO SISTEMA:")
print("• Limite máximo: 10 lojas/licenças")
print("• Não será possível criar mais que isso")
print("• Tentativas serão bloqueadas automaticamente")
print("="*60)