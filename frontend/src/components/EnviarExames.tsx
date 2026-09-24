import { useRef, useState, type DragEvent } from 'react'
import { avisarDadosMudaram, REGIOES, useApi, type Envio } from '../api'
import { TagSistema } from './Badges'
import { Painel } from './Painel'
import { fmtData, TIPOS } from '../format'
import { href } from '../rota'

/** Caixa para enviar laudos em PDF pelo proprio painel. A API roda o mesmo
 * analisador da linha de comando e cada marcador cai sozinho no sistema certo
 * (mapa_exames.py) — a lista abaixo mostra para onde foi cada exame. */
export function EnviarExames() {
  const status = useApi<{ habilitado: boolean; limite_mb: number }>('/api/upload')
  const entrada = useRef<HTMLInputElement>(null)
  const [arrastando, setArrastando] = useState(false)
  const [enviando, setEnviando] = useState<string[]>([])
  const [envios, setEnvios] = useState<Envio[]>([])
  const [erro, setErro] = useState<string | null>(null)

  if (status.dados && !status.dados.habilitado) {
    return (
      <Painel titulo="Enviar exames">
        <p className="text-sm text-muted">
          O envio pelo painel está desligado neste servidor. Para ligar, monte uma pasta gravável no container e defina
          {' '}<code className="rounded bg-canvas px-1">ANALISADOR_UPLOAD_DIR</code> (veja o README).
        </p>
      </Painel>
    )
  }

  async function enviar(lista: FileList | File[]) {
    const todos = Array.from(lista)
    if (!todos.length) return
    // Arquivos acima do limite nem sao enviados (a Cloudflare recusa uploads
    // grandes, e um ZIP de imagens DICOM de centenas de MB so gastaria tempo).
    const limite = (status.dados?.limite_mb ?? 25) * 1024 * 1024
    const grandes: Envio[] = todos.filter((f) => f.size > limite).map((f) => ({
      arquivo: f.name,
      status: 'erro',
      erro: /\.zip$/i.test(f.name) && f.size > 50 * 1024 * 1024
        ? `ZIP de ${Math.round(f.size / 1024 / 1024)} MB — provavelmente imagens DICOM, que o painel não lê. Envie os laudos em PDF (ou um .zip só com os PDFs).`
        : `Arquivo de ${Math.round(f.size / 1024 / 1024)} MB passa do limite de ${status.dados?.limite_mb ?? 25} MB.`,
    }))
    const pdfs = todos.filter((f) => f.size <= limite)
    if (grandes.length) setEnvios((antes) => [...grandes, ...antes])
    if (!pdfs.length) {
      setErro(null)
      return
    }
    setErro(null)
    setEnviando(pdfs.map((f) => f.name))
    const corpo = new FormData()
    pdfs.forEach((f) => corpo.append('arquivos', f))
    try {
      const r = await fetch('/api/upload', { method: 'POST', body: corpo })
      const json = await r.json().catch(() => null)
      if (!r.ok) throw new Error(json?.detail ?? `A API respondeu ${r.status}.`)
      setEnvios((antes) => [...(json.envios as Envio[]), ...antes])
      if ((json.envios as Envio[]).some((e) => e.status === 'adicionado')) avisarDadosMudaram()
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível enviar.')
    } finally {
      setEnviando([])
      if (entrada.current) entrada.current.value = ''
    }
  }

  async function remover(arquivo: string) {
    if (!window.confirm(`Remover "${arquivo}" do painel? O PDF enviado também será apagado do servidor.`)) return
    const r = await fetch(`/api/upload/${encodeURIComponent(arquivo)}`, { method: 'DELETE' })
    if (r.ok) {
      setEnvios((antes) => antes.filter((e) => e.arquivo !== arquivo))
      avisarDadosMudaram()
    } else {
      const json = await r.json().catch(() => null)
      setErro(json?.detail ?? 'Não foi possível remover.')
    }
  }

  const aoSoltar = (e: DragEvent) => {
    e.preventDefault()
    setArrastando(false)
    if (e.dataTransfer.files.length) enviar(e.dataTransfer.files)
  }

  return (
    <Painel titulo="Enviar exames" acoes={<span className="text-xs text-muted">PDF ou .zip com PDFs, até {status.dados?.limite_mb ?? 25} MB cada</span>}>
      <div
        onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
        onDragLeave={() => setArrastando(false)}
        onDrop={aoSoltar}
        className={`flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ${arrastando ? 'border-teal bg-teal-soft/60' : 'border-line bg-canvas/50'}`}
      >
        <svg viewBox="0 0 24 24" className="h-8 w-8 text-teal" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </svg>
        {enviando.length ? (
          <p className="text-sm font-medium text-ink" role="status">Analisando {enviando.length === 1 ? enviando[0] : `${enviando.length} arquivos`}…</p>
        ) : (
          <>
            <p className="text-sm font-medium text-ink">Arraste os PDFs ou o .zip aqui</p>
            <button type="button" onClick={() => entrada.current?.click()}
              className="rounded-lg bg-teal px-4 py-1.5 text-sm font-medium text-white hover:bg-teal-deep">
              Escolher arquivos
            </button>
            <p className="text-xs text-muted">Cada exame vai sozinho para a área certa (Fígado, Rins, Hormônios…). Pode mandar um .zip com vários laudos. Laudos repetidos são ignorados.</p>
          </>
        )}
        <input ref={entrada} type="file" multiple className="hidden" onChange={(e) => e.target.files && enviar(e.target.files)} />
      </div>

      {erro && <p className="mt-3 text-sm text-alto" role="alert">{erro}</p>}

      {envios.length > 0 && (
        <ul className="mt-4 space-y-3">
          {envios.map((e, i) => (
            <li key={`${e.arquivo}-${i}`} className="rounded-xl border border-line p-3 text-sm">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate font-medium" title={e.arquivo}>{e.arquivo}</div>
                  <div className="text-xs text-muted">
                    {e.status === 'adicionado' && <>{TIPOS[e.tipo ?? ''] ?? e.tipo} · {fmtData(e.data ?? null)} · {e.resultados} {e.resultados === 1 ? 'valor' : 'valores'}{e.fora ? `, ${e.fora} fora da referência` : ''}</>}
                    {e.status === 'duplicado' && <>Já estava no painel{e.igual_a ? ` (igual a ${e.igual_a})` : ''} — nada foi alterado.</>}
                    {e.status === 'erro' && <span className="text-alto">{e.erro}</span>}
                    {e.status === 'info' && <span>{e.erro}</span>}
                  </div>
                  {e.aviso && <div className="mt-0.5 text-xs text-alto">{e.aviso}</div>}
                </div>
                {e.status === 'adicionado' && (
                  <button type="button" onClick={() => remover(e.arquivo)} className="text-xs text-muted underline hover:text-alto">Desfazer</button>
                )}
              </div>
              {e.status === 'adicionado' && ((e.sistemas?.length ?? 0) > 0 || (e.regioes?.length ?? 0) > 0) && (
                <div className="mt-2 space-y-1.5">
                  {e.sistemas?.map((s) => (
                    <a key={s.id} href={href('anatomia', { r: s.id })} className="flex flex-wrap items-baseline gap-2 rounded-lg px-1 py-0.5 hover:bg-canvas">
                      <TagSistema id={s.id} nome={s.nome} />
                      <span className="text-xs text-muted">{s.marcadores.join(', ')}</span>
                    </a>
                  ))}
                  {e.regioes?.map((r) => (
                    <a key={r} href={href('anatomia', { vista: 'coluna', r })} className="mr-1 inline-block rounded-md bg-ink/5 px-2 py-0.5 text-xs font-medium text-ink hover:bg-teal-soft">
                      {REGIOES[r] ?? r}
                    </a>
                  ))}
                </div>
              )}
              {e.status === 'adicionado' && !e.resultados && !(e.regioes?.length) && (
                <p className="mt-1 text-xs text-muted">Nenhum valor reconhecido automaticamente — o documento aparece na lista abaixo para conferência.</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Painel>
  )
}
