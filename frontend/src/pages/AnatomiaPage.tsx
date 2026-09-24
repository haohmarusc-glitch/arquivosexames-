import { useMemo, useState } from 'react'
import { MODALIDADES, REGIOES, TERMOS, useApi, type Achado, type Marcador, type Serie, type Sistema } from '../api'
import { FiguraColuna, FiguraOrgaos, type EstiloCostas, type EstiloFrente, type Orientacao } from '../components/Anatomia'
import { BadgeClassificacao } from '../components/Badges'
import { GraficoMarcador } from '../components/GraficoMarcador'
import { Aviso, Painel } from '../components/Painel'
import { fmtData, fmtNum, fmtReferencia } from '../format'
import { href } from '../rota'

type Vista = 'orgaos' | 'coluna'

export function AnatomiaPage({ vistaInicial, regiaoInicial }: { vistaInicial: string | null; regiaoInicial: string | null }) {
  const [vista, setVista] = useState<Vista>(vistaInicial === 'coluna' ? 'coluna' : 'orgaos')
  const [orientacao, setOrientacao] = useState<Orientacao>('frente')
  const [estiloFrente, setEstiloFrente] = useState<EstiloFrente>('composta')
  const [estiloCostas, setEstiloCostas] = useState<EstiloCostas>('composta')
  const [sistema, setSistema] = useState<string | null>(vista === 'orgaos' ? regiaoInicial : null)
  const [regiao, setRegiao] = useState<string | null>(vista === 'coluna' ? regiaoInicial : null)

  const sistemas = useApi<Sistema[]>('/api/sistemas')
  const marcadores = useApi<Marcador[]>('/api/marcadores')
  const achados = useApi<Achado[]>('/api/achados')

  const comAlerta = useMemo(() => new Set((sistemas.dados ?? []).filter((s) => s.fora > 0).map((s) => s.id)), [sistemas.dados])
  const erro = sistemas.erro || marcadores.erro || achados.erro

  return (
    <div className="space-y-6 px-4 py-8 lg:px-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-3xl font-bold tracking-tight">Anatomia</h1>
        <div className="inline-flex rounded-xl border border-line bg-white p-1" role="tablist" aria-label="Vista">
          {([['orgaos', 'Órgãos e exames de sangue'], ['coluna', 'Coluna e articulações']] as const).map(([id, rotulo]) => (
            <button key={id} role="tab" aria-selected={vista === id} onClick={() => setVista(id)}
              className={`rounded-lg px-4 py-1.5 text-sm font-medium ${vista === id ? 'bg-teal text-white' : 'text-muted hover:text-ink'}`}>
              {rotulo}
            </button>
          ))}
        </div>
      </div>
      {erro && <Aviso tom="erro">{erro}</Aviso>}

      <div className="grid gap-6 lg:grid-cols-[minmax(260px,380px)_1fr]">
        <div className="rounded-2xl border border-line bg-[radial-gradient(circle_at_50%_30%,#ffffff_0%,#eef4f4_70%)] p-4 lg:sticky lg:top-6 lg:self-start">
          <div className="mx-auto aspect-[240/640] max-h-[72vh]">
            {vista === 'orgaos' ? (
              <FiguraOrgaos selecionado={sistema} comAlerta={comAlerta} onSelecionar={(s) => setSistema(s === sistema ? null : s)} orientacao={orientacao} estiloFrente={estiloFrente} estiloCostas={estiloCostas} />
            ) : (
              <FiguraColuna selecionado={regiao} marcas={achados.dados ?? []} onSelecionar={(r) => setRegiao(r === regiao ? null : r)} orientacao={orientacao} />
            )}
          </div>
          <div className="mt-3 flex justify-center gap-1 rounded-lg border border-line bg-white p-1 text-sm">
            {(['frente', 'costas'] as const).map((o) => (
              <button key={o} onClick={() => setOrientacao(o)} aria-pressed={orientacao === o}
                className={`rounded-md px-3 py-1 font-medium ${orientacao === o ? 'bg-teal text-white' : 'text-muted hover:text-ink'}`}>
                {o === 'frente' ? 'Frente' : 'Costas'}
              </button>
            ))}
          </div>
          {vista === 'orgaos' && orientacao === 'frente' && (
            <div className="mt-2 flex justify-center gap-1 rounded-lg border border-line bg-white p-1 text-xs">
              {(['composta', 'camadas'] as const).map((e) => (
                <button key={e} onClick={() => setEstiloFrente(e)} aria-pressed={estiloFrente === e}
                  className={`rounded-md px-2.5 py-1 font-medium ${estiloFrente === e ? 'bg-teal-soft text-teal-deep' : 'text-muted hover:text-ink'}`}>
                  {e === 'composta' ? 'Imagem única' : 'Em camadas'}
                </button>
              ))}
            </div>
          )}
          {vista === 'orgaos' && orientacao === 'costas' && (
            <div className="mt-2 flex justify-center gap-1 rounded-lg border border-line bg-white p-1 text-xs">
              {(['composta', 'camadas'] as const).map((e) => (
                <button key={e} onClick={() => setEstiloCostas(e)} aria-pressed={estiloCostas === e}
                  className={`rounded-md px-2.5 py-1 font-medium ${estiloCostas === e ? 'bg-teal-soft text-teal-deep' : 'text-muted hover:text-ink'}`}>
                  {e === 'composta' ? 'Imagem única' : 'Em camadas'}
                </button>
              ))}
            </div>
          )}
          <p className="mt-3 text-center text-xs text-muted">
            {orientacao === 'frente'
              ? 'Vista frontal: o lado direito do corpo aparece à esquerda.'
              : 'Vista de costas: o lado direito do corpo aparece à direita (a relação se inverte).'}
          </p>
        </div>

        <div className="min-w-0 space-y-4">
          {vista === 'orgaos' ? (
            <PainelOrgaos sistemas={sistemas.dados ?? []} marcadores={marcadores.dados ?? []} achados={achados.dados ?? []} selecionado={sistema} onSelecionar={setSistema} />
          ) : (
            <PainelColuna achados={achados.dados ?? []} selecionado={regiao} onSelecionar={setRegiao} />
          )}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ Órgãos */

function Chip({ ativo, alerta, onClick, children }: { ativo: boolean; alerta?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-pressed={ativo}
      className={`rounded-full border px-3 py-1 text-sm ${ativo ? 'border-teal bg-teal text-white' : 'border-line bg-white text-muted hover:border-teal hover:text-teal'}`}>
      {children}
      {alerta && <span className="ml-1.5 inline-block h-1.5 w-1.5 -translate-y-0.5 rounded-full bg-alto align-middle" />}
    </button>
  )
}

function PainelOrgaos({ sistemas, marcadores, achados, selecionado, onSelecionar }: { sistemas: Sistema[]; marcadores: Marcador[]; achados: Achado[]; selecionado: string | null; onSelecionar: (s: string | null) => void }) {
  const atual = sistemas.find((s) => s.id === selecionado)
  const lista = marcadores.filter((m) => m.sistema === selecionado)
  const comDados = sistemas.filter((s) => s.marcadores > 0)
  const achadosRenais = selecionado === 'rins' ? achados.filter((a) => a.regiao === 'renal') : []

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {comDados.map((s) => (
          <Chip key={s.id} ativo={s.id === selecionado} alerta={s.fora > 0} onClick={() => onSelecionar(s.id === selecionado ? null : s.id)}>
            {s.nome}
          </Chip>
        ))}
      </div>

      {!atual ? (
        <Painel>
          <p className="pt-5 text-sm text-muted">
            Toque em um órgão ou em uma das áreas acima. Contorno tracejado laranja indica pelo menos um marcador fora da referência no último resultado.
            {' '}Inflamação e vitaminas não têm um órgão próprio na figura; Sangue destaca o baço e a circulação (em camadas).
          </p>
        </Painel>
      ) : (
        <Painel titulo={atual.nome} acoes={<span className="text-sm text-muted">{atual.marcadores} marcadores{atual.fora ? `, ${atual.fora} fora da referência` : ''}</span>}>
          {atual.id === 'sangue' && <p className="mb-3 text-xs text-muted">Baço destacado na figura; a circulação aparece na vista em camadas.</p>}
          {atual.id === 'proteinas' && <p className="mb-3 text-xs text-muted">A albumina e a maior parte das proteínas do sangue são produzidas pelo fígado.</p>}
          {atual.id === 'testiculos' && <p className="mb-3 text-xs text-muted">Região marcada de forma esquemática — a ilustração não desenha a genitália.</p>}
          {lista.length > 0 && (
            <ul className="grid gap-3 sm:grid-cols-2">
              {lista.map((m) => <MiniMarcador key={m.id} marcador={m} />)}
            </ul>
          )}
          {achadosRenais.length > 0 && (
            <div className={lista.length > 0 ? 'mt-5 border-t border-line pt-4' : ''}>
              <h3 className="mb-3 text-sm font-semibold text-muted">Achados de imagem</h3>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <img src="/anatomia/costas/rins-corte-calculos.webp" alt="Ilustração esquemática de rins em corte com cálculos"
                  className="w-full max-w-[220px] shrink-0 rounded-xl border border-line" />
                <div className="min-w-0 flex-1">
                  <p className="mb-2 text-xs text-muted">
                    Ilustração esquemática — não representa a posição, o tamanho ou a quantidade reais dos cálculos.
                  </p>
                  <ol className="relative space-y-4 border-l-2 border-line pl-5">
                    {achadosRenais.map((a, i) => <ItemAchado key={`${a.arquivo}-${i}`} achado={a} />)}
                  </ol>
                </div>
              </div>
            </div>
          )}
        </Painel>
      )}
    </>
  )
}

function MiniMarcador({ marcador }: { marcador: Marcador }) {
  const serie = useApi<Serie>(`/api/marcadores/${marcador.id}`)
  const ultimo = serie.dados?.pontos.at(-1)
  return (
    <li>
      <a href={href('evolucao', { m: marcador.id })} className="block rounded-xl border border-line p-3 hover:border-teal">
        <div className="flex items-start justify-between gap-2">
          <div>
            <div className="text-sm font-semibold">{marcador.nome}</div>
            <div className="text-lg font-semibold tabular-nums">{fmtNum(marcador.ultimo_valor)} <span className="text-xs font-normal text-muted">{marcador.unidade}</span></div>
          </div>
          <BadgeClassificacao valor={marcador.classificacao} />
        </div>
        {serie.dados && <GraficoMarcador pontos={serie.dados.pontos} altura={64} compacto />}
        <div className="mt-1 text-xs text-muted">
          {fmtData(marcador.ultima_data)}, ref. {ultimo ? fmtReferencia(ultimo.ref_min, ultimo.ref_max) : '—'}
        </div>
      </a>
    </li>
  )
}

/* ---------------------------------------------------- Coluna e articulações */

export const DETALHE_REGIAO: Record<string, { src: string; alt: string }> = {
  cervical: { src: '/anatomia/costas/coluna-cervical-detalhe.webp', alt: 'Ampliação didática da coluna cervical' },
  lombar: { src: '/anatomia/costas/coluna-lombossacra-detalhe.webp', alt: 'Ampliação didática da coluna lombossacra' },
  renal: { src: '/anatomia/costas/rins-corte-calculos.webp', alt: 'Ilustração esquemática de rins em corte com cálculos' },
}

export function PainelColuna({ achados, selecionado, onSelecionar }: { achados: Achado[]; selecionado: string | null; onSelecionar: (r: string | null) => void }) {
  const porRegiao = useMemo(() => {
    const m = new Map<string, Achado[]>()
    achados.forEach((a) => m.set(a.regiao, [...(m.get(a.regiao) ?? []), a]))
    return m
  }, [achados])

  const visiveis = selecionado ? [[selecionado, porRegiao.get(selecionado) ?? []] as const] : [...porRegiao.entries()]

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {[...porRegiao.keys()].map((r) => (
          <Chip key={r} ativo={r === selecionado} onClick={() => onSelecionar(r === selecionado ? null : r)}>
            {REGIOES[r] ?? r} ({porRegiao.get(r)!.length})
          </Chip>
        ))}
      </div>

      {achados.length === 0 && (
        <Painel>
          <p className="pt-5 text-sm text-muted">
            Nenhum achado encontrado. Os achados vêm da conclusão dos laudos de ressonância, tomografia, raio-X e ultrassom, e do arquivo achados_manuais.json no servidor.
          </p>
        </Painel>
      )}

      {visiveis.map(([r, lista]) => (
        <Painel key={r} titulo={REGIOES[r] ?? r}>
          <div className={DETALHE_REGIAO[r] ? 'flex flex-col gap-4 sm:flex-row sm:items-start' : undefined}>
            {DETALHE_REGIAO[r] && (
              <img src={DETALHE_REGIAO[r].src} alt={DETALHE_REGIAO[r].alt}
                className="w-full max-w-[200px] shrink-0 self-center rounded-xl border border-line sm:self-start" />
            )}
            <div className="min-w-0 flex-1">
              {lista.length === 0 ? (
                <p className="text-sm text-muted">Nenhum achado registrado nesta região.</p>
              ) : (
                <ol className="relative space-y-4 border-l-2 border-line pl-5">
                  {lista.map((a, i) => <ItemAchado key={`${a.arquivo}-${i}`} achado={a} />)}
                </ol>
              )}
            </div>
          </div>
        </Painel>
      ))}

      <p className="text-xs leading-relaxed text-muted">
        O texto de cada achado é copiado da conclusão do laudo; as etiquetas são detectadas automaticamente e podem errar. Pontos laranja marcam níveis citados em laudos; pontos verde-escuros, registros manuais.
      </p>
    </>
  )
}

function ItemAchado({ achado: a }: { achado: Achado }) {
  const manual = a.origem === 'manual'
  return (
    <li className="relative">
      <span className={`absolute top-1.5 -left-[27px] h-3 w-3 rounded-full border-2 border-white ${manual ? 'bg-teal-deep' : 'bg-alto'}`} aria-hidden />
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-sm font-semibold tabular-nums">{fmtData(a.data)}</span>
        <span className="text-sm text-muted">
          {MODALIDADES[a.modalidade] ?? a.modalidade}
          {a.lado && `, lado ${a.lado}`}
          {manual && ', registro manual'}
        </span>
      </div>
      {a.titulo && <p className="mt-1 font-semibold">{a.titulo}</p>}
      {(a.niveis.length > 0 || a.termos.length > 0) && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {a.niveis.map((n) => {
            const historico = (a.niveis_historicos ?? []).includes(n)
            return (
              <span
                key={n}
                title={historico ? 'Citado no laudo como resolvido/anterior, comparado ao exame anterior' : undefined}
                className={`rounded-md px-2 py-0.5 text-xs font-semibold ${historico ? 'bg-canvas text-muted line-through decoration-1' : 'bg-ink text-white'}`}
              >
                {n}
                {historico && <span className="ml-1 font-normal not-italic no-underline">(anterior)</span>}
              </span>
            )
          })}
          {a.termos.map((t) => <span key={t} className="rounded-md bg-alto-soft px-2 py-0.5 text-xs font-medium text-alto">{TERMOS[t] ?? t}</span>)}
        </div>
      )}
      {a.trecho && <blockquote className="mt-2 max-w-prose rounded-lg bg-canvas px-3 py-2 text-sm leading-relaxed">{a.trecho}</blockquote>}
      <p className="mt-1 truncate text-xs text-muted" title={a.arquivo}>{a.arquivo}</p>
    </li>
  )
}
