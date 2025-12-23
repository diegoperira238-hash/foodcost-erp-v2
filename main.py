import threading
import webbrowser
import time
from FoodCost_Ultimate_ERP_v8.app1 import app, init_db

def open_browser():
    # Espera 1.5 segundos para garantir que o Flask subiu
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == "__main__":
    init_db()
    # O daemon=True garante que a thread feche se o programa principal fechar
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(port=5000, debug=False)
