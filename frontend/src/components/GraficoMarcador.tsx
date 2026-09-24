import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Classificacao, Ponto } from '../api'
import { fmtData, fmtMesAno, fmtNum, fmtReferencia, timestamp } from '../format'

const COR_PONTO: Record<Classificacao, string> = {
  acima: '#b8661f',
  abaixo: '#4a5fbf',
  dentro: '#2b7a78',
  'nao determinado': '#8aa0a5',
}

interface Props {
  pontos: Ponto[]
  altura?: number
  compacto?: boolean
}

/** Domínio e marcas "redondos" (1, 2, 2,5 ou 5 x 10^n) para o eixo Y. */
function escalaBonita(lo: number, hi: number) {
  const faixa = hi - lo || Math.abs(hi) || 1
  const bruto = (faixa * 1.3) / 4
  const pot = 10 ** Math.floor(Math.log10(bruto))
  const passo = [1, 2, 2.5, 5, 10].map((m) => m * pot).find((x) => x >= bruto) ?? 10 * pot
  const ini = Math.max(0, Math.floor((lo - faixa * 0.15) / passo) * passo)
  const fim = Math.ceil((hi + faixa * 0.15) / passo) * passo
  const ticks: number[] = []
  for (let v = ini; v <= fim + passo / 2; v += passo) ticks.push(Math.round(v * 1e6) / 1e6)
  return { dominio: [ini, fim] as [number, number], ticks }
}

export function limites(pontos: Ponto[]) {
  const ultimo = pontos[pontos.length - 1]
  return { min: ultimo?.ref_min ?? null, max: ultimo?.ref_max ?? null }
}

export function GraficoMarcador({ pontos, altura = 280, compacto = false }: Props) {
  const dados = pontos.map((p) => ({ ...p, t: timestamp(p.data) }))
  const { min, max } = limites(pontos)
  const valores = [...pontos.map((p) => p.valor), ...(min != null ? [min] : []), ...(max != null ? [max] : [])]
  const lo = Math.min(...valores)
  const hi = Math.max(...valores)
  const { dominio, ticks } = escalaBonita(lo, hi)
  const unidade = pontos[0]?.unidade ?? ''

  return (
    <div style={{ height: altura }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={dados} margin={{ top: 12, right: compacto ? 6 : 16, bottom: 0, left: compacto ? -28 : -8 }}>
          <CartesianGrid stroke="#e7eeee" vertical={false} />
          {(min != null || max != null) && (
            <ReferenceArea y1={min ?? dominio[0]} y2={max ?? dominio[1]} fill="#e3f2e8" fillOpacity={0.9} stroke="none" ifOverflow="hidden" />
          )}
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            tickFormatter={(t: number) => fmtMesAno(t)}
            tick={{ fontSize: 12, fill: '#5b7178' }}
            tickLine={false}
            axisLine={{ stroke: '#dce5e6' }}
            minTickGap={36}
            padding={{ left: 14, right: 14 }}
            hide={compacto}
          />
          <YAxis
            domain={dominio}
            ticks={ticks}
            tickFormatter={(v: number) => fmtNum(v)}
            tick={{ fontSize: 12, fill: '#5b7178' }}
            tickLine={false}
            axisLine={false}
            width={56}
            hide={compacto}
          />
          {!compacto && (
            <Tooltip
              cursor={{ stroke: '#9dbdbd', strokeDasharray: '3 3' }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const p = payload[0].payload as Ponto
                return (
                  <div className="rounded-lg border border-line bg-white px-3 py-2 text-sm shadow-md">
                    <div className="text-muted">{fmtData(p.data)}</div>
                    <div className="text-lg font-semibold" style={{ color: COR_PONTO[p.classificacao] }}>
                      {fmtNum(p.valor)} <span className="text-sm font-normal text-muted">{p.unidade}</span>
                    </div>
                    <div className="text-xs text-muted">Referência: {fmtReferencia(p.ref_min, p.ref_max, p.unidade)}</div>
                  </div>
                )
              }}
            />
          )}
          <Line
            type="monotone"
            dataKey="valor"
            stroke="#2b7a78"
            strokeWidth={compacto ? 1.8 : 2.4}
            isAnimationActive={false}
            dot={(props) => {
              const { cx, cy, payload, index } = props as { cx: number; cy: number; payload: Ponto; index: number }
              const cor = COR_PONTO[payload.classificacao]
              const r = compacto ? (index === dados.length - 1 ? 3 : 0) : payload.classificacao === 'dentro' ? 4 : 5.5
              return <circle key={index} cx={cx} cy={cy} r={r} fill={cor} stroke="#fff" strokeWidth={1.5} />
            }}
            activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
      {!compacto && <span className="sr-only">Gráfico em {unidade}</span>}
    </div>
  )
}

export function Legenda({ pontos }: { pontos: Ponto[] }) {
  const { min, max } = limites(pontos)
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted">
      <span className="flex items-center gap-2">
        <span className="h-3 w-5 rounded-sm bg-band" /> Faixa de referência do laudo mais recente: {fmtReferencia(min, max, pontos[0]?.unidade)}
      </span>
      <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-alto" /> acima</span>
      <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-baixo" /> abaixo</span>
    </div>
  )
}

export function variacao(pontos: Ponto[]) {
  if (pontos.length < 2) return null
  const a = pontos[0]
  const b = pontos[pontos.length - 1]
  if (!a.valor) return null
  return { de: a, para: b, pct: ((b.valor - a.valor) / Math.abs(a.valor)) * 100 }
}
