# arquivosexames- — contexto para Claude Code

Painel privado que le laudos em PDF (Unimed) e extrai valores laboratoriais e
achados de laudos de imagem (coluna, articulacoes). Uso pessoal do Jefferson.

## Stack
- `analisar_exames.py` + `achados.py` + `mapa_exames.py`: extracao dos PDFs (Python, pypdf).
- `api.py`: FastAPI, serve `/api/*` e o frontend compilado. Leitura do
  `resultados.json` + envio opcional de PDFs (`POST /api/upload`, grava em
  `ANALISADOR_UPLOAD_DIR/resultados_upload.json`, mesclado na leitura).
  O sistema de cada marcador e recalculado a partir do titulo na leitura, entao
  mudar `mapa_exames.py` vale sem rodar o analisador de novo.
- `frontend/`: React + TypeScript + Vite + Tailwind + Recharts (`npm run build` gera `frontend/dist`).
- `test_analisador.py`: testes (`.venv/bin/python -m unittest`), rode sempre antes de aplicar no VPS.

## Deploy (producao)
- Roda como container Docker `saude-app` na rede `premercado_default` (mesma do
  Premercado), SEM publicar porta no host — so o Caddy alcanca via nome do container.
- Reconstruir apos mudanca: `docker build -t saude-exames:latest .` depois
  `docker stop saude-app && docker rm saude-app` e recriar (ver README.md, secao
  "Publicar em saude.premercadosc.com").
- Exposto publicamente em `https://saude.premercadosc.com`, atras de
  `basic_auth` no `/opt/premercado/Caddyfile` (usuario `jefferson`). DNS no
  Cloudflare, registro A `saude` -> IP do VPS, proxied (nuvem laranja).
- Continua existindo tambem um `painel-exames.service` (systemd) escutando so
  em 127.0.0.1:8502, para acesso por tunel SSH direto, sem depender do Caddy.
- Dados ficam em `/srv/saude/painel/resultados.json` (gerado por
  `executar_no_servidor.sh`, que baixa o zip do rclone, roda o analisador e
  criptografa o resultado). Nunca commitar esse arquivo nem os PDFs.
- `executar_no_servidor.sh` tambem copia `/srv/saude/uploads/pdfs` para
  `saude-crypt:exames/enviados/` (so `rclone copy`, nunca `sync`: perder o disco
  nao pode apagar o backup) e passa a pasta ao analisador com `--enviados`
  (`ExamFile.origem="envio"`). A API esconde envio cujo PDF sumiu da pasta.
- `.env` (fora do Git) pode ter `ANALISADOR_SEXO=M`, usado para escolher a
  faixa certa em tabelas de referencia que variam por sexo/idade.

## Anatomia com imagens reais (frente + costas)

A tela Anatomia > Orgaos usa fotos/ilustracoes reais (webp) em vez de SVG
desenhado a mao, em `frontend/public/anatomia/` (frente) e
`frontend/public/anatomia/costas/` (vista posterior). Geradas por um Claude
Code separado com uma ferramenta de imagem que esta sessao de chat nao tem.

- `formasCorpo.ts`: `ORGAOS_FRENTE` (orgaos clicaveis, ligados a `sistema` do
  mapa_exames), `DECORATIVOS_FRENTE` (pulmoes/estomago/intestino/bexiga, sem
  clique), `ORGAOS_COSTAS` (so os rins, clicaveis — posicao anatomica real).
  Cada item tem uma `caixa` (x,y,w,h no viewBox) onde a imagem e "contida"
  sem distorcer; o clique e uma elipse do tamanho da caixa, nao a imagem.
- Corrigido um bug real do codigo anterior: os IDs `rimD`/`rimE` estavam com
  a lateralidade trocada. Na vista de FRENTE, rim direito da pessoa fica a
  ESQUERDA da tela; na vista de COSTAS essa relacao se INVERTE (rim direito
  fica a direita da tela). As duas vistas tem `caixa` calibradas
  separadamente — nao reusar coordenadas de uma vista na outra.
- Vista de Costas (fundo = `costas/orgaos-costas.webp`): figado, baco, rins,
  suprarrenais, bexiga e prostata clicaveis, caixas medidas numa grade do
  viewBox (formula em `formasCorpo.ts`). Coracao, pancreas, tireoide e
  testiculos nao aparecem nessa imagem.
- Quando ha achado de imagem com regiao `renal` (calculo renal), o painel
  mostra `costas/rins-corte-calculos.webp` com aviso de que e esquematico
  (nao reproduz posicao/quantidade reais).
- Coluna cervical/lombar mostram uma imagem de apoio
  (`costas/coluna-cervical-detalhe.webp` / `coluna-lombossacra-detalhe.webp`)
  ao lado da lista de achados — o esqueleto SVG (calibrado, ja testado)
  continua sendo a figura interativa principal; NAO foi substituido pela
  imagem `esqueleto-costas.png` (fica para depois, precisa recalibrar todas
  as vertebras/articulacoes contra a imagem nova).
- Pendente (deliberadamente adiado, nao é bug): vesicula/regiao escrotal/
  parede abdominal na vista de costas (nao visiveis na imagem); troca do esqueleto da Coluna pela imagem nova; vistas alternativas
  por sistema (venoso, arterial, muscular, nervoso, linfatico — existem
  arquivos prontos em `imagens-anatomia/camadas/` e `costas/` fora do repo,
  nao processados ainda).

## Imagens de anatomia novas (2026-09)
- `orgaos-frente.webp` e `costas/orgaos-costas.webp` trocadas por uma ilustracao
  nova, SEM texto (as duas vistas vieram numa imagem so; recortadas, centradas
  na linha media e reduzidas para caber inteiras com as maos, 700x1734 com
  fundo transparente). A vista de costas veio com figado/baco do lado errado e
  foi ESPELHADA (de costas, figado a direita da tela).
- Todas as caixas de `ORGAOS_FRENTE`, `ORGAOS_COSTAS` e `PULMOES_FRENTE` foram
  medidas de novo numa grade do viewBox (vx = 30.819 + px*0.36909,
  vy = 8 + py*0.36909), com area minima de 10x10 para toque no celular.
- A secao abaixo descreve a calibracao da imagem ANTERIOR (so historico).

## Auditoria da anatomia (2026-09)
- Caixas de `ORGAOS_FRENTE` recalibradas com uma grade do viewBox desenhada
  sobre `orgaos-frente.webp` (vx = 30.145 + px*0.37101, vy = 8 + py*0.37101).
- Novos hotspots: hipófise e suprarrenais (hormonios), baço (sangue), bexiga
  (rins), próstata, testículos (novo sistema `testiculos`, espermograma).
  `tambem: ['proteinas']` no fígado destaca-o na aba Proteínas.
- Camadas: bexiga subiu para trás da sínfise púbica, intestinos encurtados,
  rim direito mais baixo, coração deslocado para a esquerda da pessoa,
  `AORTA_CAMADAS` refeita sobre `esqueleto-frontal.webp`.
- Vista de costas com figado, baco, rins, suprarrenais, bexiga e prostata.

## Cuidados importantes (ja corrigidos, nao regredir)
- **Privacidade**: nome, CPF e data de nascimento do paciente NUNCA podem
  aparecer no `resultados.json` nem na API. Ja houve um vazamento por um `\b`
  quebrado numa regex de corte de rodape — qualquer mudanca em
  `reference_near()` (analisar_exames.py) ou `conclusao()`/`FIM_SECAO_RE`
  (achados.py) precisa ser testada contra vazamento (ver testes existentes e
  rode uma busca pelo nome no JSON gerado).
- **PDFs duplicados**: o portal da Unimed as vezes salva o mesmo laudo com
  nomes de arquivo diferentes. O analisador detecta pelo hash do TEXTO
  extraido (nao dos bytes) e ignora repetidos — nao reverter para hash de
  bytes.
- **Classificacao por conteudo, nao por nome de arquivo**: um PDF chamado
  "Rm_Coluna_Cervical.pdf" pode conter exame de sangue. `classify_file()` le
  o conteudo primeiro.
- **Datas**: prioriza datas com rotulo (Entrada/Coleta/Data do exame) sobre
  data solta no texto, e ignora "D.N." (data de nascimento).
- **Repositorio GitHub**: ficou publico temporariamente para eu (Claude via
  chat) conseguir clonar. Se ainda estiver publico, considere voltar para
  privado.

## Regras da serie dos graficos (`consolidar()` em analisar_exames.py)
Roda no analisador E na API (sobre o JSON + envios), e idempotente:
- Leucocitos/hemacias de EAS/sedimento/urocultura (material do bloco ou unidade
  /mL, /campo, UFC) viram `urina_leucocitos`/`urina_hemacias`. Ponto sem unidade
  numa serie com unidade dominante fica fora do grafico (`grafico=false`).
- Rotulo generico ("Indice") vira "<TITULO> - Indice" (id `<exame>_indice`);
  sem titulo nas linhas acima, fica fora do grafico.
- (marcador, data, valor) repetido vira um registro com `arquivos` = todos os PDFs;
  valores diferentes na mesma data vao para `conflitos.json` (`/api/conflitos`)
  e so um fica no grafico.
- `/api/marcadores/{id}` traz `conflitos` da serie; a tela Evolucao mostra as
  datas com mais de um valor (e a hora de cada coleta) abaixo do grafico.
- `mapa_exames.NAO_MARCADORES`: contagens tecnicas (metafases do cariotipo) ficam
  na tabela, fora do grafico. Sistema `sorologias` (sifilis, HIV, toxo...) nao tem
  orgao na Anatomia (`naoOrgao` em Anatomia.tsx).
- `classificacao` sai SO de `ref_min`/`ref_max` (faixas que discordam -> ambos None).
- Unidade: `unidade_valida()` rejeita texto do laudo; senao a da referencia; por
  ultimo `UNIDADE_PADRAO` (`unidade_fonte="padrao"`, so exibicao).

- `verificar_graficos.py` confere a API como o grafico a ve (datas repetidas,
  unidades misturadas, nome generico, classificacao x limites, discrepantes).
  Rodar depois de recriar o container:
  `docker cp verificar_graficos.py saude-app:/tmp/ && docker exec saude-app python3 /tmp/verificar_graficos.py --base http://localhost:8502`

## Patologias da coluna desenhadas (frontend/src/patologias.ts)
- O achado traz niveis e termos separados; `patologiasDoTrecho` le o trecho do
  laudo frase por frase e so marca quando termo e nivel estao na MESMA frase
  (lado: esquerdo/direito/bilateral/central; negacao "sem hernias" ignorada).
  ESTADO ATUAL: em cada regiao da coluna (e cada articulacao/lado) so o laudo
  MAIS RECENTE vale para o desenho (`maisRecentesPorRegiao`); uma patologia que
  melhorou ou sumiu no exame novo nao fica desenhada. O historico continua na
  lista de laudos ao lado.
  Artrodese: faixa de vertebras ("L4-S1", "L4 a S1", "parafusos em L4, L5 e S1")
  -> todos os discos da faixa. Fratura: a vertebra ("T12").
- Figura da coluna (Anatomia.tsx `GlifosColuna`): de FRENTE o lado esquerdo da
  pessoa fica a direita da tela; de COSTAS, a esquerda. Etiquetas empilhadas e
  desenhadas por ultimo (por cima dos circulos dos ombros).
- Imagens de detalhe (AnatomiaPage `DetalheComPatologias`): `DISCOS_DETALHE` e
  `PEDICULOS_DETALHE` em % da imagem (vistas de costas).

## Testar antes de aplicar
```bash
.venv/bin/python -m unittest
cd frontend && npm run build && cd ..
```

## Imagens DICOM (Orthanc + OHIF)
- Container `saude-orthanc` (orthancteam/orthanc, plugins DicomWeb + OHIF) na
  rede `premercado_default`, porta 8042 so em 127.0.0.1, dados em
  `/srv/saude/orthanc`. Caddy repassa so GET/HEAD de `/ohif/*` e `/dicom-web/*`.
- `importar_imagens.py` ANONIMIZA (pydicom) antes de enviar — nao enviar DICOM
  ao Orthanc por outro caminho (ex.: upload pela UI /ui do Orthanc), senao o
  nome do paciente vai junto. Texto queimado nos pixels nao e removido.
- API: `GET /api/imagens` (precisa `ORTHANC_URL` no saude-app); frontend
  `pages/Imagens.tsx`. Disco do VPS e pequeno: importar zip a zip e apagar.
- Baixar/imprimir: `GET /api/documentos/{arquivo}/pdf[?baixar=true]` (so PDFs
  indexados em `PDF_DIRS` = uploads/pdfs + `ANALISADOR_PDF_DIR`; o PDF original
  tem nome do paciente, mas e o arquivo dele, atras do basic_auth);
  `/api/imagens/{id}/series`, `/api/imagens/instancia/{id}.png` (preview do
  Orthanc), `/api/imagens/{id}/zip` (archive). IDs validados por regex.
  Pagina `#/imprimir?estudo=` (menu some com `print:hidden`).
- `importar_imagens.py` pula DICOMDIR (indice do CD) — enviar ao Orthanc dava
  404 "Inexistent tag".

## Data do laudo e laudos bilaterais
- `first_date`: data rotulada (exame/coleta/atendimento) > "LIBERADO EM:" > data no nome do arquivo > primeira data solta. Nas datas soltas, ignora a que vem ate 150 caracteres depois de um rotulo de nascimento (o rotulo pode estar separado da data por outras linhas do cabecalho).
- `achados.secoes_por_lado`: laudo com titulos "... DIREITO" e "... ESQUERDO" sozinhos na linha, cada um com sua conclusao (ex.: Doppler das duas pernas), vira um achado por lado. PDF repetido nao duplica.
- Regiao `membros_inferiores` (safena, varizes, membro inferior) e termos `insuficiencia_venosa`/`trombose`.
- `auditar_laudos.py resultados.json` lista arquivos com data suspeita, sem texto, regiao "outros", articulacao sem lado, etc. Imprime so nome do arquivo e o motivo.
