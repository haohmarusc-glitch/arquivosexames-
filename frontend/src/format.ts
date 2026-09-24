const dataCurta = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' })
const dataLonga = new Intl.DateTimeFormat('pt-BR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const mesAno = new Intl.DateTimeFormat('pt-BR', { month: 'short', year: 'numeric', timeZone: 'UTC' })

const iso = (d: string) => new Date(`${d}T00:00:00Z`)

export const fmtData = (d: string | null) => (d ? dataCurta.format(iso(d)) : '—')
export const fmtDataLonga = (d: string | null) => (d ? dataLonga.format(iso(d)) : '—')
export const fmtMesAno = (d: string | number | null) =>
  d == null ? '—' : mesAno.format(typeof d === 'number' ? new Date(d) : iso(d)).replace('. de ', '/').replace('.', '')
export const timestamp = (d: string) => iso(d).getTime()

export function fmtNum(v: number | null | undefined) {
  if (v == null || Number.isNaN(v)) return '—'
  const casas = Math.abs(v) < 10 && !Number.isInteger(v) ? 2 : Number.isInteger(v) ? 0 : 1
  return v.toLocaleString('pt-BR', { maximumFractionDigits: casas })
}

/** Largura do eixo Y a partir do maior rótulo: com largura fixa, "100.000" virava "00.000". */
export function larguraEixoY(ticks: number[], formatar: (v: number) => string = fmtNum, pxPorCaractere = 7.5) {
  const maior = Math.max(1, ...ticks.map((t) => formatar(t).length))
  return Math.ceil(maior * pxPorCaractere) + 12
}

export function fmtReferencia(min: number | null, max: number | null, unidade = '') {
  const u = unidade ? ` ${unidade}` : ''
  if (min != null && max != null) return `${fmtNum(min)} a ${fmtNum(max)}${u}`
  if (max != null) return `até ${fmtNum(max)}${u}`
  if (min != null) return `a partir de ${fmtNum(min)}${u}`
  return 'sem referência numérica'
}

export const TIPOS: Record<string, string> = {
  laboratorial: 'Laboratorial',
  imagem: 'Imagem',
  anatomopatologico: 'Anatomopatológico',
}
