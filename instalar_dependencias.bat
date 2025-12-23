@echo off
title Instalador FoodCost ERP - Suporte Comercial
echo.
echo ======================================================
echo   PREPARANDO AMBIENTE PARA O SISTEMA FOODCOST
echo ======================================================
echo.
echo 1. Atualizando o instalador de pacotes (PIP)...
python -m pip install --upgrade pip

echo.
echo 2. Instalando bibliotecas necessarias (Flask, DB, Servidor)...
pip install flask flask_sqlalchemy waitress

echo.
echo ======================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo   AGORA VOCE PODE ABRIR O EXECUTAVEL DO SISTEMA.
echo ======================================================
echo.
pause