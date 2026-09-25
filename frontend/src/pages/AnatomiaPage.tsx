import { useMemo, useState } from 'react'
import { MODALIDADES, REGIOES, TERMOS, useApi, type Achado, type Marcador, type Serie, type Sistema } from '../api'
import { FiguraColuna, FiguraOrgaos, type EstiloCostas, type EstiloFrente, type Orientacao } from '../components/Anatomia'
import { BadgeClassificacao } from '../components/Badges'
import { GraficoMarcador } from '../components/GraficoMarcador'
import { Aviso, Painel } from '../components/Painel'
import { fmtData, fmtNum, fmtReferencia } from '../format'
import { href } from '../rota'
import { ALTURA_PERNAS, COR_VEIA, NOME_VEIA, marcasDasPernas, trajeto, trechoDoTrajeto } from '../veias'
import { COR_PATOLOGIA, DISCOS_DETALHE, GRAVIDADE, NOME_PATOLOGIA, PEDICULOS_DETALHE, faixasArtrodese, marcasDosAchados, vertebraDetalhe, vertebrasDaFaixa } from '../patologias'

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
  membros_inferiores: { src: '/anatomia/pernas-veias-detalhe.webp', alt: 'Ilustração das veias das pernas, vista de frente' },
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
            {DETALHE_REGIAO[r] && (r === 'membros_inferiores' ? <DetalhePernas achados={lista} /> : <DetalheComPatologias regiao={r} achados={lista} />)}
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

/* ------------------------------------------- Patologias na imagem de detalhe */

// Proporcao altura/largura das imagens de detalhe (para desenhar sem distorcer).
const PROPORCAO_DETALHE: Record<string, number> = { cervical: 1364 / 900, lombar: 1536 / 829 }

function DetalheComPatologias({ regiao, achados }: { regiao: string; achados: Achado[] }) {
  const img = DETALHE_REGIAO[regiao]
  const discos = DISCOS_DETALHE[regiao]
  const alt = 100 * (PROPORCAO_DETALHE[regiao] ?? 1)
  const marcas = useMemo(
    () => marcasDosAchados(achados).filter((m) => (m.tipo === 'fratura' ? vertebraDetalhe(regiao, m.nivel) : discos?.[m.nivel])),
    [achados, regiao, discos],
  )
  const faixas = faixasArtrodese(marcas)
  const tipos = GRAVIDADE.filter((t) => marcas.some((m) => m.tipo === t))
  const Y = (pct: number) => (pct / 100) * alt
  // Vista de COSTAS: esquerda da pessoa = esquerda da tela.
  const xs = (d: { xE: number; xD: number; xC: number }, lado: string) =>
    lado === 'bilateral' ? [d.xE, d.xD] : lado === 'esquerdo' ? [d.xE] : lado === 'direito' ? [d.xD] : [d.xC]

  return (
    <figure className="w-full max-w-[260px] shrink-0 self-center sm:self-start">
      <div className="relative overflow-hidden rounded-xl border border-line">
        <img src={img.src} alt={img.alt} className="block w-full" />
        {discos && marcas.length > 0 && (
          <svg viewBox={`0 0 100 ${alt}`} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
            {/* artrodese: hastes dos dois lados e um parafuso por vertebra */}
            {faixas.map((f) => {
              const vs = vertebrasDaFaixa(f).map((v) => vertebraDetalhe(regiao, v)).filter((v): v is NonNullable<typeof v> => v != null)
              const ped = PEDICULOS_DETALHE[regiao]
              if (vs.length < 2 || !ped) return null
              return (
                <g key={f.join()}>
                  {[ped.xE, ped.xD].map((x) => (
                    <g key={x}>
                      <line x1={x} x2={x} y1={Y(vs[0].y)} y2={Y(vs[vs.length - 1].y)} stroke={COR_PATOLOGIA.artrodese} strokeWidth={2.2} strokeLinecap="round" />
                      {vs.map((v, i) => <circle key={i} cx={x} cy={Y(v.y)} r={2.4} fill="#ced4da" stroke={COR_PATOLOGIA.artrodese} strokeWidth={1} />)}
                    </g>
                  ))}
                  <Etiqueta x={ped.xD + 4} y={Y(vs[0].y)} cor={COR_PATOLOGIA.artrodese} texto={`${vertebrasDaFaixa(f)[0]}–${vertebrasDaFaixa(f).slice(-1)[0]}`} />
                </g>
              )
            })}
            {marcas.map((m, i) => {
              if (m.tipo === 'artrodese') return null
              const cor = COR_PATOLOGIA[m.tipo]
              const op = m.historico ? 0.45 : 1
              if (m.tipo === 'fratura') {
                const v = vertebraDetalhe(regiao, m.nivel)!
                return (
                  <g key={i} opacity={op}>
                    <path d={`M${v.xC - 7},${Y(v.y) - 1.5} l3.5,3 l3.5,-3 l3.5,3 l3.5,-3`} fill="none" stroke={cor} strokeWidth={1.8} />
                    <Etiqueta x={v.xC + 9} y={Y(v.y)} cor={cor} texto={m.nivel} />
                  </g>
                )
              }
              const d = discos[m.nivel]
              if (m.tipo === 'degenerativo') return <circle key={i} cx={d.xC} cy={Y(d.y)} r={1.8} fill={cor} stroke="#fff" strokeWidth={0.6} opacity={op} />
              if (m.tipo === 'estenose' || m.tipo === 'listese') {
                return (
                  <g key={i} opacity={op}>
                    <ellipse cx={d.xC} cy={Y(d.y)} rx={6} ry={3} fill="none" stroke={cor} strokeWidth={1.6} />
                    <Etiqueta x={d.xC + 8} y={Y(d.y)} cor={cor} texto={m.nivel} />
                  </g>
                )
              }
              const [rx, ry] = m.tipo === 'hernia' ? [5.5, 2.6] : [4, 2]
              const pos = xs(d, m.lado)
              return (
                <g key={i} opacity={op}>
                  {pos.map((x, k) => (
                    <ellipse key={k} cx={x} cy={Y(d.y)} rx={rx} ry={ry} fill={cor} stroke="#fff" strokeWidth={0.7} />
                  ))}
                  <Etiqueta x={pos[0] < 50 ? pos[0] - rx - 1 : pos[pos.length - 1] + rx + 1} y={Y(d.y)} cor={cor} texto={m.nivel} fim={pos[0] < 50} />
                </g>
              )
            })}
          </svg>
        )}
      </div>
      {tipos.length > 0 && (
        <figcaption className="mt-2 space-y-1 text-xs text-muted">
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {tipos.map((t) => (
              <span key={t} className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: t === 'estenose' || t === 'listese' ? 'transparent' : COR_PATOLOGIA[t], border: `2px solid ${COR_PATOLOGIA[t]}` }} />
                {NOME_PATOLOGIA[t]}
              </span>
            ))}
          </div>
          <p>Ilustrativo: mostra só o laudo mais recente desta região (o que melhorou não aparece); nível e lado tirados do texto; posição aproximada, vista de costas (esquerda da pessoa à esquerda).</p>
        </figcaption>
      )}
    </figure>
  )
}

function DetalhePernas({ achados }: { achados: Achado[] }) {
  const img = DETALHE_REGIAO.membros_inferiores
  const marcas = useMemo(() => marcasDasPernas(achados), [achados])
  const tipos = (['trombose', 'insuficiencia'] as const).filter((t) => marcas.some((m) => m.tipo === t))
  const ladosComLaudo = new Set(achados.flatMap((a) => (a.lado === 'bilateral' || !a.lado ? ['direito', 'esquerdo'] : [a.lado])))
  const pontos = (ps: [number, number][]) => ps.map(([x, y]) => `${x},${y}`).join(' ')

  return (
    <figure className="w-full max-w-[220px] shrink-0 self-center sm:self-start">
      <div className="relative overflow-hidden rounded-xl border border-line bg-white">
        <img src={img.src} alt={img.alt} className="block w-full" />
        <svg viewBox={`0 0 100 ${ALTURA_PERNAS}`} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden>
          {marcas.map((m, i) => {
            const ps = trechoDoTrajeto(trajeto(m.lado), m.faixa)
            const cor = COR_VEIA[m.tipo]
            const meio = ps[Math.floor(ps.length / 2)]
            // Vista de FRENTE: perna direita da pessoa a esquerda da tela; etiqueta do lado de fora.
            const fora = m.lado === 'direito'
            return (
              <g key={i}>
                <polyline points={pontos(ps)} fill="none" stroke={cor} strokeOpacity={0.3} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" />
                <polyline points={pontos(ps)} fill="none" stroke={cor} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
                <Etiqueta x={fora ? 3 : 97} y={meio[1]} cor={cor} texto={m.tipo === 'trombose' ? 'Trombose' : 'Insuficiência'} fim={!fora} />
              </g>
            )
          })}
          {(['direito', 'esquerdo'] as const).filter((l) => ladosComLaudo.has(l) && !marcas.some((m) => m.lado === l)).map((l) => (
            <Etiqueta key={l} x={l === 'direito' ? 3 : 97} y={60} cor="#2b8a3e" texto="normal" fim={l === 'esquerdo'} />
          ))}
          <Etiqueta x={3} y={8} cor="#495057" texto="D" />
          <Etiqueta x={97} y={8} cor="#495057" texto="E" fim />
        </svg>
      </div>
      <figcaption className="mt-2 space-y-1 text-xs text-muted">
        {tipos.length > 0 && (
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            {tipos.map((t) => (
              <span key={t} className="flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: COR_VEIA[t] }} />
                {NOME_VEIA[t]}
              </span>
            ))}
          </div>
        )}
        <p>Ilustrativo: mostra só o laudo mais recente de cada perna; trecho aproximado tirado da conclusão, desenhado no trajeto da safena magna. Vista de frente (perna direita à esquerda).</p>
      </figcaption>
    </figure>
  )
}

function Etiqueta({ x, y, cor, texto, fim = false }: { x: number; y: number; cor: string; texto: string; fim?: boolean }) {
  return (
    <text x={x} y={y + 1.8} textAnchor={fim ? 'end' : 'start'} fontSize={5} fontWeight={700} fill={cor} stroke="#fff" strokeWidth={1.4} paintOrder="stroke">
      {texto}
    </text>
  )
}
