import { useState } from 'react'
import { REGIOES, useApi, type Achado, type Documento, type Estado, type Marcador, type Resumo, type Serie } from '../api'
import { BadgeClassificacao } from '../components/Badges'
import { GraficoMarcador, Legenda, variacao } from '../components/GraficoMarcador'
import { Aviso, Carregando, Painel } from '../components/Painel'
import { TabelaDocumentos } from './Documentos'
import { fmtDataLonga, fmtMesAno, fmtNum } from '../format'
import { href } from '../rota'

export function VisaoGeral({ resumo }: { resumo: Estado<Resumo> }) {
  const marcadores = useApi<Marcador[]>('/api/marcadores')
  const achados = useApi<Achado[]>('/api/achados')
  const documentos = useApi<Documento[]>('/api/documentos')
  const r = resumo.dados

  if (resumo.erro) {
    return (
      <div className="p-6 lg:p-10">
        <Aviso tom="erro">
          <p className="font-semibold">O painel ainda não tem dados.</p>
          <p className="mt-1">{resumo.erro}</p>
        </Aviso>
      </div>
    )
  }

  const saudacao = r?.titular ? `Olá, ${r.titular}` : 'Seus exames'
  const regioesAchados = new Set((achados.dados ?? []).map((a) => a.regiao))
  const padrao = r?.atencao[0]?.id ?? marcadores.dados?.[0]?.id ?? null

  return (
    <div>
      <div className="bg-[linear-gradient(135deg,#1d5b5a_0%,#2b7a78_55%,#5fa7a0_100%)] px-5 pt-8 pb-24 text-white lg:px-10 lg:pt-10">
        <h1 className="text-3xl font-bold tracking-tight lg:text-4xl">{saudacao}</h1>
        {r && (
          <p className="mt-2 max-w-2xl text-[15px] text-teal-soft">
            {r.total_documentos} documentos entre {fmtMesAno(r.periodo.inicio)} e {fmtMesAno(r.periodo.fim)}, com {r.total_marcadores} marcadores acompanhados.
          </p>
        )}
      </div>

      <div className="-mt-16 space-y-6 px-4 pb-12 lg:px-10">
        {r && r.nome_divergente > 0 && (
          <div className="relative rounded-2xl border border-alto/40 bg-alto-soft px-5 py-4 text-sm text-alto">
            <p className="font-semibold">Confira o download dos laudos</p>
            {r.nome_divergente > 0 && <p className="mt-1">{r.nome_divergente === 1 ? '1 PDF tem nome de exame de imagem, mas o conteúdo é de laboratório.' : `${r.nome_divergente} PDFs têm nome de exame de imagem, mas o conteúdo é de laboratório.`}</p>}
            <p className="mt-1">Confira esses laudos no portal e, se preciso, baixe de novo e rode a análise.</p>
          </div>
        )}
        {!r ? (
          <Carregando />
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            <Cartao titulo="Última coleta">
              <p className="text-xl font-semibold">{fmtDataLonga(r.ultimo_exame.data)}</p>
              <p className="mt-1 text-sm text-muted">{r.ultimo_exame.marcadores} marcadores em {r.ultimo_exame.arquivos.length} laudo{r.ultimo_exame.arquivos.length === 1 ? '' : 's'}</p>
            </Cartao>

            <Cartao titulo="Fora da referência no último resultado" destaque={r.atencao.length > 0}>
              {r.atencao.length === 0 ? (
                <p className="text-sm text-muted">Nenhum marcador fora da faixa informada no laudo.</p>
              ) : (
                <ul className="space-y-1.5">
                  {r.atencao.slice(0, 4).map((a) => (
                    <li key={a.id}>
                      <a href={href('evolucao', { m: a.id })} className="flex items-center justify-between gap-3 text-sm hover:text-teal">
                        <span className="font-medium">{a.nome}</span>
                        <span className="flex items-center gap-2 text-muted">
                          {fmtNum(a.valor)} {a.unidade}
                          <BadgeClassificacao valor={a.classificacao} />
                        </span>
                      </a>
                    </li>
                  ))}
                  {r.atencao.length > 4 && <li className="text-sm text-muted">e mais {r.atencao.length - 4}</li>}
                </ul>
              )}
            </Cartao>

            <Cartao titulo="Achados de imagem">
              {achados.dados?.length ? (
                <>
                  <p className="text-xl font-semibold">{achados.dados.length} registros</p>
                  <p className="mt-1 text-sm text-muted">{[...regioesAchados].map((x) => REGIOES[x] ?? x).join(', ')}</p>
                  <a href={href('anatomia', { vista: 'coluna' })} className="mt-3 inline-block text-sm font-semibold text-teal hover:underline">Ver no corpo</a>
                </>
              ) : (
                <p className="text-sm text-muted">Nenhum achado extraído de laudos de imagem.</p>
              )}
              {r.sem_texto > 0 && <p className="mt-3 text-xs text-alto">{r.sem_texto} laudo{r.sem_texto > 1 ? 's' : ''} sem texto (digitalizado como imagem) precisa{r.sem_texto > 1 ? 'm' : ''} de OCR.</p>}
            </Cartao>
          </div>
        )}

        {padrao && marcadores.dados && <EvolucaoRapida marcadores={marcadores.dados} destaque={r?.atencao.map((a) => a.id) ?? []} inicial={padrao} />}

        <Painel titulo="Documentos recentes" acoes={<a href={href('documentos')} className="text-sm font-semibold text-teal hover:underline">Ver todos</a>}>
          {documentos.dados ? <TabelaDocumentos documentos={documentos.dados.slice(0, 6)} /> : <Carregando />}
        </Painel>
      </div>
    </div>
  )
}

function Cartao({ titulo, children, destaque = false }: { titulo: string; children: React.ReactNode; destaque?: boolean }) {
  return (
    <section className={`rounded-2xl border bg-white p-5 shadow-[0_8px_24px_-12px_rgba(23,49,58,.25)] ${destaque ? 'border-alto/40' : 'border-line'}`}>
      <h2 className="mb-3 text-sm font-semibold text-muted">{titulo}</h2>
      {children}
    </section>
  )
}

function EvolucaoRapida({ marcadores, destaque, inicial }: { marcadores: Marcador[]; destaque: string[]; inicial: string }) {
  const [id, setId] = useState(inicial)
  const serie = useApi<Serie>(`/api/marcadores/${id}`)
  const rapidos = [...new Set([...destaque, ...marcadores.slice(0, 6).map((m) => m.id)])].slice(0, 7)
  const nomes = Object.fromEntries(marcadores.map((m) => [m.id, m.nome]))
  const v = serie.dados ? variacao(serie.dados.pontos) : null

  return (
    <Painel
      titulo={`Evolução: ${nomes[id] ?? id}`}
      acoes={
        <select value={id} onChange={(e) => setId(e.target.value)} className="rounded-lg border border-line bg-white px-3 py-1.5 text-sm" aria-label="Escolher marcador">
          {marcadores.map((m) => <option key={m.id} value={m.id}>{m.nome}</option>)}
        </select>
      }
    >
      <div className="mb-3 flex flex-wrap gap-2">
        {rapidos.map((m) => (
          <button key={m} onClick={() => setId(m)} aria-pressed={m === id}
            className={`rounded-full border px-3 py-1 text-sm ${m === id ? 'border-teal bg-teal text-white' : 'border-line text-muted hover:border-teal hover:text-teal'}`}>
            {nomes[m]}
            {destaque.includes(m) && <span className="ml-1.5 inline-block h-1.5 w-1.5 -translate-y-0.5 rounded-full bg-alto align-middle" aria-label="fora da referência" />}
          </button>
        ))}
      </div>
      {serie.erro && <Aviso>{serie.erro}</Aviso>}
      {serie.dados && (
        <>
          <GraficoMarcador pontos={serie.dados.pontos} />
          <Legenda pontos={serie.dados.pontos} />
          {v && (
            <p className="mt-3 text-sm text-muted">
              De {fmtNum(v.de.valor)} para {fmtNum(v.para.valor)} {v.para.unidade} entre {fmtMesAno(v.de.data)} e {fmtMesAno(v.para.data)} ({v.pct >= 0 ? '+' : ''}{fmtNum(v.pct)}%).{' '}
              <a href={href('evolucao', { m: id })} className="font-semibold text-teal hover:underline">Ver todas as medições</a>
            </p>
          )}
        </>
      )}
    </Painel>
  )
}
