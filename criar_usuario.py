# criar_usuario.py - Salve este arquivo na pasta
import sqlite3

print("🔧 CRIANDO USUÁRIO ADMIN...")

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Criar tabela se não existir
c.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    loja_id INTEGER
)
''')

# Apagar admin existente (se houver)
c.execute("DELETE FROM usuarios WHERE username='admin'")

# Criar novo admin
c.execute("INSERT INTO usuarios (username, password, role) VALUES ('admin', '123', 'admin')")

conn.commit()
conn.close()

print("✅ USUÁRIO CRIADO COM SUCESSO!")
print("🎯 AGORA USE:")
print("   Usuário: admin")
print("   Senha: 123")
print("\n👉 Execute: python app.py")