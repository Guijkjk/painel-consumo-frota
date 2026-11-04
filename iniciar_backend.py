"""Inicia a API apenas neste computador; senha digitada fica na memoria do processo."""
import getpass
import os

import uvicorn


if __name__ == "__main__":
    os.environ["FROTA_DB_PASSWORD"] = getpass.getpass("Senha MySQL: ")
    print("Documentacao: http://127.0.0.1:8000/docs")
    print("Para encerrar: Ctrl+C")
    uvicorn.run("backend:app", host="127.0.0.1", port=8000, log_level="info")
