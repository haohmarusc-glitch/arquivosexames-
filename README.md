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
- `conflitos.json`: mesmo marcador e data com valores diferentes em laudos distintos (só um vai para o gráfico).

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

Para manter o frontend ativo apos reiniciar o VPS:

```bash
install -m 644 analisador-exames.service /etc/systemd/system/analisador-exames.service
systemctl daemon-reload
systemctl enable --now analisador-exames.service
```

## Painel novo (React + API)

Substitui o painel Streamlit. A API (`api.py`, FastAPI) le o `resultados.json` e serve o frontend compilado.

### No servidor

```bash
cd /opt/analisador-exames
.venv/bin/pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..
install -m 644 painel-exames.service /etc/systemd/system/painel-exames.service
systemctl daemon-reload
systemctl enable --now painel-exames.service
```

No computador: `ssh -L 8502:127.0.0.1:8502 root@SEU_IP` e acesse `http://localhost:8502`.

Depois de atualizar os PDFs, rode `executar_no_servidor.sh` de novo; a API recarrega o JSON sozinha.

### Desenvolvimento com dados ficticios

```bash
python exemplo/gerar_demo.py
ANALISADOR_RESULT_DIR=exemplo/demo uvicorn api:app --port 8502   # terminal 1
cd frontend && npm install && npm run dev                          # terminal 2
```

### Telas

- **Visao geral**: ultima coleta, marcadores fora da referencia, achados de imagem, grafico de evolucao e documentos recentes.
- **Evolucao**: todos os marcadores agrupados por sistema, grafico com a faixa de referencia e tabela de medicoes.
- **Anatomia**: figura com orgaos ligados aos exames de sangue, e vista de coluna e articulacoes com os achados dos laudos de imagem marcados por nivel (C5-C6, L4-L5...).
- **Documentos**: catalogo filtravel.

### Achados de imagem

O analisador copia a conclusao ("Impressao diagnostica", "Conclusao") dos laudos de RM, TC, RX e USG, e detecta regiao, niveis vertebrais, lado e termos (hernia, protrusao, artrodese, estenose...). Negacoes como "sem compressao" sao ignoradas. O painel mostra o texto original com o arquivo de origem.

### Configuracao local (.env)

Algumas tabelas de referencia mudam por sexo e idade (testosterona, LH, estradiol...). A idade e lida do laudo; o sexo vem de `/opt/analisador-exames/.env` (fora do Git):

```bash
echo "ANALISADOR_SEXO=M" > /opt/analisador-exames/.env
chmod 600 /opt/analisador-exames/.env
```

Sem essa configuracao, esses exames aparecem como "sem referencia" em vez de usar a faixa errada.

### Registros manuais

Para diagnosticos ou cirurgias que nao estao em laudo de imagem, crie `achados_manuais.json` **na pasta de resultados do servidor** (`/srv/saude/painel`), nunca no repositorio. Modelo em `exemplo/achados_manuais.exemplo.json`. Campos:

| Campo | Exemplo |
|---|---|
| `titulo` | "Artroscopia" |
| `regiao` | cervical, toracica, lombar, sacral, ombro, cotovelo, punho_mao, quadril, joelho, tornozelo_pe |
| `niveis` | ["L4-L5"] (so coluna) |
| `lado` | direito, esquerdo, bilateral |
| `data` | "2021-08-15" |
| `tipo` | "cirurgia" |
| `descricao` | texto livre |
| `fonte` | "Relatorio cirurgico" |

### Normalizacao de exames

`mapa_exames.py` agrupa grafias diferentes ("COLESTEROL LDL", "LDL-COLESTEROL") e liga cada exame a um sistema do corpo. Se um exame aparecer em "Outros", acrescente os padroes dele la.

## Limites

Numeros: virgula e decimal; ponto com grupos de 3 digitos ("6.500") e milhar; demais pontos ("5.0") sao decimais.

PDFs digitalizados como imagem podem exigir OCR. Intervalos de referencia variam por laboratorio, idade, sexo e contexto. Confirme qualquer achado no documento original e com o profissional assistente.

### Publicar em saude.premercadosc.com (Docker + Caddy)

O painel roda como container na mesma rede Docker (`premercado_default`) do Caddy que ja serve premercadosc.com, sem publicar porta nenhuma no host — o container so e alcancavel de dentro dessa rede.

```bash
cd /opt/analisador-exames
docker build -t saude-exames:latest .
docker run -d --name saude-app --restart unless-stopped \
  --network premercado_default \
  -e ANALISADOR_RESULT_DIR=/data \
  -e ANALISADOR_NOME=Jefferson \
  -e ANALISADOR_SEXO=M \
  -e ANALISADOR_UPLOAD_DIR=/uploads \
  -v /srv/saude/painel:/data:ro \
  -v /srv/saude/uploads:/uploads \
  saude-exames:latest
```

### Envio de PDFs pelo painel

Em **Documentos → Enviar exames** dá para arrastar laudos em PDF. A API roda o
mesmo analisador (`analisar_exames.analisar_pdf`) e grava o resultado em
`/srv/saude/uploads/resultados_upload.json` (os PDFs ficam em
`/srv/saude/uploads/pdfs/`, permissão 600). O `resultados.json` principal
continua somente leitura; a API junta os dois na leitura e ignora um envio que
o analisador principal ja tenha (mesmo sha256, mesmo texto ou mesmo nome).
Cada marcador vai para o sistema definido em `mapa_exames.py`, e a tela mostra
para onde foi cada exame. "Desfazer" remove só o que foi enviado pelo painel.

Antes de recriar o container: `install -d -m 700 /srv/saude/uploads`.
Sem `ANALISADOR_UPLOAD_DIR` o envio fica desligado (a caixa explica isso).
Para ter cópia no Drive, inclua no cron algo como
`rclone copy /srv/saude/uploads saude-crypt:exames/enviados-pelo-painel`.

Depois que `./executar_no_servidor.sh` atualiza `/srv/saude/painel/resultados.json`, o container ve a mudanca sozinho (volume montado, sem precisar reiniciar).

No `/opt/premercado/Caddyfile`, acrescente um bloco `saude.{$DOMINIO}` com `basic_auth` (gere o hash com `docker run --rm -it caddy:2-alpine caddy hash-password`, nunca com `--plaintext` direto no comando) e `reverse_proxy saude-app:8502`, valide com `docker exec premercado-caddy-1 caddy validate --config /etc/caddy/Caddyfile` antes de `caddy reload`. Crie o registro DNS `saude` no Cloudflare com as mesmas opcoes do registro `kuma` existente.

## Imagens (visualizador DICOM)

A aba **Imagens** do painel lista os exames de imagem (raio-X, ressonância,
ultrassom) e abre cada um no visualizador **OHIF** (zoom, contraste, régua,
rolagem pelas fatias). As imagens ficam num **Orthanc** (servidor DICOM
open source) em container próprio, na mesma rede do Caddy, sem porta pública.

Privacidade: `importar_imagens.py` apaga nome, ID, nascimento, endereço,
atendimento e tags privadas de cada DICOM **antes** de enviar ao Orthanc. Texto
gravado nos pixels pelo aparelho (comum em ultrassom) não é removido — o site
continua atrás do `basic_auth`.

### 1. Subir o Orthanc

```bash
install -d -m 700 /srv/saude/orthanc
docker run -d --name saude-orthanc --restart unless-stopped \
  --network premercado_default \
  -p 127.0.0.1:8042:8042 \
  --memory 1g \
  -e ORTHANC__NAME=saude \
  -e ORTHANC__AUTHENTICATION_ENABLED=false \
  -e ORTHANC__REMOTE_ACCESS_ALLOWED=true \
  -e ORTHANC__DICOM_SERVER_ENABLED=false \
  -e ORTHANC__STORAGE_COMPRESSION=true \
  -e DICOM_WEB_PLUGIN_ENABLED=true \
  -e OHIF_PLUGIN_ENABLED=true \
  -e ORTHANC__DICOM_WEB__HOST=saude.premercadosc.com \
  -e ORTHANC__DICOM_WEB__SSL=true \
  -v /srv/saude/orthanc:/var/lib/orthanc/db \
  orthancteam/orthanc:latest
curl -s http://127.0.0.1:8042/system | head   # deve responder JSON
```

A porta 8042 fica só em 127.0.0.1 (para o importador); a internet só chega
pelo Caddy, e só às rotas de leitura (`/ohif/*`, `/dicom-web/*`, método GET).
Sem autenticação no Orthanc de propósito: ele não é alcançável de fora.

### 2. Ligar a aba no painel

Recrie o `saude-app` com mais uma variável:

```bash
-e ORTHANC_URL=http://saude-orthanc:8042
```

### 3. Caddy

Dentro do bloco `saude.{$DOMINIO}` existente (depois do `basic_auth`,
junto do `reverse_proxy saude-app:8502`):

```caddy
	@imagens {
		path /ohif /ohif/* /dicom-web/*
		method GET HEAD
	}
	handle @imagens {
		reverse_proxy saude-orthanc:8042
	}
```

Valide com `docker exec premercado-caddy-1 caddy validate --config /etc/caddy/Caddyfile` e faça `caddy reload`.

### 4. Importar os zips

```bash
.venv/bin/pip install pydicom
.venv/bin/python importar_imagens.py /srv/saude/imagens/Exame_2025-10-31_US_Articular.zip --simular   # só testa
```

O disco do VPS é pequeno: importe um zip por vez, guarde o original no Drive
criptografado e apague a cópia local:

```bash
for z in /srv/saude/imagens/*.zip; do
  .venv/bin/python importar_imagens.py "$z" \
    && rclone copy "$z" saude-crypt:imagens/originais \
    && rm "$z"
  df -h /srv | tail -1
done
```

Reimportar o mesmo zip não duplica nada.

### Baixar e imprimir

- **Documentos**: cada laudo com PDF guardado no servidor mostra "Abrir /
  imprimir" (abre no navegador; imprima por lá) e "Baixar PDF". Os enviados pela
  caixa ficam em `/srv/saude/uploads/pdfs`. Para os do analisador principal,
  deixe os PDFs numa pasta e monte no container:
  `-v /srv/saude/laudos:/laudos:ro -e ANALISADOR_PDF_DIR=/laudos`
  (varias pastas: separe com `:`).
- **Imagens**: "Baixar" gera o zip DICOM do exame (já anonimizado);
  "Imprimir" abre uma página com as imagens em grade (escolha série e imagens
  por linha; "Salvar como PDF" na janela de impressão também funciona).
