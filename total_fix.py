# total_fix.py
import os
from app import app, db
from sqlalchemy import text

print(" CORREÇÃO TOTAL DO BANCO POSTGRESQL")
print("="*60)

with app.app_context():
    # Verificar se estamos no PostgreSQL do Render
    db_url = os.environ.get('DATABASE_URL', '')
    print(f"Banco: {db_url}")
    
    if 'postgresql' not in db_url.lower():
        print("❌ Não é PostgreSQL. Saindo...")
        exit()
    
    try:
        # Colunas que DEVEM existir na tabela maquinas
        required_columns = [
            ('observacoes', 'TEXT'),
            ('data_cadastro', 'TIMESTAMP')
        ]
        
        for column_name, column_type in required_columns:
            # Verificar se a coluna existe
            check_sql = f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'maquinas' 
                AND column_name = '{column_name}'
            """
            
            result = db.session.execute(text(check_sql))
            
            if not result.fetchone():
                print(f" Adicionando coluna: {column_name} ({column_type})")
                alter_sql = f"ALTER TABLE maquinas ADD COLUMN {column_name} {column_type}"
                db.session.execute(text(alter_sql))
            else:
                print(f" Coluna já existe: {column_name}")
        
        db.session.commit()
        print(" BANCO CORRIGIDO COM SUCESSO!")
        
    except Exception as e:
        print(f" ERRO: {e}")
        db.session.rollback()
        print(" SOLUÇÃO ALTERNATIVA: Recrie o banco no Render Dashboard")
