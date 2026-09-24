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
  caixa: Caixa
  proporcao: number // largura/altura da imagem original, para "contain"
}

// Orgaos clicaveis (tem exames de sangue associados) — vista de frente.
// Caixas medidas diretamente na imagem composta unica (orgaos-frente.webp);
// usadas so como area de clique/selecao — a propria imagem ja mostra os orgaos,
// nao ha mais imagem separada por orgao nesta vista (ver "arquivo: ''").
export const ORGAOS_FRENTE: OrgaoImagem[] = [
  { id: 'tireoide', sistema: 'tireoide', nome: 'Tireoide', arquivo: '', proporcao: 1, caixa: { x: 148, y: 93, w: 33, h: 16 } },
  { id: 'coracao', sistema: 'coracao', nome: 'Coração', arquivo: '', proporcao: 1, caixa: { x: 141, y: 137, w: 52, h: 58 } },
  { id: 'figado', sistema: 'figado', nome: 'Fígado', arquivo: '', proporcao: 1, caixa: { x: 94, y: 198, w: 76, h: 43 } },
  { id: 'pancreas', sistema: 'pancreas', nome: 'Pâncreas', arquivo: '', proporcao: 1, caixa: { x: 125, y: 236, w: 69, h: 18 } },
  // Corrigido: rim DIREITO da pessoa fica a ESQUERDA da tela (vista de frente).
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: '', proporcao: 1, caixa: { x: 125, y: 234, w: 20, h: 26 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: '', proporcao: 1, caixa: { x: 187, y: 234, w: 20, h: 26 } },
]

// Recorte (dentro da propria imagem composta) usado so para a animacao de
// respiracao via clip-path — nao sao clicaveis, nao tem sistema associado.
export const PULMOES_FRENTE = {
  pulmaoD: { x: 94, y: 122, w: 49, h: 73 },
  pulmaoE: { x: 182, y: 122, w: 45, h: 73 },
}

// --- Vista de COSTAS -------------------------------------------------------
// Imagem de corpo inteiro (fundo), com rins clicaveis (posicao anatomica
// real deles). Demais orgaos aparecem "em projecao" na propria imagem, sem
// area de clique dedicada nesta primeira versao.
export const ORGAOS_COSTAS: OrgaoImagem[] = [
  // Na vista de costas a lateralidade NAO se inverte: rim direito continua a direita da tela.
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: '', proporcao: 1, caixa: { x: 168, y: 218, w: 26, h: 38 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: '', proporcao: 1, caixa: { x: 126, y: 218, w: 26, h: 38 } },
]

// ---------------------------------------------------------------------------
// Vista de frente "em camadas" (alternativa a ORGAOS_FRENTE): esqueleto +
// musculo + vasos + orgao individual, cada um como imagem propria. Mantida
// para comparacao lado a lado com a versao de imagem composta unica.
export const ORGAOS_FRENTE_CAMADAS: OrgaoImagem[] = [
  { id: 'tireoide', sistema: 'tireoide', nome: 'Tireoide', arquivo: 'tireoide.webp', proporcao: 1.363, caixa: { x: 138, y: 86, w: 44, h: 20 } },
  { id: 'coracao', sistema: 'coracao', nome: 'Coração', arquivo: 'coracao.webp', proporcao: 0.776, caixa: { x: 136, y: 128, w: 52, h: 62 } },
  { id: 'figado', sistema: 'figado', nome: 'Fígado', arquivo: 'figado.webp', proporcao: 1.411, caixa: { x: 104, y: 148, w: 90, h: 55 } },
  { id: 'pancreas', sistema: 'pancreas', nome: 'Pâncreas', arquivo: 'pancreas.webp', proporcao: 2.03, caixa: { x: 130, y: 206, w: 72, h: 26 } },
  // Corrigido: rim DIREITO da pessoa fica a ESQUERDA da tela (vista de frente).
  { id: 'rimD', sistema: 'rins', nome: 'Rim direito', arquivo: 'rim-direito.webp', proporcao: 0.664, caixa: { x: 112, y: 198, w: 30, h: 48 } },
  { id: 'rimE', sistema: 'rins', nome: 'Rim esquerdo', arquivo: 'rim-esquerdo.webp', proporcao: 0.655, caixa: { x: 178, y: 198, w: 30, h: 48 } },
]

export const DECORATIVOS_FRENTE_CAMADAS: { id: string; arquivo: string; proporcao: number; caixa: Caixa }[] = [
  { id: 'pulmaoD', arquivo: 'pulmao-direito.webp', proporcao: 0.615, caixa: { x: 108, y: 118, w: 50, h: 92 } },
  { id: 'pulmaoE', arquivo: 'pulmao-esquerdo.webp', proporcao: 0.649, caixa: { x: 162, y: 118, w: 50, h: 92 } },
  { id: 'estomago', arquivo: 'estomago.webp', proporcao: 0.858, caixa: { x: 172, y: 168, w: 44, h: 48 } },
  { id: 'intestino', arquivo: 'intestinos.webp', proporcao: 0.871, caixa: { x: 118, y: 250, w: 84, h: 95 } },
  { id: 'bexiga', arquivo: 'bexiga.webp', proporcao: 0.931, caixa: { x: 140, y: 300, w: 40, h: 36 } },
]

export const AORTA_CAMADAS = "M168,202 C168,186 160,184 160,198 L160,420 C150,440 142,480 140,600 M160,420 C170,440 178,480 180,600 M160,176 C136,164 104,164 92,200 C86,260 80,340 74,430 M160,176 C184,164 216,164 228,200 C234,260 240,340 246,430 M156,172 L152,70 M164,172 L168,70"

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
