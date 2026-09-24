import { useMemo, useState } from 'react'
import { useApi, type EstudoImagem, type RespostaImagens } from '../api'
import { Aviso, Carregando, Painel } from '../components/Painel'
import { fmtData } from '../format'
import { href } from '../rota'

const MODALIDADES: Record<string, string> = {
  MR: 'Ressonância',
  CT: 'Tomografia',
  CR: 'Raio-X',
  DX: 'Raio-X',
  US: 'Ultrassom',
  MG: 'Mamografia',
  NM: 'Medicina nuclear',
  XA: 'Angiografia',
  OT: 'Outros',
}

function nomeModalidade(m: string[]) {
  const nomes = [...new Set(m.map((x) => MODALIDADES[x] ?? x))]
  return nomes.length ? nomes.join(' + ') : 'Imagem'
}

function CartaoEstudo({ e }: { e: EstudoImagem }) {
  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <span className="font-semibold tabular-nums">{fmtData(e.data)}</span>
          <span className="rounded-full bg-teal-soft px-2.5 py-0.5 text-xs font-semibold text-teal-deep">{nomeModalidade(e.modalidades)}</span>
        </div>
        <div className="mt-1 truncate text-sm text-ink" title={e.descricao}>{e.descricao || 'Sem descrição'}</div>
        <div className="text-xs text-muted">
          {e.series} {e.series === 1 ? 'série' : 'séries'} · {e.imagens} {e.imagens === 1 ? 'imagem' : 'imagens'}
        </div>
        {e.laudos.length > 0 && (
          <div className="mt-1 text-xs text-muted">
            Laudo do mesmo dia:{' '}
            {e.laudos.map((l, k) => (
              <span key={l}>
                {k > 0 && ', '}
                <a href={`/api/documentos/${encodeURIComponent(l)}/pdf`} target="_blank" rel="noopener" className="text-teal hover:underline">{l}</a>
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2 sm:flex-col sm:items-stretch">
        <a
          href={e.visualizador}
          target="_blank"
          rel="noopener"
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-teal px-4 py-2 text-sm font-medium text-white hover:bg-teal-deep"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          Abrir imagens
        </a>
        <div className="flex gap-2">
          <a href={href('imprimir', { estudo: e.id })} className="inline-flex flex-1 items-center justify-center rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-canvas">
            Imprimir
          </a>
          <a href={`/api/imagens/${e.id}/zip`} title="Arquivos DICOM originais (sem seus dados pessoais), para outro visualizador ou para levar ao médico" className="inline-flex flex-1 items-center justify-center rounded-lg border border-line px-3 py-1.5 text-sm font-medium text-ink hover:bg-canvas">
            Baixar
          </a>
        </div>
      </div>
    </li>
  )
}

export function Imagens() {
  const resp = useApi<RespostaImagens>('/api/imagens')
  const [filtro, setFiltro] = useState('')

  const estudos = useMemo(() => {
    const lista = resp.dados?.estudos ?? []
    return filtro ? lista.filter((e) => e.modalidades.some((m) => (MODALIDADES[m] ?? m) === filtro)) : lista
  }, [resp.dados, filtro])

  const opcoes = useMemo(
    () => [...new Set((resp.dados?.estudos ?? []).flatMap((e) => e.modalidades.map((m) => MODALIDADES[m] ?? m)))].sort(),
    [resp.dados],
  )

  return (
    <div className="space-y-6 px-4 py-8 lg:px-10">
      <h1 className="text-3xl font-bold tracking-tight">Imagens</h1>
      {resp.carregando && !resp.dados && <Carregando />}
      {resp.erro && <Aviso tom="erro">{resp.erro}</Aviso>}
      {resp.dados && !resp.dados.habilitado && (
        <Aviso>
          O servidor de imagens não está configurado. Defina <code className="rounded bg-canvas px-1">ORTHANC_URL</code> no container do
          painel (veja a seção "Imagens" do README).
        </Aviso>
      )}
      {resp.dados?.erro && <Aviso tom="erro">{resp.dados.erro}</Aviso>}
      {resp.dados?.habilitado && !resp.dados.erro && (
        <Painel
          titulo={`${estudos.length} ${estudos.length === 1 ? 'exame' : 'exames'} com imagens`}
          acoes={
            opcoes.length > 1 && (
              <select value={filtro} onChange={(e) => setFiltro(e.target.value)} className="rounded-lg border border-line bg-white px-2 py-1 text-sm" aria-label="Filtrar por tipo">
                <option value="">Todos os tipos</option>
                {opcoes.map((o) => <option key={o}>{o}</option>)}
              </select>
            )
          }
        >
          {estudos.length ? (
            <ul className="space-y-3">{estudos.map((e) => <CartaoEstudo key={e.id} e={e} />)}</ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted">
              Nenhuma imagem importada ainda. Rode <code className="rounded bg-canvas px-1">importar_imagens.py</code> no servidor.
            </p>
          )}
          <p className="mt-4 text-xs text-muted">
            As imagens abrem no visualizador OHIF (zoom, contraste, régua, rolagem pelas fatias). Os dados do paciente foram removidos dos
            arquivos; textos gravados dentro da própria imagem pelo aparelho podem continuar visíveis.
          </p>
        </Painel>
      )}
    </div>
  )
}
