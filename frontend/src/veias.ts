// Doppler venoso das pernas: onde desenhar o achado na imagem de detalhe
// (recorte das pernas de sistema-venoso.webp, vista de FRENTE: a perna
// direita da pessoa fica a esquerda da tela).
//
// Coordenadas em % da largura (x 0-100) e na mesma escala para a altura
// (y 0-ALTURA_PERNAS), calibradas em 2026-09 numa grade sobre o recorte.

export const ALTURA_PERNAS = (100 * 835) / 380

export type TipoVeia = 'insuficiencia' | 'trombose'
export type LadoPerna = 'direito' | 'esquerdo'

export const NOME_VEIA: Record<TipoVeia, string> = { insuficiencia: 'Insuficiência venosa', trombose: 'Trombose' }
export const COR_VEIA: Record<TipoVeia, string> = { insuficiencia: '#f08c00', trombose: '#c92a2a' }

// Trajeto da safena magna (face interna) na perna direita da pessoa; a
// esquerda e o espelho em x = 50.
const SAFENA_DIREITA: [number, number][] = [
  [33, 18], [36, 35], [39, 50], [40, 65], [41, 78], [40, 92], [37, 104], [40, 120], [38, 140], [36, 160], [35, 178],
]

export function trajeto(lado: LadoPerna): [number, number][] {
  return lado === 'direito' ? SAFENA_DIREITA : SAFENA_DIREITA.map(([x, y]) => [100 - x, y])
}

// Faixas de altura (y) de cada parte do membro.
const FAIXAS: [RegExp, [number, number]][] = [
  [/juncao safeno.?femoral|\bjsf\b|croca|virilha|inguinal/, [15, 25]],
  [/terco proximal da coxa/, [20, 45]],
  [/terco medio da coxa/, [42, 67]],
  [/terco distal da coxa/, [64, 90]],
  [/\bcoxa/, [20, 90]],
  [/poplite|joelho/, [86, 98]],
  [/terco proximal da perna/, [94, 124]],
  [/terco medio da perna/, [120, 152]],
  [/terco distal da perna/, [148, 178]],
  [/\bperna/, [94, 178]],
  [/tornozelo|maleol|\bpe\b|\bpes\b/, [170, 188]],
]
const MEMBRO_TODO: [number, number] = [18, 178]

const sem = (t: string) => t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const TERMO_RE: [TipoVeia, RegExp][] = [
  ['trombose', /trombo/],
  ['insuficiencia', /insuficien|refluxo|incompeten/],
]
const NEGACAO_RE = /\b(sem|nao|ausencia|ausente|nem|negativ)\b[^.;]{0,60}$/

export interface MarcaVeia {
  tipo: TipoVeia
  lado: LadoPerna
  faixa: [number, number]
}

/** Trechos afetados citados no texto da conclusao de UMA perna. */
export function marcasDoTrecho(trecho: string, lado: LadoPerna): MarcaVeia[] {
  const marcas: MarcaVeia[] = []
  // O PDF usa hifen invisivel (U+00AD) como marcador de item e dentro de palavras ("safeno-femoral").
  const texto = sem(trecho).replace(/\u00ad\s/g, '. ').replace(/\u00ad/g, '-')
  for (const frase of texto.split(/[.;\n]|\s-\s/)) {
    for (const [tipo, re] of TERMO_RE) {
      const m = re.exec(frase)
      if (!m || NEGACAO_RE.test(frase.slice(0, m.index))) continue
      // "desde a prega poplitea ate o terco distal": o trecho vai do primeiro ao ultimo local citado
      const achadas = FAIXAS.filter(([r]) => r.test(frase)).map(([, f]) => f)
      // "terco distal da perna" tambem casa com "perna": fica so a faixa mais especifica
      const especificas = achadas.filter((f) => !achadas.some((g) => g !== f && f[0] <= g[0] && f[1] >= g[1]))
      const faixa: [number, number] = especificas.length
        ? [Math.min(...especificas.map((f) => f[0])), Math.max(...especificas.map((f) => f[1]))]
        : MEMBRO_TODO
      if (!marcas.some((x) => x.tipo === tipo && x.faixa[0] === faixa[0] && x.faixa[1] === faixa[1])) marcas.push({ tipo, lado, faixa })
    }
  }
  return marcas
}

interface AchadoPerna {
  data: string | null
  lado: string
  trecho: string
  regiao: string
  termos: string[]
}

// Termo do backend (achados.py) que libera cada tipo de marca: ele ja trata negacao.
const TERMO_BACKEND: Record<TipoVeia, string> = { insuficiencia: 'insuficiencia_venosa', trombose: 'trombose' }

/** Estado atual de cada perna: so o laudo mais recente dela vale (o que melhorou some). */
export function marcasDasPernas(achados: AchadoPerna[]): MarcaVeia[] {
  const doMembro = achados.filter((a) => a.regiao === 'membros_inferiores')
  const marcas: MarcaVeia[] = []
  for (const lado of ['direito', 'esquerdo'] as LadoPerna[]) {
    const daPerna = doMembro.filter((a) => a.lado === lado || a.lado === 'bilateral' || !a.lado)
    if (!daPerna.length) continue
    const ultima = daPerna.reduce((m, a) => ((a.data ?? '') > m ? a.data ?? '' : m), '')
    daPerna
      .filter((a) => (a.data ?? '') === ultima)
      .forEach((a) => marcas.push(...marcasDoTrecho(a.trecho, lado).filter((m) => a.termos.includes(TERMO_BACKEND[m.tipo]))))
  }
  return marcas
}

/** Pedaco do trajeto entre as alturas y0 e y1, com as pontas interpoladas. */
export function trechoDoTrajeto(pontos: [number, number][], [y0, y1]: [number, number]): [number, number][] {
  const noY = (y: number): [number, number] => {
    for (let i = 1; i < pontos.length; i++) {
      const [xa, ya] = pontos[i - 1]
      const [xb, yb] = pontos[i]
      if (y >= ya && y <= yb) return [xa + ((xb - xa) * (y - ya)) / (yb - ya || 1), y]
    }
    return y < pontos[0][1] ? pontos[0] : pontos[pontos.length - 1]
  }
  return [noY(y0), ...pontos.filter(([, y]) => y > y0 && y < y1), noY(y1)]
}
