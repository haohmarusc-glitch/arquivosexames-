/** Patologias da coluna citadas no trecho do laudo, ligadas ao nivel e ao lado.
 *
 * O achado traz niveis e termos em listas separadas (a hernia pode ser so em
 * C6-C7 e os outros niveis so degenerativos). Aqui cada frase do trecho e lida
 * sozinha: so vira marca quando o termo E o nivel aparecem na mesma frase.
 * Nao interpreta nem cria diagnostico: posicao ilustrativa.
 */

export type TipoPatologia = 'hernia' | 'protrusao' | 'estenose' | 'listese' | 'artrodese' | 'degenerativo'
export type Lado = 'esquerdo' | 'direito' | 'bilateral' | 'central'

export interface Patologia {
  nivel: string
  tipo: TipoPatologia
  lado: Lado
}

export const NOME_PATOLOGIA: Record<TipoPatologia, string> = {
  hernia: 'Hérnia',
  protrusao: 'Protrusão / abaulamento',
  estenose: 'Estenose',
  listese: 'Listese',
  artrodese: 'Artrodese',
  degenerativo: 'Degenerativo',
}

// Ordem = prioridade quando a mesma frase cita mais de um termo para o nivel.
const TERMOS: [TipoPatologia, RegExp][] = [
  ['hernia', /herni|extrus/],
  ['protrusao', /protrus|abaulament/],
  ['listese', /listese/],
  ['estenose', /estenose|reducao da amplitude do canal/],
  ['artrodese', /artrodese|parafusos pediculares|espacador intersomatico/],
  ['degenerativo', /discopatia|degenerativ|espondilose|osteofit|desidratacao discal|artrose/],
]

const NEGACAO = /(sem|nao ha|nao se observa[m]?|ausencia de|nao|livre de)\s+(\S+\s+){0,2}$/

const semAcento = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

// "C6-C7", "C6/C7", "C6 - C7", "L5-S1", "C7-T1"
const NIVEL_RE = /\b([ctl])\s?(\d{1,2})\s*[-/–]\s*([ctls])?\s?(\d{1,2})\b/g

function niveisDaFrase(frase: string): string[] {
  const out: string[] = []
  for (const m of frase.matchAll(NIVEL_RE)) {
    const a = `${m[1].toUpperCase()}${m[2]}`
    const b = `${(m[3] ?? m[1]).toUpperCase()}${m[4]}`
    const nivel = `${a}-${b}`
    if (!out.includes(nivel)) out.push(nivel)
  }
  return out
}

function ladoDaFrase(frase: string): Lado {
  const d = /\bdireit/.test(frase)
  const e = /\besquerd/.test(frase)
  if ((d && e) || /bilateral/.test(frase)) return 'bilateral'
  if (d) return 'direito'
  if (e) return 'esquerdo'
  return 'central'
}

/** Divide o trecho em frases/itens ("1. ...", "2. ...", ";" e ".") e acha
 * cada patologia com nivel e lado. */
export function patologiasDoTrecho(trecho: string): Patologia[] {
  const texto = semAcento(trecho)
  // Itens numerados e pontuacao separam frases; "C6-C7." nao quebra o nivel.
  const frases = texto.split(/(?:^|\s)\d{1,2}[.)]\s|[;\n]|\.(?=\s|$)/).map((f) => f.trim()).filter(Boolean)
  const saida: Patologia[] = []
  for (const frase of frases) {
    const niveis = niveisDaFrase(frase)
    if (!niveis.length) continue
    const tipo = TERMOS.find(([, re]) => {
      const m = re.exec(frase)
      return m != null && !NEGACAO.test(frase.slice(0, m.index))
    })?.[0]
    if (!tipo) continue
    const lado = ladoDaFrase(frase)
    for (const nivel of niveis) {
      if (!saida.some((p) => p.nivel === nivel && p.tipo === tipo && p.lado === lado)) saida.push({ nivel, tipo, lado })
    }
  }
  return saida
}

/** Posicao dos discos nas imagens de detalhe, em % da largura/altura.
 * Medido numa grade sobre as imagens (vistas de COSTAS: o lado esquerdo da
 * pessoa fica a esquerda da tela). */
export const DISCOS_DETALHE: Record<string, Record<string, { y: number; xE: number; xD: number; xC: number }>> = {
  cervical: {
    'C2-C3': { y: 28.5, xE: 34, xD: 56, xC: 45 },
    'C3-C4': { y: 38, xE: 34, xD: 57, xC: 45 },
    'C4-C5': { y: 47.5, xE: 33, xD: 57, xC: 45 },
    'C5-C6': { y: 57, xE: 32, xD: 57, xC: 45 },
    'C6-C7': { y: 66, xE: 31, xD: 57, xC: 44 },
    'C7-T1': { y: 75.5, xE: 30, xD: 57, xC: 44 },
  },
  lombar: {
    'T12-L1': { y: 3, xE: 25, xD: 69, xC: 47 },
    'L1-L2': { y: 11.5, xE: 24, xD: 70, xC: 47 },
    'L2-L3': { y: 21, xE: 23, xD: 71, xC: 47 },
    'L3-L4': { y: 32.5, xE: 22, xD: 72, xC: 47 },
    'L4-L5': { y: 44, xE: 22, xD: 73, xC: 47 },
    'L5-S1': { y: 54.5, xE: 22, xD: 74, xC: 47 },
  },
}
