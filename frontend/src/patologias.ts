/** Patologias da coluna citadas no trecho do laudo, ligadas ao nivel e ao lado.
 *
 * O achado traz niveis e termos em listas separadas (a hernia pode ser so em
 * C6-C7 e os outros niveis so degenerativos). Aqui cada frase do trecho e lida
 * sozinha: so vira marca quando o termo E o nivel aparecem na mesma frase.
 * Nao interpreta nem cria diagnostico: posicao ilustrativa.
 */

export type TipoPatologia = 'hernia' | 'protrusao' | 'estenose' | 'listese' | 'artrodese' | 'fratura' | 'degenerativo'
export type Lado = 'esquerdo' | 'direito' | 'bilateral' | 'central'

export interface Patologia {
  /** Disco ("C6-C7", "L5-S1") ou, para fratura, a vertebra ("T12"). */
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
  fratura: 'Fratura',
  degenerativo: 'Degenerativo',
}

/** Rotulo curto para a etiqueta ao lado da coluna. */
export const CURTO_PATOLOGIA: Record<TipoPatologia, string> = {
  hernia: 'hérnia',
  protrusao: 'protrusão',
  estenose: 'estenose',
  listese: 'listese',
  artrodese: 'artrodese',
  fratura: 'fratura',
  degenerativo: '',
}

export const COR_PATOLOGIA: Record<TipoPatologia, string> = {
  hernia: '#d9480f',
  protrusao: '#f08c00',
  estenose: '#7048e8',
  listese: '#1c7ed6',
  artrodese: '#495057',
  fratura: '#c92a2a',
  degenerativo: '#795548',
}

// Ordem = prioridade quando a mesma frase cita mais de um termo para o nivel.
const TERMOS: [TipoPatologia, RegExp][] = [
  ['hernia', /herni|extrus/],
  ['protrusao', /protrus|abaulament/],
  ['listese', /listese/],
  ['estenose', /estenose|reducao da amplitude do canal/],
  ['fratura', /fratura|achatamento/],
  ['degenerativo', /discopatia|degenerativ|espondilose|osteofit|desidratacao discal|artrose/],
]
const ARTRODESE = /artrodese|parafusos? pedicula|espacador intersomatico|fixacao (vertebral|lombar|cervical|toracica|pedicular)|haste/

const NEGACAO = /(sem|nao ha|nao se observa[m]?|ausencia de|nao|livre de)\s+(\S+\s+){0,2}$/

const semAcento = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Vertebras em ordem craniocaudal. */
export const VERTEBRAS_ORDEM = [
  ...Array.from({ length: 7 }, (_, i) => `C${i + 1}`),
  ...Array.from({ length: 12 }, (_, i) => `T${i + 1}`),
  ...Array.from({ length: 5 }, (_, i) => `L${i + 1}`),
  'S1',
]
const idx = (v: string) => VERTEBRAS_ORDEM.indexOf(v)

// "C6-C7", "C6/C7", "C6 - C7", "L5-S1", "C7-T1" (tambem "L4-S1" em artrodese)
const NIVEL_RE = /\b([ctl])\s?(\d{1,2})\s*[-/–]\s*([ctls])?\s?(\d{1,2})\b/g
// "L4 a S1", "de L3 ate L5"
const FAIXA_RE = /\b([ctls])\s?(\d{1,2})\s+(?:a|ate)\s+([ctls])\s?(\d{1,2})\b/g
const VERTEBRA_RE = /\b([ctls])(\d{1,2})\b/g

const vert = (letra: string, num: string) => `${letra.toUpperCase()}${Number(num)}`

/** Discos entre duas vertebras (inclusive): L4..S1 -> L4-L5, L5-S1. */
function discosEntre(a: string, b: string): string[] {
  let [i, j] = [idx(a), idx(b)]
  if (i < 0 || j < 0) return []
  if (i > j) [i, j] = [j, i]
  const out: string[] = []
  for (let k = i; k < j; k++) out.push(`${VERTEBRAS_ORDEM[k]}-${VERTEBRAS_ORDEM[k + 1]}`)
  return out
}

/** Discos citados na frase ("C5-C6 e C6-C7"): so pares de vertebras vizinhas. */
function niveisDaFrase(frase: string): string[] {
  const out: string[] = []
  for (const m of frase.matchAll(NIVEL_RE)) {
    const a = vert(m[1], m[2])
    const b = vert(m[3] ?? m[1], m[4])
    const n = `${a}-${b}`
    if (idx(a) >= 0 && idx(b) - idx(a) === 1 && !out.includes(n)) out.push(n)
  }
  return out
}

/** Artrodese: faixa de vertebras citada na frase ("L4-S1", "L4 a S1",
 * "parafusos em L4, L5 e S1") -> todos os discos dentro dela. */
function discosArtrodese(frase: string): string[] {
  const vs = new Set<string>()
  for (const re of [NIVEL_RE, FAIXA_RE]) {
    for (const m of frase.matchAll(re)) {
      discosEntre(vert(m[1], m[2]), vert(m[3] ?? m[1], m[4])).forEach((d) => d.split('-').forEach((v) => vs.add(v)))
    }
  }
  for (const m of frase.matchAll(VERTEBRA_RE)) vs.add(vert(m[1], m[2]))
  const validas = [...vs].filter((v) => idx(v) >= 0).sort((a, b) => idx(a) - idx(b))
  return validas.length >= 2 ? discosEntre(validas[0], validas[validas.length - 1]) : []
}

/** Fratura: vertebras citadas soltas ("fratura de T12", "achatamento de L1"). */
function vertebrasDaFrase(frase: string): string[] {
  const semDiscos = frase.replace(NIVEL_RE, ' ')
  const out: string[] = []
  for (const m of semDiscos.matchAll(VERTEBRA_RE)) {
    const v = vert(m[1], m[2])
    if (idx(v) >= 0 && !out.includes(v)) out.push(v)
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

/** true quando o termo nao aparece ou aparece negado ("sem hernias"). */
const ausente = (frase: string, re: RegExp) => {
  const m = re.exec(frase)
  return m == null || NEGACAO.test(frase.slice(0, m.index))
}

/** Divide o trecho em frases/itens ("1. ...", "2. ...", ";" e ".") e acha
 * cada patologia com nivel e lado. */
export function patologiasDoTrecho(trecho: string): Patologia[] {
  const texto = semAcento(trecho)
  const frases = texto.split(/(?:^|\s)\d{1,2}[.)]\s|[;\n]|\.(?=\s|$)/).map((f) => f.trim()).filter(Boolean)
  const saida: Patologia[] = []
  const add = (p: Patologia) => {
    if (!saida.some((q) => q.nivel === p.nivel && q.tipo === p.tipo && q.lado === p.lado)) saida.push(p)
  }
  for (const frase of frases) {
    if (!ausente(frase, ARTRODESE)) discosArtrodese(frase).forEach((nivel) => add({ nivel, tipo: 'artrodese', lado: 'bilateral' }))
    const tipo = TERMOS.find(([, re]) => !ausente(frase, re))?.[0]
    if (!tipo) continue
    if (tipo === 'fratura') {
      vertebrasDaFrase(frase).forEach((nivel) => add({ nivel, tipo, lado: 'central' }))
      continue
    }
    const lado = ladoDaFrase(frase)
    niveisDaFrase(frase).forEach((nivel) => add({ nivel, tipo, lado }))
  }
  return saida
}

/** Ordem de gravidade para escolher a cor/rotulo de um nivel com varias patologias. */
export const GRAVIDADE: TipoPatologia[] = ['fratura', 'hernia', 'listese', 'estenose', 'protrusao', 'artrodese', 'degenerativo']

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
    // Vista obliqua: o lado esquerdo do disco fica sob a lamina (x ~36%).
    'T12-L1': { y: 3, xE: 37, xD: 69, xC: 47 },
    'L1-L2': { y: 11.5, xE: 37, xD: 70, xC: 47 },
    'L2-L3': { y: 21, xE: 36, xD: 71, xC: 47 },
    'L3-L4': { y: 32.5, xE: 36, xD: 72, xC: 47 },
    'L4-L5': { y: 44, xE: 36, xD: 73, xC: 47 },
    'L5-S1': { y: 54.5, xE: 36, xD: 74, xC: 47 },
  },
}

/** Colunas dos parafusos/hastes de artrodese (pediculos, junto as facetas). */
export const PEDICULOS_DETALHE: Record<string, { xE: number; xD: number }> = {
  cervical: { xE: 35, xD: 55 },
  lombar: { xE: 38, xD: 60 },
}

/** Centro de uma vertebra na imagem de detalhe: meio caminho entre os discos
 * de cima e de baixo (nas pontas, meio intervalo alem do ultimo disco). */
export function vertebraDetalhe(regiao: string, v: string): { y: number; xE: number; xD: number; xC: number } | null {
  const discos = DISCOS_DETALHE[regiao]
  const i = idx(v)
  if (!discos || i < 0) return null
  const cima = discos[`${VERTEBRAS_ORDEM[i - 1]}-${v}`]
  const baixo = discos[`${v}-${VERTEBRAS_ORDEM[i + 1]}`]
  if (cima && baixo) return { y: (cima.y + baixo.y) / 2, xE: (cima.xE + baixo.xE) / 2, xD: (cima.xD + baixo.xD) / 2, xC: (cima.xC + baixo.xC) / 2 }
  const lista = Object.values(discos)
  const passo = lista.length > 1 ? (lista[lista.length - 1].y - lista[0].y) / (lista.length - 1) : 8
  const fora = (p: { y: number }) => p.y < 1 || p.y > 99 // fora da imagem (ex.: T12 na lombar)
  if (cima) return fora({ y: cima.y + passo / 2 }) ? null : { ...cima, y: cima.y + passo / 2 }
  if (baixo) return fora({ y: baixo.y - passo / 2 }) ? null : { ...baixo, y: baixo.y - passo / 2 }
  return null
}

export interface MarcaPatologia extends Patologia {
  data: string | null
  historico: boolean
}

/** Regiao de um nivel pela letra, como regiao_de_nivel (achados.py):
 * C7-T1 -> cervical, T12-L1 -> toracica, L5-S1 -> lombar, T12 -> toracica. */
export const regiaoDoNivel = (nivel: string) => ({ C: 'cervical', T: 'toracica', L: 'lombar', S: 'sacral' } as Record<string, string>)[nivel[0]] ?? ''

interface AchadoTexto { regiao?: string; data?: string | null; trecho?: string; niveis?: string[]; niveis_historicos?: string[] }

/** Para cada regiao da coluna, SO o laudo mais recente que fala dela (pela
 * regiao do achado ou por um nivel citado no texto). Uma patologia que
 * melhorou ou sumiu no exame novo nao fica desenhada por causa de um antigo. */
export function maisRecentesPorRegiao<T extends AchadoTexto>(achados: T[]): Map<string, T[]> {
  const porRegiao = new Map<string, T[]>()
  for (const a of achados) {
    const regioes = new Set([a.regiao ?? '', ...(a.niveis ?? []).map(regiaoDoNivel), ...patologiasDoTrecho(a.trecho ?? '').map((p) => regiaoDoNivel(p.nivel))])
    regioes.delete('')
    for (const r of regioes) {
      const atuais = porRegiao.get(r)
      const dAtual = atuais?.[0]?.data ?? ''
      const d = a.data ?? ''
      if (!atuais || d > dAtual) porRegiao.set(r, [a])
      else if (d === dAtual) atuais.push(a)
    }
  }
  return porRegiao
}

/** Patologias do estado ATUAL: em cada regiao, so as do laudo mais recente
 * dela; "degenerativo" so aparece onde nao ha outra patologia no nivel. */
export function marcasDosAchados(achados: AchadoTexto[]): MarcaPatologia[] {
  const marcas: MarcaPatologia[] = []
  for (const [regiao, doExame] of maisRecentesPorRegiao(achados)) {
    for (const a of doExame) {
      for (const p of patologiasDoTrecho(a.trecho ?? '')) {
        if (regiaoDoNivel(p.nivel) !== regiao) continue
        if (marcas.some((m) => m.nivel === p.nivel && m.tipo === p.tipo && m.lado === p.lado)) continue
        marcas.push({ ...p, data: a.data ?? null, historico: (a.niveis_historicos ?? []).includes(p.nivel) })
      }
    }
  }
  return marcas.filter((m) => m.tipo !== 'degenerativo' || !marcas.some((o) => o.nivel === m.nivel && o.tipo !== 'degenerativo'))
}

/** Discos de artrodese agrupados em faixas continuas: [["L4-L5","L5-S1"], ...]. */
export function faixasArtrodese(marcas: MarcaPatologia[]): string[][] {
  const discos = [...new Set(marcas.filter((m) => m.tipo === 'artrodese').map((m) => m.nivel))]
    .sort((a, b) => idx(a.split('-')[0]) - idx(b.split('-')[0]))
  const faixas: string[][] = []
  for (const d of discos) {
    const ultima = faixas[faixas.length - 1]
    if (ultima && ultima[ultima.length - 1].split('-')[1] === d.split('-')[0]) ultima.push(d)
    else faixas.push([d])
  }
  return faixas
}

/** Vertebras cobertas por uma faixa de discos: ["L4-L5","L5-S1"] -> [L4, L5, S1]. */
export const vertebrasDaFaixa = (faixa: string[]) => [faixa[0].split('-')[0], ...faixa.map((d) => d.split('-')[1])]

export const ABREV_LADO: Record<Lado, string> = { esquerdo: 'E', direito: 'D', bilateral: 'bilat.', central: '' }
