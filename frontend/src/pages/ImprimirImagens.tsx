import { useMemo, useState } from 'react'
import { useApi, type EstudoSeries } from '../api'
import { Aviso, Carregando } from '../components/Painel'
import { fmtData } from '../format'
import { href } from '../rota'

const LIMITE = 120 // evita mandar centenas de fatias de ressonancia para a impressora sem querer

/** Pagina de impressao: imagens de um exame em grade, com cabecalho (data e
 * descricao, sem dados pessoais). Menu e botoes somem na impressao. */
export function ImprimirImagens({ estudo }: { estudo: string | null }) {
  const resp = useApi<EstudoSeries>(estudo ? `/api/imagens/${encodeURIComponent(estudo)}/series` : null)
  const [serieEscolhida, setSerie] = useState<string>('')
  const [colunas, setColunas] = useState(2)
  const [inicio, setInicio] = useState(0)

  const series = useMemo(() => resp.dados?.series ?? [], [resp.dados])
  const totalGeral = series.reduce((n, s) => n + s.imagens.length, 0)
  // Padrao: tudo se o exame for pequeno (raio-X, ultrassom); senao a 1a serie.
  const serieAtual = serieEscolhida || (totalGeral <= LIMITE ? 'todas' : series[0]?.id ?? 'todas')
  const imagens = useMemo(() => {
    const escolhidas = serieAtual === 'todas' ? series : series.filter((s) => s.id === serieAtual)
    return escolhidas.flatMap((s) => s.imagens)
  }, [series, serieAtual])
  const pagina = imagens.slice(inicio, inicio + LIMITE)

  if (!estudo) return <div className="px-4 py-8 lg:px-10"><Aviso tom="erro">Nenhum exame escolhido.</Aviso></div>

  const nomeSerie = (id: string) => {
    const s = series.find((x) => x.id === id)
    return s ? `${s.numero ? `Série ${s.numero}` : 'Série'}${s.descricao ? ` — ${s.descricao}` : ''} (${s.imagens.length})` : ''
  }

  return (
    <div className="space-y-5 px-4 py-8 lg:px-10 print:space-y-3 print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <a href={href('imagens')} className="text-sm font-medium text-teal hover:underline">← Voltar para Imagens</a>
        <button
          type="button"
          onClick={() => window.print()}
          disabled={!pagina.length}
          className="rounded-lg bg-teal px-5 py-2 text-sm font-medium text-white hover:bg-teal-deep disabled:opacity-50"
        >
          Imprimir
        </button>
      </div>

      {resp.carregando && !resp.dados && <Carregando />}
      {resp.erro && <Aviso tom="erro">{resp.erro}</Aviso>}

      {resp.dados && (
        <>
          <header>
            <h1 className="text-2xl font-bold tracking-tight print:text-lg">{resp.dados.descricao || 'Exame de imagem'}</h1>
            <p className="text-sm text-muted print:text-xs">
              {fmtData(resp.dados.data)}
              {serieAtual !== 'todas' && <> · {nomeSerie(serieAtual)}</>}
              {' · '}{imagens.length} {imagens.length === 1 ? 'imagem' : 'imagens'}
            </p>
          </header>

          <div className="flex flex-wrap items-end gap-4 rounded-2xl border border-line bg-white p-4 text-sm print:hidden">
            {series.length > 1 && (
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold text-muted">Série</span>
                <select value={serieAtual} onChange={(e) => { setSerie(e.target.value); setInicio(0) }} className="max-w-[80vw] rounded-lg border border-line bg-white px-2 py-1.5">
                  <option value="todas">Todas as séries ({totalGeral})</option>
                  {series.map((s) => <option key={s.id} value={s.id}>{nomeSerie(s.id)}</option>)}
                </select>
              </label>
            )}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-muted">Imagens por linha</span>
              <select value={colunas} onChange={(e) => setColunas(Number(e.target.value))} className="rounded-lg border border-line bg-white px-2 py-1.5">
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </label>
            {imagens.length > LIMITE && (
              <div className="flex items-center gap-2">
                <button type="button" disabled={inicio === 0} onClick={() => setInicio(Math.max(0, inicio - LIMITE))} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Anteriores</button>
                <span className="text-xs text-muted">{inicio + 1}–{Math.min(inicio + LIMITE, imagens.length)} de {imagens.length}</span>
                <button type="button" disabled={inicio + LIMITE >= imagens.length} onClick={() => setInicio(inicio + LIMITE)} className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40">Próximas</button>
              </div>
            )}
            <p className="basis-full text-xs text-muted">
              Dica: na janela de impressão, escolha “Salvar como PDF” para guardar ou mandar por e-mail. Para o exame completo em
              qualidade original, use “Baixar” na lista de imagens.
            </p>
          </div>

          <div className="grid gap-3 print:gap-2" style={{ gridTemplateColumns: `repeat(${colunas}, minmax(0, 1fr))` }}>
            {pagina.map((id, i) => (
              <figure key={id} className="break-inside-avoid rounded-lg bg-black p-1">
                <img src={`/api/imagens/instancia/${id}.png`} alt={`Imagem ${inicio + i + 1}`} loading="lazy" className="mx-auto max-h-[90vh] w-full object-contain print:max-h-[45vh]" />
                <figcaption className="px-1 pt-0.5 text-[10px] text-white/70">{inicio + i + 1}</figcaption>
              </figure>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
