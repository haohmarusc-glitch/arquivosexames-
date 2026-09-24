import { useMemo, useState } from 'react'
import { REGIOES, useApi, type Documento, type Sistema } from '../api'
import { BadgeStatus, TagSistema } from '../components/Badges'
import { Aviso, Carregando, Painel } from '../components/Painel'
import { EnviarExames } from '../components/EnviarExames'
import { fmtData, TIPOS } from '../format'
import { href } from '../rota'

export function TabelaDocumentos({ documentos }: { documentos: Documento[] }) {
  const sistemas = useApi<Sistema[]>('/api/sistemas')
  const nomes = Object.fromEntries((sistemas.dados ?? []).map((s) => [s.id, s.nome]))

  if (!documentos.length) return <p className="py-6 text-center text-sm text-muted">Nenhum documento corresponde aos filtros.</p>

  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="text-xs text-muted">
          <tr className="border-b border-line">
            <th className="px-5 py-2 font-semibold">Data</th>
            <th className="px-3 py-2 font-semibold">Documento</th>
            <th className="px-3 py-2 font-semibold">Áreas</th>
            <th className="px-5 py-2 font-semibold">Situação</th>
          </tr>
        </thead>
        <tbody>
          {documentos.map((d) => (
            <tr key={d.arquivo} className="border-b border-line/70 last:border-0">
              <td className="px-5 py-3 whitespace-nowrap tabular-nums">{fmtData(d.data)}</td>
              <td className="px-3 py-3">
                <div className="font-medium">{TIPOS[d.tipo] ?? d.tipo}</div>
                <div className="max-w-[28ch] truncate text-xs text-muted" title={d.arquivo}>{d.arquivo}</div>
                {d.aviso && <div className="mt-0.5 text-xs text-alto">{d.aviso}</div>}
                {d.origem === 'upload' && <div className="mt-0.5 text-xs text-teal">Enviado pelo painel</div>}
                {d.pdf && (
                  <div className="mt-1 flex gap-3 text-xs font-medium">
                    <a href={`/api/documentos/${encodeURIComponent(d.arquivo)}/pdf`} target="_blank" rel="noopener" className="text-teal hover:underline">Abrir / imprimir</a>
                    <a href={`/api/documentos/${encodeURIComponent(d.arquivo)}/pdf?baixar=true`} className="text-teal hover:underline">Baixar PDF</a>
                  </div>
                )}
              </td>
              <td className="px-3 py-3">
                <div className="flex flex-wrap gap-1">
                  {d.sistemas.slice(0, 4).map((s) => <TagSistema key={s} id={s} nome={nomes[s] ?? s} />)}
                  {d.sistemas.length > 4 && <span className="text-xs text-muted">+{d.sistemas.length - 4}</span>}
                  {d.regioes.map((r) => (
                    <a key={r} href={href('anatomia', { vista: 'coluna', r })} className="rounded-md bg-ink/5 px-2 py-0.5 text-xs font-medium whitespace-nowrap text-ink hover:bg-teal-soft">{REGIOES[r] ?? r}</a>
                  ))}
                </div>
              </td>
              <td className="px-5 py-3">
                {!d.texto_extraido ? (
                  <span className="inline-flex rounded-full bg-alto-soft px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap text-alto">Precisa de OCR</span>
                ) : (
                  <BadgeStatus valor={d.status} fora={d.fora} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Documentos() {
  const docs = useApi<Documento[]>('/api/documentos')
  const [busca, setBusca] = useState('')
  const [tipo, setTipo] = useState('')
  const [status, setStatus] = useState('')

  const filtrados = useMemo(() => {
    const q = busca.trim().toLowerCase()
    return (docs.dados ?? []).filter(
      (d) => (!q || d.arquivo.toLowerCase().includes(q)) && (!tipo || d.tipo === tipo) && (!status || d.status === status),
    )
  }, [docs.dados, busca, tipo, status])

  return (
    <div className="space-y-6 px-4 py-8 lg:px-10">
      <h1 className="text-3xl font-bold tracking-tight">Documentos</h1>
      <EnviarExames />
      {docs.erro && <Aviso tom="erro">{docs.erro}</Aviso>}
      <Painel
        titulo={docs.dados ? `${filtrados.length} de ${docs.dados.length}` : undefined}
        acoes={
          <div className="flex flex-wrap gap-2">
            <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Buscar pelo nome do arquivo" aria-label="Buscar pelo nome do arquivo"
              className="w-56 rounded-lg border border-line px-3 py-1.5 text-sm" />
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="rounded-lg border border-line bg-white px-3 py-1.5 text-sm" aria-label="Tipo">
              <option value="">Todos os tipos</option>
              {Object.entries(TIPOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-line bg-white px-3 py-1.5 text-sm" aria-label="Situação">
              <option value="">Todas as situações</option>
              <option value="atencao">Com valores fora</option>
              <option value="normal">Dentro das referências</option>
              <option value="achados">Com achados de imagem</option>
              <option value="sem_valores">Sem valores extraídos</option>
            </select>
          </div>
        }
      >
        {docs.dados ? <TabelaDocumentos documentos={filtrados} /> : <Carregando />}
      </Painel>
    </div>
  )
}
