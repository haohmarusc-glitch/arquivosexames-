# Analisador local de exames

Ferramenta local em Python para catalogar laudos PDF, extrair resultados laboratoriais e criar uma linha do tempo em CSV, JSON e Markdown.

## Privacidade

- Os PDFs permanecem no computador ou servidor onde o programa e executado.
- Nunca coloque PDFs, DICOMs, ZIPs, resultados ou credenciais no Git.
- O relatorio omite identificadores pessoais por padrao.
- A ferramenta organiza dados; nao diagnostica nem substitui avaliacao medica.

## Instalacao

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No Windows PowerShell, ative com:

```powershell
.venv\Scripts\Activate.ps1
```

## Uso

```bash
python analisar_exames.py /caminho/dos/pdfs --saida ./resultado
```

Arquivos produzidos:

- `catalogo.csv`: um registro por PDF.
- `resultados.csv`: resultados laboratoriais encontrados.
- `resultados.json`: dados estruturados completos.
- `resumo.md`: linha do tempo e itens fora do intervalo informado no laudo.

Para analisar um ZIP sem extrair manualmente:

```bash
python analisar_exames.py Exames_Unimed_2023-2026.zip --saida ./resultado
```

## Git seguro

O `.gitignore` bloqueia formatos médicos e arquivos de saída. Antes de cada commit, confira:

```bash
git status --short
```

## Execucao no servidor

O computador pessoal nao precisa ficar ligado. Clone o repositorio privado no VPS e execute o script `executar_no_servidor.sh`. Ele:

1. baixa temporariamente o ZIP do remoto criptografado;
2. executa a analise local;
3. envia os relatorios de volta para `saude-crypt:historico/`;
4. apaga os dados temporarios ao terminar.

```bash
chmod 700 executar_no_servidor.sh
./executar_no_servidor.sh
```

Para agendar uma execucao mensal no servidor:

```bash
crontab -e
```

Exemplo, todo dia 1 as 03:00:

```cron
0 3 1 * * cd /opt/analisador-exames && /opt/analisador-exames/executar_no_servidor.sh >> /var/log/analisador-exames.log 2>&1
```

## Painel web privado

O frontend roda no VPS, ligado somente ao endereco local do servidor:

```bash
ANALISADOR_RESULT_DIR=/srv/saude/painel ./iniciar_frontend.sh
```

No computador, crie um tunel privado:

```powershell
ssh -L 8501:127.0.0.1:8501 root@SEU_IP
```

Enquanto a janela SSH estiver aberta, acesse `http://localhost:8501`. O painel nao fica exposto diretamente na internet.

## Limites

PDFs digitalizados como imagem podem exigir OCR. Intervalos de referencia variam por laboratorio, idade, sexo e contexto. Confirme qualquer achado no documento original e com o profissional assistente.
