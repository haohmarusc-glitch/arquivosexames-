import { useMemo, useState } from 'react'
import { useApi, type Conflito, type Marcador, type Serie, type Sistema } from '../api'
import { BadgeClassificacao } from '../components/Badges'
import { GraficoMarcador, Legenda, variacao } from '../components/GraficoMarcador'
import { Aviso, Carregando, Painel } from '../components/Painel'
import { fmtData, fmtMesAno, fmtNum, fmtReferencia } from '../format'
import { href } from '../rota'

const semAcento = (s: string) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

export function Evolucao({ marcadorInicial }: { marcadorInicial: string | null }) {
  const marcadores = useApi<Marcador[]>('/api/marcadores')
  const sistemas = useApi<Sistema[]>('/api/sistemas')
  const [escolhido, setEscolhido] = useState<string | null>(marcadorInicial)
  const [filtro, setFiltro] = useState('')
  const id = escolhido ?? marcadores.dados?.[0]?.id ?? null
  const serie = useApi<Serie>(id ? `/api/marcadores/${id}` : null)

  const escolher = (marcadorId: string) => {
    setEscolhido(marcadorId)
    // So a URL, para poder salvar/compartilhar o link deste marcador
    // (a tela nao remonta com isso; quem mantem o estado e o setEscolhido acima).
    window.history.replaceState(null, '', href('evolucao', { m: marcadorId }))
  }

  const grupos = useMemo(() => {
    const q = semAcento(filtro.trim())
    return (sistemas.dados ?? [])
      .map((s) => ({ ...s, itens: (marcadores.dados ?? []).filter((m) => m.sistema === s.id && (!q || semAcento(m.nome).includes(q))) }))
      .filter((s) => s.itens.length)
  }, [sistemas.dados, marcadores.dados, filtro])

  const v = serie.dados ? variacao(serie.dados.pontos) : null
  const datasConflito = new Set((serie.dados?.conflitos ?? []).map((c) => c.data))

  return (
    <div className="space-y-6 px-4 py-8 lg:px-10">
      <h1 className="text-3xl font-bold tracking-tight">Evolução</h1>
      {marcadores.erro && <Aviso tom="erro">{marcadores.erro}</Aviso>}
      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <Painel className="xl:sticky xl:top-6 xl:max-h-[calc(100vh-3rem)] xl:overflow-y-auto">
          <input type="search" value={filtro} onChange={(e) => setFiltro(e.target.value)} placeholder="Buscar marcador" aria-label="Buscar marcador"
            className="mt-4 mb-2 w-full rounded-lg border border-line px-3 py-2 text-sm" />
          {!marcadores.dados && <Carregando />}
          {grupos.map((g) => (
            <div key={g.id} className="mt-4">
              <h2 className="mb-1 text-xs font-semibold text-muted">{g.nome}</h2>
              <ul>
                {g.itens.map((m) => (
                  <li key={m.id}>
                    <button onClick={() => escolher(m.id)} aria-pressed={m.id === id}
                      className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm ${m.id === id ? 'bg-teal-soft font-semibold text-teal-deep' : 'hover:bg-canvas'}`}>
                      <span>{m.nome}</span>
                      {(m.classificacao === 'acima' || m.classificacao === 'abaixo') && (
                        <span className={`text-xs font-bold ${m.classificacao === 'acima' ? 'text-alto' : 'text-baixo'}`} aria-label={m.classificacao}>
                          {m.classificacao === 'acima' ? '↑' : '↓'}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </Painel>

        <div className="min-w-0 space-y-6">
          {serie.erro && <Aviso>{serie.erro}</Aviso>}
          {serie.carregando && !serie.dados && <Carregando />}
          {serie.dados && (
            <div key={id} className="space-y-6">
              <Painel titulo={serie.dados.nome}>
                {v && (
                  <p className="mb-2 text-sm text-muted">
                    {serie.dados.pontos.length} medições. De {fmtNum(v.de.valor)} para {fmtNum(v.para.valor)} {v.para.unidade} entre {fmtMesAno(v.de.data)} e {fmtMesAno(v.para.data)} ({v.pct >= 0 ? '+' : ''}{fmtNum(v.pct)}%).
                  </p>
                )}
                <GraficoMarcador pontos={serie.dados.pontos} altura={320} />
                <Legenda pontos={serie.dados.pontos} />
                {Boolean(serie.dados.conflitos?.length) && <AvisoConflitos conflitos={serie.dados.conflitos ?? []} />}
              </Painel>

              <Painel titulo="Medições">
                <div className="-mx-5 overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead className="text-xs text-muted">
                      <tr className="border-b border-line">
                        <th className="px-5 py-2 font-semibold">Data</th>
                        <th className="px-3 py-2 text-right font-semibold">Valor</th>
                        <th className="px-3 py-2 font-semibold">Referência do laudo</th>
                        <th className="px-3 py-2 font-semibold">Situação</th>
                        <th className="px-5 py-2 font-semibold">Arquivo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...serie.dados.pontos].reverse().map((p, i) => (
                        <tr key={`${p.data}-${p.arquivo}-${i}`} className="border-b border-line/70 last:border-0">
                          <td className="px-5 py-2.5 whitespace-nowrap tabular-nums">
                            {fmtData(p.data)}
                            {p.coleta_hora && datasConflito.has(p.data) && <span className="ml-1 text-xs text-muted">{p.coleta_hora}</span>}
                          </td>
                          <td className="px-3 py-2.5 text-right font-semibold whitespace-nowrap tabular-nums">{fmtNum(p.valor)} <span className="font-normal text-muted">{p.unidade}</span></td>
                          <td className="px-3 py-2.5 text-muted">{fmtReferencia(p.ref_min, p.ref_max, p.unidade)}</td>
                          <td className="px-3 py-2.5"><BadgeClassificacao valor={p.classificacao} /></td>
                          <td className="max-w-[24ch] truncate px-5 py-2.5 text-xs text-muted" title={p.arquivo}>{p.arquivo}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Painel>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/** Datas com mais de um valor: o grafico mostra um so, aqui aparecem os outros. */
function AvisoConflitos({ conflitos }: { conflitos: Conflito[] }) {
  return (
    <div className="mt-4 rounded-xl border border-line bg-canvas px-4 py-3 text-sm">
      <p className="font-semibold">
        {conflitos.length === 1 ? 'Uma data tem' : `${conflitos.length} datas têm`} mais de um valor. O gráfico mostra um por dia:
      </p>
      <ul className="mt-2 space-y-1.5 text-muted">
        {conflitos.map((c) => (
          <li key={c.data}>
            <span className="font-medium text-ink">{fmtData(c.data)}:</span>{' '}
            {c.valores.map((x, i) => (
              <span key={i}>
                {i > 0 && ' · '}
                <span className={x.no_grafico ? 'font-semibold text-ink' : ''}>
                  {fmtNum(x.valor)} {x.unidade}
                </span>
                {x.coleta_hora && ` (coleta ${x.coleta_hora})`}
                {x.no_grafico ? ' — no gráfico' : ''}
              </span>
            ))}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted">
        Quando há duas coletas no mesmo dia, o gráfico usa a mais recente. Confira no laudo original.
      </p>
    </div>
  )
}
