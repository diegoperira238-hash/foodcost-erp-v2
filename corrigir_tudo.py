import psycopg2
import sys

# SUA SENHA (você já compartilhou, mas altere depois!)
SENHA = "9xt0XsOw9frem7aGcFlkIcyLmKS3jPU7"
DATABASE_URL = f"postgresql://postgresqldatabese:{SENHA}@dpg-d54q6fali9vc73em62b0-a.frankfurt-postgres.render.com/foodcost_ultimate_erp_v8_postegree"

print("="*60)
print(" CORRIGINDO SISTEMA FOODCOST ERP")
print("="*60)

try:
    # 1. Conectar ao banco
    print("1.  Conectando ao PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("    Conectado!")
    
    # 2. Verificar tabelas
    print("\n2.  Verificando tabelas...")
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    
    tabelas = cursor.fetchall()
    print(f"    {len(tabelas)} tabelas encontradas:")
    for tabela in tabelas:
        print(f"       {tabela[0]}")
    
    # 3. Verificar usuário bpereira
    print("\n3.  Verificando usuário 'bpereira'...")
    cursor.execute("SELECT id, username, password, role FROM usuarios WHERE username = 'bpereira';")
    usuario = cursor.fetchone()
    
    if usuario:
        print(f"    Usuário encontrado:")
        print(f"      ID: {usuario[0]}")
        print(f"      Username: {usuario[1]}")
        print(f"      Senha atual: {usuario[2]}")
        print(f"      Role: {usuario[3]}")
        
        # Verificar se senha está correta
        if usuario[2] != 'chef@26':
            print(f"     Senha incorreta! Resetando...")
            cursor.execute("UPDATE usuarios SET password = 'chef@26' WHERE username = 'bpereira';")
            conn.commit()
            print(f"    Senha alterada para: chef@26")
        else:
            print(f"    Senha já está correta: chef@26")
            
    else:
        print("    Usuário não encontrado! Criando...")
        
        # Verificar se há loja
        cursor.execute("SELECT id, nome FROM lojas LIMIT 1;")
        loja = cursor.fetchone()
        
        if loja:
            loja_id = loja[0]
            loja_nome = loja[1]
            print(f"    Loja encontrada: {loja_nome} (ID: {loja_id})")
        else:
            # Criar loja se não existir
            cursor.execute("INSERT INTO lojas (nome, ativo, licenca_ativa) VALUES ('Loja Principal', true, true) RETURNING id;")
            loja_id = cursor.fetchone()[0]
            loja_nome = 'Loja Principal'
            print(f"    Loja criada: {loja_nome} (ID: {loja_id})")
        
        # Criar usuário
        cursor.execute("""
            INSERT INTO usuarios (username, password, role, loja_id) 
            VALUES ('bpereira', 'chef@26', 'admin', %s)
            RETURNING id;
        """, (loja_id,))
        
        novo_id = cursor.fetchone()[0]
        conn.commit()
        print(f"    Usuário criado:")
        print(f"      ID: {novo_id}")
        print(f"      Username: bpereira")
        print(f"      Senha: chef@26")
        print(f"      Role: admin")
        print(f"      Loja: {loja_nome}")
    
    # 4. Verificar resultado final
    print("\n4.  Verificação final...")
    cursor.execute("SELECT username, password, role FROM usuarios WHERE username = 'bpereira';")
    resultado = cursor.fetchone()
    
    if resultado:
        print(f"    USUÁRIO CONFIGURADO:")
        print(f"       Login: {resultado[0]}")
        print(f"       Senha: {resultado[1]}")
        print(f"       Role: {resultado[2]}")
    else:
        print("    ERRO: Usuário não encontrado após criação!")
    
    # 5. Contar registros
    print("\n5.  Estatísticas do banco:")
    cursor.execute("SELECT COUNT(*) FROM usuarios;")
    total_usuarios = cursor.fetchone()[0]
    print(f"    Total usuários: {total_usuarios}")
    
    cursor.execute("SELECT COUNT(*) FROM lojas;")
    total_lojas = cursor.fetchone()[0]
    print(f"    Total lojas: {total_lojas}")
    
    cursor.execute("SELECT COUNT(*) FROM fichas;")
    total_fichas = cursor.fetchone()[0]
    print(f"    Total fichas: {total_fichas}")
    
    conn.close()
    
    print("\n" + "="*60)
    print(" SISTEMA PRONTO PARA USO!")
    print("="*60)
    print("\n ACESSE AGORA:")
    print("   URL: https://foodcost-erp.onrender.com")
    print("    Usuário: bpereira")
    print("    Senha: chef@26")
    print("\n  ALERTA DE SEGURANÇA:")
    print("    SUA SENHA FOI EXPOSTA PUBLICAMENTE!")
    print("    Altere-a no Render Dashboard AGORA!")
    print("="*60)
    
except Exception as e:
    print(f"\n ERRO CRÍTICO: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n SOLUÇÕES:")
    print("1. Verifique se a senha está correta")
    print("2. Verifique se o PostgreSQL está ativo no Render")
    print("3. Teste a conexão manualmente")
    
    input("\nPressione Enter para sair...")
    sys.exit(1)
