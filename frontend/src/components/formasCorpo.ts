// Formas do corpo em coordenadas do viewBox "40 8 240 640".
// Vista FRONTAL: o lado direito da pessoa aparece a ESQUERDA de quem olha.
// Vista de COSTAS: o lado direito da pessoa aparece a DIREITA de quem olha
// (a relacao se inverte, como e' natural ao ver alguem de costas).
export const CORPO = "M160,18 C182,18 196,36 196,58 C196,80 186,95 173,101 C173,108 173,114 174,119 C180,127 200,131 222,136 C240,141 248,156 249,176 C252,230 257,300 261,360 C263,390 265,410 267,428 C270,445 262,458 254,452 C248,446 248,430 246,412 C240,360 233,300 225,240 C223,228 219,221 214,219 C213,262 207,320 211,360 C215,390 222,410 222,432 C222,500 213,570 209,610 C208,625 213,634 200,636 C188,637 183,632 183,620 C181,560 177,500 169,452 C166,444 163,442 160,442 C157,442 154,444 151,452 C143,500 139,560 137,620 C137,632 132,637 120,636 C107,634 112,625 111,610 C107,570 98,500 98,432 C98,410 105,390 109,360 C113,320 107,262 106,219 C101,221 97,228 95,240 C87,300 80,360 74,412 C72,430 72,446 66,452 C58,458 50,445 53,428 C55,410 57,390 59,360 C63,300 68,230 71,176 C72,156 80,141 98,136 C120,131 140,127 146,119 C147,114 147,108 147,101 C134,95 124,80 124,58 C124,36 138,18 160,18 Z"

/** Retangulo (x,y,largura,altura) dentro do viewBox onde cada imagem PNG/WEBP
 * e' desenhada, mantendo a proporcao original (a imagem fica centralizada e
 * "contida" nesse retangulo — object-fit: contain manual). O retangulo de
 * clique/selecao e' uma elipse inscrita nesse mesmo espaco. */
export interface Caixa { x: number; y: number; w: number; h: number }

export interface OrgaoImagem {
  id: string
  sistema: string
  nome: string
  arquivo: string // caminho a partir de /anatomia/
  tambem?: string[] // outros sistemas que tambem destacam este orgao (ex.: proteinas -> figado)
  caixa: Caixa
  proporcao: number // largura/altura da imagem original, para "contain"
}

// Orgaos clicaveis (tem exames de sangue associados) — vista de frente.
// Caixas medidas diretamente na imagem composta unica (orgaos-frente.webp,
// 700x1734, desenhada com "slice": vx = 30.819 + px*0.36909, vy = 8 + py*0.36909).
// Recalibradas em 2026-09 (imagem nova, sem texto) sobrepondo uma grade do viewBox.
// Itens sem imagem propria (arquivo '') aparecem so como area de clique.
// Areas com no minimo 10x10 no viewBox, para dar para tocar no celular.
export const ORGAOS_FRENTE: OrgaoImagem[] = [
  { id: 'hipofise', sistema: 'hormonios', nome: 'Hipófise', arquivo: '', proporcao: 1, caixa: { x: 155, y: 106, w: 10, h: 10 } },
  { id: 'tireoide', sistema: 'tireoide', nome: 'Tireoide', arquivo: '', proporcao: 1, caixa: { x: 152, y: 139, w: 16, h: 10 } },
  { id: 'coracao', sistema: 'coracao', nome: 'Coração', arquivo: '', proporcao: 1, caixa: { x: 149, y: 195, w: 28, h: 31 } },
  { id: 'figado', sistema: 'figado', tambem: ['proteinas'], nome: 'Fígado', arquivo: '', proporcao: 1, caixa: { x: 119, y: 224, w: 53, h: 34 } },
  { id: 'baco', sistema: 'sangue', nome: 'Baço', arquivo: '', proporcao: 1, caixa: { x: 190, y: 232, w: 10, h: 26 } },
  { id: 'pancreas', sistema: 'pancreas', nome: 'Pâncreas', arquivo: '', proporcao: 1, caixa: { x: 151, y: 251, w: 37, h: 16 } },
  // Rim DIREITO da pessoa fica a ESQUERDA da tela (vista de frente).
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: '', proporcao: 1, caixa: { x: 130, y: 259, w: 17, h: 22 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: '', proporcao: 1, caixa: { x: 177, y: 259, w: 16, h: 19 } },
  // Suprarrenais nao aparecem de frente (ficam atras): area no topo de cada rim.
  { id: 'adrenalD', sistema: 'hormonios', nome: 'Suprarrenal direita', arquivo: '', proporcao: 1, caixa: { x: 134, y: 251, w: 10, h: 10 } },
  { id: 'adrenalE', sistema: 'hormonios', nome: 'Suprarrenal esquerda', arquivo: '', proporcao: 1, caixa: { x: 180, y: 251, w: 10, h: 10 } },
  { id: 'bexiga', sistema: 'rins', nome: 'Bexiga', arquivo: '', proporcao: 1, caixa: { x: 146, y: 324, w: 25, h: 19 } },
  { id: 'prostata', sistema: 'prostata', nome: 'Próstata', arquivo: '', proporcao: 1, caixa: { x: 154, y: 344, w: 10, h: 10 } },
  // A ilustracao nao desenha a genitalia: area esquematica logo abaixo do pube.
  { id: 'testiculos', sistema: 'testiculos', nome: 'Testículos (região escrotal)', arquivo: '', proporcao: 1, caixa: { x: 154, y: 354, w: 12, h: 10 } },
]

// Recorte (dentro da propria imagem composta) usado so para a animacao de
// respiracao via clip-path — nao sao clicaveis, nao tem sistema associado.
export const PULMOES_FRENTE = {
  pulmaoD: { x: 119, y: 169, w: 34, h: 60 },
  pulmaoE: { x: 173, y: 169, w: 31, h: 60 },
}

// --- Vista de COSTAS -------------------------------------------------------
// Imagem de corpo inteiro (fundo, costas/orgaos-costas.webp, 700x1734) com os
// orgaos visiveis clicaveis. Caixas medidas numa grade do viewBox desenhada
// sobre a imagem: vx = 30.819 + px*0.36909, vy = 8 + py*0.36909.
// Na vista de costas o lado DIREITO da pessoa fica a DIREITA da tela
// (figado e rim direito a direita; baco e rim esquerdo a esquerda).
// A ilustracao original vinha com figado/baco trocados de lado: foi espelhada.
// Nao aparecem nesta imagem: coracao, pancreas, tireoide, testiculos.
export const ORGAOS_COSTAS: OrgaoImagem[] = [
  { id: 'figado', sistema: 'figado', tambem: ['proteinas'], nome: 'Fígado', arquivo: '', proporcao: 1, caixa: { x: 169, y: 224, w: 30, h: 28 } },
  { id: 'baco', sistema: 'sangue', nome: 'Baço', arquivo: '', proporcao: 1, caixa: { x: 126, y: 236, w: 13, h: 25 } },
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: '', proporcao: 1, caixa: { x: 174, y: 257, w: 19, h: 26 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: '', proporcao: 1, caixa: { x: 129, y: 253, w: 18, h: 28 } },
  // Depois dos rins: ficam por cima deles e recebem o clique na sobreposicao.
  { id: 'adrenalD', sistema: 'hormonios', nome: 'Suprarrenal direita', arquivo: '', proporcao: 1, caixa: { x: 174, y: 246, w: 14, h: 12 } },
  { id: 'adrenalE', sistema: 'hormonios', nome: 'Suprarrenal esquerda', arquivo: '', proporcao: 1, caixa: { x: 137, y: 243, w: 11, h: 12 } },
  { id: 'bexiga', sistema: 'rins', nome: 'Bexiga', arquivo: '', proporcao: 1, caixa: { x: 151, y: 322, w: 20, h: 19 } },
  { id: 'prostata', sistema: 'prostata', nome: 'Próstata', arquivo: '', proporcao: 1, caixa: { x: 156, y: 341, w: 10, h: 10 } },
]

// ---------------------------------------------------------------------------
// Vista de frente "em camadas" (alternativa a ORGAOS_FRENTE): esqueleto +
// musculo + vasos + orgao individual, cada um como imagem propria. Mantida
// para comparacao lado a lado com a versao de imagem composta unica.
export const ORGAOS_FRENTE_CAMADAS: OrgaoImagem[] = [
  { id: 'hipofise', sistema: 'hormonios', nome: 'Hipófise', arquivo: '', proporcao: 1, caixa: { x: 155, y: 43, w: 10, h: 8 } },
  // Tireoide desce um pouco: fica na base do pescoco (C5-T1), nao logo abaixo do queixo.
  { id: 'tireoide', sistema: 'tireoide', nome: 'Tireoide', arquivo: 'tireoide.webp', proporcao: 1.363, caixa: { x: 138, y: 90, w: 44, h: 20 } },
  // Coracao um pouco para a esquerda da pessoa (direita da tela), como na anatomia real.
  { id: 'coracao', sistema: 'coracao', nome: 'Coração', arquivo: 'coracao.webp', proporcao: 0.776, caixa: { x: 140, y: 128, w: 52, h: 62 } },
  { id: 'figado', sistema: 'figado', tambem: ['proteinas'], nome: 'Fígado', arquivo: 'figado.webp', proporcao: 1.411, caixa: { x: 104, y: 148, w: 90, h: 55 } },
  { id: 'pancreas', sistema: 'pancreas', nome: 'Pâncreas', arquivo: 'pancreas.webp', proporcao: 2.03, caixa: { x: 130, y: 206, w: 72, h: 26 } },
  // Corrigido: rim DIREITO da pessoa fica a ESQUERDA da tela (vista de frente).
  // Rim direito ~1 vertebra mais baixo que o esquerdo (empurrado pelo figado).
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: 'rim-direito.webp', proporcao: 0.664, caixa: { x: 112, y: 204, w: 30, h: 48 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: 'rim-esquerdo.webp', proporcao: 0.655, caixa: { x: 178, y: 198, w: 30, h: 48 } },
  { id: 'adrenalD', sistema: 'hormonios', nome: 'Suprarrenal direita', arquivo: '', proporcao: 1, caixa: { x: 121, y: 201, w: 12, h: 7 } },
  { id: 'adrenalE', sistema: 'hormonios', nome: 'Suprarrenal esquerda', arquivo: '', proporcao: 1, caixa: { x: 187, y: 195, w: 12, h: 7 } },
  { id: 'baco', sistema: 'sangue', nome: 'Baço', arquivo: '', proporcao: 1, caixa: { x: 206, y: 186, w: 12, h: 28 } },
  // Bexiga: atras da sinfise pubica do esqueleto (y~300-312), antes ficava abaixo dela.
  { id: 'bexiga', sistema: 'rins', nome: 'Bexiga', arquivo: 'bexiga.webp', proporcao: 0.931, caixa: { x: 146, y: 280, w: 28, h: 26 } },
  { id: 'prostata', sistema: 'prostata', nome: 'Próstata', arquivo: '', proporcao: 1, caixa: { x: 154, y: 306, w: 12, h: 9 } },
  { id: 'testiculos', sistema: 'testiculos', nome: 'Testículos (região escrotal)', arquivo: '', proporcao: 1, caixa: { x: 151, y: 324, w: 18, h: 13 } },
]

export const DECORATIVOS_FRENTE_CAMADAS: { id: string; arquivo: string; proporcao: number; caixa: Caixa }[] = [
  { id: 'pulmaoD', arquivo: 'pulmao-direito.webp', proporcao: 0.615, caixa: { x: 108, y: 118, w: 50, h: 92 } },
  { id: 'pulmaoE', arquivo: 'pulmao-esquerdo.webp', proporcao: 0.649, caixa: { x: 162, y: 118, w: 50, h: 92 } },
  { id: 'estomago', arquivo: 'estomago.webp', proporcao: 0.858, caixa: { x: 172, y: 168, w: 44, h: 48 } },
  // Intestinos sobem para terminar na entrada da pelve; a bexiga virou orgao clicavel.
  { id: 'intestino', arquivo: 'intestinos.webp', proporcao: 0.871, caixa: { x: 118, y: 236, w: 84, h: 78 } },
]

// Circulacao esquematica calibrada no esqueleto-frontal.webp (ombros ~95/225,125;
// cotovelos ~78/242,223; punhos ~63/257,293; quadris ~130/190,298; joelhos
// ~130/188,423; tornozelos ~130/188,553). A aorta se divide nas iliacas na
// altura de L4 (y~255), nao nos joelhos como no desenho anterior.
export const AORTA_CAMADAS = [
  'M166,168 C166,140 156,136 158,158 L160,255',
  'M160,255 C150,268 134,282 131,300 L130,423 L130,553 L129,592',
  'M160,255 C170,268 186,282 189,300 L188,423 L188,553 L189,592',
  'M158,140 C140,128 108,120 95,128 L78,223 L63,293 L60,322',
  'M162,140 C180,128 212,120 225,128 L242,223 L257,293 L260,322',
  'M156,140 L152,70 M164,140 L168,70',
].join(' ')

// ---------------------------------------------------------------------------
// Vista de COSTAS "em camadas": esqueleto + musculo + vasos + orgao
// individual. Cada PNG de orgao ocupa o canvas INTEIRO (o orgao ja vem
// posicionado no lugar certo dentro dele) — por isso NAO usa "caixa" para
// encaixar a imagem (como a frente faz), so para a area de clique/selecao.
// Posicoes vieram medidas pelo pacote de entrega (ORGAOS-COSTAS-SEPARADOS).
export interface OrgaoCostasCamadas { id: string; sistema: string; nome: string; arquivo: string; caixa: Caixa }

export const ORGAOS_COSTAS_CAMADAS: OrgaoCostasCamadas[] = [
  { id: 'tireoide', sistema: 'tireoide', nome: 'Tireoide', arquivo: 'costas/orgaos/tireoide-costas.webp', caixa: { x: 149, y: 100, w: 20, h: 19 } },
  { id: 'coracao', sistema: 'coracao', nome: 'Coração', arquivo: 'costas/orgaos/coracao-costas.webp', caixa: { x: 136, y: 152, w: 40, h: 50 } },
  { id: 'figado', sistema: 'figado', nome: 'Fígado', arquivo: 'costas/orgaos/figado-costas.webp', caixa: { x: 142, y: 199, w: 68, h: 47 } },
  { id: 'pancreas', sistema: 'pancreas', nome: 'Pâncreas', arquivo: 'costas/orgaos/pancreas-costas.webp', caixa: { x: 137, y: 232, w: 45, h: 19 } },
  // Vista de costas: rim DIREITO fica a DIREITA da tela (nao inverte como na frente).
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: 'costas/orgaos/rim-direito-costas.webp', caixa: { x: 173, y: 237, w: 25, h: 40 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: 'costas/orgaos/rim-esquerdo-costas.webp', caixa: { x: 123, y: 229, w: 24, h: 40 } },
]

export const DECORATIVOS_COSTAS_CAMADAS = [
  { id: 'pulmaoD', arquivo: 'costas/orgaos/pulmao-direito-costas.webp' },
  { id: 'pulmaoE', arquivo: 'costas/orgaos/pulmao-esquerdo-costas.webp' },
]
