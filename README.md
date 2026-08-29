# TaskFlow

Aplicativo de lista de tarefas para Windows, desenvolvido em Python com Flask, SQLite e SQLAlchemy.

## Funcionalidades

- Cadastro, edição, conclusão, arquivamento e exclusão de tarefas
- Prioridades, categorias, prazos e identificação de tarefas atrasadas
- Pesquisa, filtros, calendário e visão de tarefas do dia
- Contas locais para separar as tarefas de cada usuário
- Exportação e restauração de backup
- Interface desktop responsiva

## Baixar para Windows

1. Acesse a página de [Releases](https://github.com/Rafaelrrol5/TaskFlow/releases/latest).
2. Baixe `TaskFlow-Windows-v1.0.0.zip`.
3. Extraia o arquivo ZIP completo.
4. Abra a pasta `TaskFlow` e execute `TaskFlow.exe`.

Não mova somente o executável: a pasta `_internal` precisa permanecer ao lado dele.

Os dados pessoais não acompanham o aplicativo. Cada instalação cria seu próprio banco em `%LOCALAPPDATA%\TaskFlow\taskflow.db`.

## Executar o código-fonte

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe desktop.py
```

Para executar somente como aplicação web:

```powershell
.\.venv\Scripts\python.exe app.py
```

## Gerar uma nova versão para Windows

```powershell
.\build.bat
```

O executável será criado em `dist\TaskFlow\TaskFlow.exe`.

## Privacidade

O repositório não contém bancos de dados, contas, senhas, backups, logs ou chaves gerados durante o uso. Esses arquivos são ignorados pelo Git.

