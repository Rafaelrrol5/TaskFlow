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

## Publicar uma atualização

1. Altere o número do arquivo `VERSION`, usando o formato `1.2.3`.
2. Envie a alteração para a branch `main`.
3. O GitHub Actions gera o aplicativo e publica automaticamente o ZIP na página de Releases.

Os bancos dos usuários ficam fora da pasta do programa e são preservados durante a atualização.

## Privacidade

O repositório não contém bancos de dados, contas, senhas, backups, logs ou chaves gerados durante o uso. Esses arquivos são ignorados pelo Git.

## Prompts utilizados

Os prompts abaixo são versões resumidas das instruções utilizadas durante o desenvolvimento com apoio de inteligência artificial.

### 1. Criação do backend

> Crie o backend de uma lista de tarefas em Python utilizando Flask, SQLite e SQLAlchemy. Implemente endpoints para criar, editar, excluir, concluir, listar e filtrar tarefas. Adicione validações de título, prioridade, status e datas. Trabalhe somente no backend nesta etapa.

### 2. Criação do frontend

> Crie um frontend moderno e responsivo para a lista de tarefas utilizando HTML, CSS e JavaScript puro. Faça um dashboard com resumo das tarefas, pesquisa, filtros, cards, modal de cadastro e integração com a API por meio de fetch.

### 3. Detalhes das tarefas

> Mantenha os cards compactos e abra um modal ao clicar em uma tarefa. Mostre o título, a descrição completa, categoria, prioridade, status e datas. Reutilize as funções existentes de editar, concluir e excluir.

### 4. Revisão de segurança

> Analise o backend e o frontend, corrija riscos reais de XSS, valide os dados recebidos, rejeite campos desconhecidos, proteja as respostas de erro e adicione configurações e headers básicos de segurança sem alterar as funcionalidades existentes.

### 5. Aplicativo para Windows

> Transforme o TaskFlow em um aplicativo executável para Windows. Utilize Waitress, pywebview e PyInstaller, mantenha o banco fora da pasta do programa e prepare uma build estável que funcione sem o usuário instalar Python.

## O que aprendi

Durante o desenvolvimento do TaskFlow, aprendi que a inteligência artificial apresenta resultados melhores quando recebe um prompt claro, organizado e detalhado. Informar o objetivo, as tecnologias, as regras, as validações e aquilo que não deve ser feito facilita bastante o trabalho e evita alterações desnecessárias.

Também aprendi que dividir um projeto em etapas — primeiro backend, depois frontend, segurança, testes e empacotamento — torna o desenvolvimento mais simples e permite conferir cada parte antes de continuar.

Percebi que não basta apenas pedir para a IA criar um sistema. É importante analisar o código gerado, testar as funcionalidades, comunicar os erros encontrados e solicitar correções específicas. A IA funciona como uma ferramenta de apoio, mas as decisões, a revisão e a validação do resultado continuam sendo responsabilidade de quem desenvolve o projeto.

Com este trabalho, também tive contato com APIs REST, banco de dados SQLite, Flask, SQLAlchemy, HTML, CSS, JavaScript, GitHub, criação de executáveis e publicação automática de novas versões com GitHub Actions.

