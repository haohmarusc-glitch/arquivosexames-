import type { KeyboardEvent } from 'react'
import {
  AORTA_CAMADAS, CORPO, DECORATIVOS_COSTAS_CAMADAS, DECORATIVOS_FRENTE_CAMADAS, ORGAOS_COSTAS,
  ORGAOS_COSTAS_CAMADAS, ORGAOS_FRENTE, ORGAOS_FRENTE_CAMADAS, PULMOES_FRENTE,
  type Caixa, type OrgaoCostasCamadas, type OrgaoImagem,
} from './formasCorpo'

const VIEWBOX = '40 8 240 640'
const ALERTA = '#b8661f'
const SELECAO = '#1d5b5a'

function aoTeclar(acao: () => void) {
  return (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      acao()
    }
  }
}


/** Encaixa uma imagem (por proporcao largura/altura) dentro da caixa, do
 * jeito que "object-fit: contain" faria — sem distorcer, centralizada. */
function encaixar(caixa: Caixa, proporcao: number) {
  const propCaixa = caixa.w / caixa.h
  const w = propCaixa > proporcao ? caixa.h * proporcao : caixa.w
  const h = propCaixa > proporcao ? caixa.h : caixa.w / proporcao
  return { x: caixa.x + (caixa.w - w) / 2, y: caixa.y + (caixa.h - h) / 2, w, h }
}

/** Gradiente do corpo e as animacoes (batimento, respiracao, fluxo) — uma so
 * instancia deste bloco por pagina, entao os nomes levam o prefixo "ms-"
 * para nao colidir com o resto do app. Paradas com prefers-reduced-motion
 * (regra global no index.css). */
function DefsEAnimacoes() {
  return (
    <defs>
      <radialGradient id="gBody" cx="42%" cy="18%" r="85%">
        <stop offset="0%" stopColor="#F3F8F8" />
        <stop offset="70%" stopColor="#E7F0F0" />
        <stop offset="100%" stopColor="#D7E6E6" />
      </radialGradient>
      <style>{`
        @keyframes ms-heartbeat {
          0%, 100% { transform: scale(1); }
          16% { transform: scale(1.07); }
          32% { transform: scale(.99); }
          46% { transform: scale(1.05); }
          62% { transform: scale(1); }
        }
        @keyframes ms-breathe {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.03); }
        }
        @keyframes ms-flow { to { stroke-dashoffset: -24; } }
        @keyframes ms-alerta { 0%, 100% { stroke-opacity: .55; } 50% { stroke-opacity: 1; } }
        .ms-coracao { transform-box: fill-box; transform-origin: center; animation: ms-heartbeat 1.1s ease-in-out infinite; }
        .ms-pulmao { transform-box: fill-box; transform-origin: center; animation: ms-breathe 4.4s ease-in-out infinite; }
        .ms-aorta-fluxo { stroke-dasharray: 5 7; animation: ms-flow 1.1s linear infinite; }
        .ms-alerta-contorno { animation: ms-alerta 1.6s ease-in-out infinite; }
      `}</style>
    </defs>
  )
}

/* ---------------------------------------------------------------- Órgãos */

export type Orientacao = 'frente' | 'costas'
export type EstiloFrente = 'composta' | 'camadas'
export type EstiloCostas = 'composta' | 'camadas'

interface PropsOrgaos {
  selecionado: string | null
  comAlerta: Set<string>
  onSelecionar: (sistema: string) => void
  orientacao?: Orientacao
  estiloFrente?: EstiloFrente
  estiloCostas?: EstiloCostas
}

/** Um órgão clicável: imagem "contida" na caixa + uma elipse invisível do
 * tamanho da caixa para clique/foco/estado (a imagem em si não recebe
 * eventos — pointer-events:none — para o hit-target não virar um retângulo
 * cru sobre fundo transparente). */
function Organ({ o, base, ativo, alerta, esmaecido, onSelecionar }: { o: OrgaoImagem; base: string; ativo: boolean; alerta: boolean; esmaecido: boolean; onSelecionar: (s: string) => void }) {
  const img = encaixar(o.caixa, o.proporcao)
  const cx = o.caixa.x + o.caixa.w / 2
  const cy = o.caixa.y + o.caixa.h / 2
  const imgClasse = o.id === 'coracao' ? 'ms-coracao' : undefined
  const elipseClasse = ['cursor-pointer focus:outline-none']
  if (alerta && !ativo) elipseClasse.push('ms-alerta-contorno')
  return (
    <g opacity={esmaecido ? 0.45 : 1} className="transition-opacity">
      {o.arquivo && <image href={`${base}${o.arquivo}`} x={img.x} y={img.y} width={img.w} height={img.h} style={{ pointerEvents: 'none' }} className={imgClasse} />}
      <ellipse
        cx={cx}
        cy={cy}
        rx={o.caixa.w / 2}
        ry={o.caixa.h / 2}
        fill={o.arquivo ? 'transparent' : 'rgba(200,120,90,.14)'}
        stroke={ativo ? SELECAO : alerta ? ALERTA : 'transparent'}
        strokeWidth={ativo ? 2.4 : alerta ? 2 : 0}
        strokeDasharray={alerta && !ativo ? '4 2.5' : undefined}
        className={elipseClasse.join(' ')}
        role="button"
        tabIndex={0}
        aria-pressed={ativo}
        aria-label={`${o.nome}${alerta ? ', com marcadores fora da referência' : ''}`}
        onClick={() => onSelecionar(o.sistema)}
        onKeyDown={aoTeclar(() => onSelecionar(o.sistema))}
      >
        <title>{o.nome}</title>
      </ellipse>
    </g>
  )
}

/** Como Organ, mas para orgaos de costas "em camadas": o PNG ja ocupa o
 * canvas inteiro (o orgao vem posicionado no lugar certo dentro dele), entao
 * a imagem e desenhada em tela cheia — so a elipse de clique usa a caixa. */
function OrganCostasCamadas({ o, ativo, alerta, esmaecido, onSelecionar }: { o: OrgaoCostasCamadas; ativo: boolean; alerta: boolean; esmaecido: boolean; onSelecionar: (s: string) => void }) {
  const cx = o.caixa.x + o.caixa.w / 2
  const cy = o.caixa.y + o.caixa.h / 2
  const imgClasse = o.id === 'coracao' ? 'ms-coracao' : undefined
  const elipseClasse = ['cursor-pointer focus:outline-none']
  if (alerta && !ativo) elipseClasse.push('ms-alerta-contorno')
  return (
    <g opacity={esmaecido ? 0.45 : 1} className="transition-opacity">
      <image href={`/anatomia/${o.arquivo}`} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" style={{ pointerEvents: 'none' }} className={imgClasse} />
      <ellipse
        cx={cx} cy={cy} rx={o.caixa.w / 2} ry={o.caixa.h / 2}
        fill="transparent"
        stroke={ativo ? SELECAO : alerta ? ALERTA : 'transparent'}
        strokeWidth={ativo ? 2.4 : alerta ? 2 : 0}
        strokeDasharray={alerta && !ativo ? '4 2.5' : undefined}
        className={elipseClasse.join(' ')}
        role="button"
        tabIndex={0}
        aria-pressed={ativo}
        aria-label={`${o.nome}${alerta ? ', com marcadores fora da referência' : ''}`}
        onClick={() => onSelecionar(o.sistema)}
        onKeyDown={aoTeclar(() => onSelecionar(o.sistema))}
      >
        <title>{o.nome}</title>
      </ellipse>
    </g>
  )
}

export function FiguraOrgaos({ selecionado, comAlerta, onSelecionar, orientacao = 'frente', estiloFrente = 'composta', estiloCostas = 'composta' }: PropsOrgaos) {
  const naoOrgao = ['sangue', 'inflamacao', 'vitaminas', 'outros', 'hormonios', 'prostata', 'proteinas']

  if (orientacao === 'costas' && estiloCostas === 'composta') {
    return (
      <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label="Figura do corpo visto de costas, com rins selecionáveis">
        <DefsEAnimacoes />
        <image href="/anatomia/costas/orgaos-costas.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" />
        {ORGAOS_COSTAS.map((o) => {
          const ativo = selecionado === o.sistema
          const alerta = comAlerta.has(o.sistema)
          return (
            <ellipse
              key={o.id}
              cx={o.caixa.x + o.caixa.w / 2}
              cy={o.caixa.y + o.caixa.h / 2}
              rx={o.caixa.w / 2}
              ry={o.caixa.h / 2}
              fill="transparent"
              stroke={ativo ? SELECAO : alerta ? ALERTA : 'rgba(255,255,255,.6)'}
              strokeWidth={ativo ? 2.6 : 1.6}
              strokeDasharray={alerta && !ativo ? '4 2.5' : undefined}
              className={`cursor-pointer focus:outline-none ${alerta && !ativo ? 'ms-alerta-contorno' : ''}`}
              role="button"
              tabIndex={0}
              aria-pressed={ativo}
              aria-label={`${o.nome} (visto de costas)${alerta ? ', com marcadores fora da referência' : ''}`}
              onClick={() => onSelecionar(o.sistema)}
              onKeyDown={aoTeclar(() => onSelecionar(o.sistema))}
            >
              <title>{o.nome}</title>
            </ellipse>
          )
        })}
      </svg>
    )
  }

  if (orientacao === 'costas' && estiloCostas === 'camadas') {
    return (
      <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label="Figura do corpo visto de costas (em camadas), com órgãos selecionáveis">
        <DefsEAnimacoes />
        <defs><clipPath id="clipCorpoCostas"><path d={CORPO} /></clipPath></defs>
        <image href="/anatomia/costas/esqueleto-costas.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" />
        <image
          href="/anatomia/costas/musculatura-costas.webp"
          x={40} y={8} width={240} height={640}
          preserveAspectRatio="xMidYMid slice"
          opacity={0.35}
          style={{ pointerEvents: 'none' }}
        />
        <image href="/anatomia/costas/sistema-arterial-costas.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" opacity={0.55} clipPath="url(#clipCorpoCostas)" />
        <image href="/anatomia/costas/sistema-venoso-costas.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" opacity={0.6} clipPath="url(#clipCorpoCostas)" />
        {DECORATIVOS_COSTAS_CAMADAS.map((d) => (
          <image
            key={d.id} href={`/anatomia/${d.arquivo}`} x={40} y={8} width={240} height={640}
            preserveAspectRatio="xMidYMid slice" className="ms-pulmao"
            style={{ pointerEvents: 'none', ...(d.id === 'pulmaoE' ? { animationDelay: '-1.4s' } : {}) }}
          />
        ))}
        {ORGAOS_COSTAS_CAMADAS.map((o) => (
          <OrganCostasCamadas
            key={o.id}
            o={o}
            ativo={selecionado === o.sistema}
            alerta={comAlerta.has(o.sistema)}
            esmaecido={Boolean(selecionado) && selecionado !== o.sistema && !naoOrgao.includes(selecionado ?? '')}
            onSelecionar={onSelecionar}
          />
        ))}
      </svg>
    )
  }

  if (estiloFrente === 'camadas') {
    return (
      <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label="Figura do corpo visto de frente (em camadas), com órgãos selecionáveis">
        <DefsEAnimacoes />
        <image href="/anatomia/esqueleto-frontal.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" />
        <image
          href="/anatomia/musculatura-frontal.webp"
          x={40} y={8} width={240} height={640}
          preserveAspectRatio="xMidYMid slice"
          opacity={0.35}
          style={{ pointerEvents: 'none' }}
        />
        <defs><clipPath id="clipCorpo"><path d={CORPO} /></clipPath></defs>
        <image href="/anatomia/sistema-arterial.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" opacity={0.55} clipPath="url(#clipCorpo)" />
        <image href="/anatomia/sistema-venoso.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" opacity={0.6} clipPath="url(#clipCorpo)" />
        <path
          d={AORTA_CAMADAS}
          fill="none"
          stroke="#c9505e"
          strokeWidth={2.2}
          strokeLinecap="round"
          opacity={selecionado === 'sangue' ? 0.75 : 0}
          className={selecionado === 'sangue' ? 'ms-aorta-fluxo' : undefined}
          style={{ transition: 'opacity .3s' }}
        />
        {DECORATIVOS_FRENTE_CAMADAS.map((d) => {
          const img = encaixar(d.caixa, d.proporcao)
          return <image key={d.id} href={`/anatomia/${d.arquivo}`} x={img.x} y={img.y} width={img.w} height={img.h} className={d.id.startsWith('pulmao') ? 'ms-pulmao' : undefined} style={d.id === 'pulmaoE' ? { animationDelay: '-1.4s' } : undefined} />
        })}
        {ORGAOS_FRENTE_CAMADAS.map((o) => (
          <Organ
            key={o.id}
            o={o}
            base="/anatomia/"
            ativo={selecionado === o.sistema}
            alerta={comAlerta.has(o.sistema)}
            esmaecido={Boolean(selecionado) && selecionado !== o.sistema && !naoOrgao.includes(selecionado ?? '')}
            onSelecionar={onSelecionar}
          />
        ))}
      </svg>
    )
  }

  const coracaoC = ORGAOS_FRENTE.find((o) => o.id === 'coracao')!.caixa
  const coracaoCentro = { x: coracaoC.x + coracaoC.w / 2, y: coracaoC.y + coracaoC.h / 2 }
  const pulmaoDCentro = { x: PULMOES_FRENTE.pulmaoD.x + PULMOES_FRENTE.pulmaoD.w / 2, y: PULMOES_FRENTE.pulmaoD.y + PULMOES_FRENTE.pulmaoD.h / 2 }
  const pulmaoECentro = { x: PULMOES_FRENTE.pulmaoE.x + PULMOES_FRENTE.pulmaoE.w / 2, y: PULMOES_FRENTE.pulmaoE.y + PULMOES_FRENTE.pulmaoE.h / 2 }
  const IMG_FRENTE = '/anatomia/orgaos-frente.webp'

  return (
    <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label="Figura do corpo visto de frente, com órgãos selecionáveis">
      <DefsEAnimacoes />
      <defs>
        <clipPath id="clipCoracao"><ellipse cx={coracaoCentro.x} cy={coracaoCentro.y} rx={coracaoC.w / 2} ry={coracaoC.h / 2} /></clipPath>
        <clipPath id="clipPulmaoD"><ellipse cx={pulmaoDCentro.x} cy={pulmaoDCentro.y} rx={PULMOES_FRENTE.pulmaoD.w / 2} ry={PULMOES_FRENTE.pulmaoD.h / 2} /></clipPath>
        <clipPath id="clipPulmaoE"><ellipse cx={pulmaoECentro.x} cy={pulmaoECentro.y} rx={PULMOES_FRENTE.pulmaoE.w / 2} ry={PULMOES_FRENTE.pulmaoE.h / 2} /></clipPath>
      </defs>
      {/* Imagem composta unica (mesmo tratamento da vista de costas): ja mostra
          todos os orgaos, musculos e vasos numa unica ilustracao coesa. */}
      <image href={IMG_FRENTE} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" />
      {/* "Batimento"/"respiracao": uma copia recortada (clip-path) da MESMA
          imagem, ampliada em torno do centro do orgao — sem precisar de um
          recorte separado do orgao (evita descolar cor/traço do resto). */}
      <image
        href={IMG_FRENTE} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice"
        clipPath="url(#clipPulmaoD)" className="ms-pulmao" style={{ transformOrigin: `${pulmaoDCentro.x}px ${pulmaoDCentro.y}px`, pointerEvents: 'none' }}
      />
      <image
        href={IMG_FRENTE} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice"
        clipPath="url(#clipPulmaoE)" className="ms-pulmao" style={{ transformOrigin: `${pulmaoECentro.x}px ${pulmaoECentro.y}px`, animationDelay: '-1.4s', pointerEvents: 'none' }}
      />
      <image
        href={IMG_FRENTE} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice"
        clipPath="url(#clipCoracao)" className="ms-coracao" style={{ transformOrigin: `${coracaoCentro.x}px ${coracaoCentro.y}px`, pointerEvents: 'none' }}
      />
      {ORGAOS_FRENTE.map((o) => (
        <Organ
          key={o.id}
          o={o}
          base="/anatomia/"
          ativo={selecionado === o.sistema}
          alerta={comAlerta.has(o.sistema)}
          esmaecido={Boolean(selecionado) && selecionado !== o.sistema && !naoOrgao.includes(selecionado ?? '')}
          onSelecionar={onSelecionar}
        />
      ))}
    </svg>
  )
}

/* ------------------------------------------------------ Coluna e articulações */

const SEGMENTOS: { regiao: 'cervical' | 'toracica' | 'lombar'; letra: string; qtd: number; topo: number; altura: number; largura: [number, number] }[] = [
  { regiao: 'cervical', letra: 'C', qtd: 7, topo: 71, altura: 3.64, largura: [11, 14] },
  { regiao: 'toracica', letra: 'T', qtd: 12, topo: 107, altura: 6.08, largura: [15, 20] },
  { regiao: 'lombar', letra: 'L', qtd: 5, topo: 198, altura: 8.3, largura: [22, 28] },
]
const GAP = 1.5
const TOPO_SACRO = 247

export const VERTEBRAS = SEGMENTOS.flatMap((s) =>
  Array.from({ length: s.qtd }, (_, i) => {
    const w = s.largura[0] + ((s.largura[1] - s.largura[0]) * i) / Math.max(1, s.qtd - 1)
    return { nome: `${s.letra}${i + 1}`, regiao: s.regiao, y: s.topo + i * (s.altura + GAP), h: s.altura, w }
  }),
)

/** Posição vertical do disco de um nível ("C5-C6", "L5-S1") ou de uma vértebra ("L4"). */
export function yDoNivel(nivel: string): number | null {
  const [a] = nivel.toUpperCase().split('-')
  const v = VERTEBRAS.find((x) => x.nome === a)
  if (!v) return null
  return nivel.includes('-') ? v.y + v.h + GAP / 2 : v.y + v.h / 2
}

// Posicoes calibradas contra coluna/frente.webp (pontos reais: ombro py~345,
// cotovelo py~650, punho py~910, quadril py~890, joelho py~1301, tornozelo
// py~1712, convertidos via vy = 8 + (py-16)*0.3254). cx e' o lado da pessoa
// na vista de FRENTE (direito = baixo, como na convencao do app); para a
// vista de costas, a lateralidade se inverte (ver espelharX em FiguraColuna).
export const ARTICULACOES: { regiao: string; lado: 'direito' | 'esquerdo'; cx: number; cy: number; r: number }[] = [
  { regiao: 'ombro', lado: 'direito', cx: 86, cy: 115, r: 11 },
  { regiao: 'ombro', lado: 'esquerdo', cx: 233, cy: 115, r: 11 },
  { regiao: 'cotovelo', lado: 'direito', cx: 80, cy: 214, r: 8 },
  { regiao: 'cotovelo', lado: 'esquerdo', cx: 239, cy: 214, r: 8 },
  { regiao: 'punho_mao', lado: 'direito', cx: 60, cy: 299, r: 8 },
  { regiao: 'punho_mao', lado: 'esquerdo', cx: 259, cy: 299, r: 8 },
  { regiao: 'quadril', lado: 'direito', cx: 119, cy: 292, r: 11 },
  { regiao: 'quadril', lado: 'esquerdo', cx: 200, cy: 292, r: 11 },
  { regiao: 'joelho', lado: 'direito', cx: 129, cy: 426, r: 10 },
  { regiao: 'joelho', lado: 'esquerdo', cx: 190, cy: 426, r: 10 },
  { regiao: 'tornozelo_pe', lado: 'direito', cx: 122, cy: 560, r: 8 },
  { regiao: 'tornozelo_pe', lado: 'esquerdo', cx: 197, cy: 560, r: 8 },
]


/** Espelha um cx horizontalmente em torno do centro do viewBox (160) — usado
 * so na vista de costas, onde a lateralidade da pessoa se inverte na tela. */
const espelharX = (cx: number) => 320 - cx

export interface Marca {
  regiao: string
  niveis: string[]
  niveis_historicos?: string[]
  lado: string
  origem: string
}

interface PropsColuna {
  selecionado: string | null
  marcas: Marca[]
  onSelecionar: (regiao: string) => void
  orientacao?: Orientacao
}

const NOME_SEGMENTO: Record<string, string> = { cervical: 'Coluna cervical', toracica: 'Coluna torácica', lombar: 'Coluna lombar', sacral: 'Sacro' }

export function FiguraColuna({ selecionado, marcas, onSelecionar, orientacao = 'frente' }: PropsColuna) {
  const regioesComAchado = new Set(marcas.map((m) => m.regiao))
  const niveis = marcas.flatMap((m) => m.niveis.map((n) => ({ n, origem: m.origem, historico: (m.niveis_historicos ?? []).includes(n) })))
  const ladosComAchado = (regiao: string) => {
    const ms = marcas.filter((m) => m.regiao === regiao)
    const lados = new Set<string>()
    ms.forEach((m) => (m.lado === 'direito' || m.lado === 'esquerdo' ? lados.add(m.lado) : (lados.add('direito'), lados.add('esquerdo'))))
    return lados
  }

  const segmento = (regiao: string, filhos: React.ReactNode, rotulo: string) => {
    const ativo = selecionado === regiao
    return (
      <g
        key={regiao}
        role="button"
        tabIndex={0}
        aria-pressed={ativo}
        aria-label={`${rotulo}${regioesComAchado.has(regiao) ? ', com achados' : ''}`}
        className="cursor-pointer focus:outline-none"
        onClick={() => onSelecionar(regiao)}
        onKeyDown={aoTeclar(() => onSelecionar(regiao))}
      >
        <title>{rotulo}</title>
        {filhos}
      </g>
    )
  }

  const corVertebra = (regiao: string) => {
    if (selecionado === regiao) return '#8cc3bf'
    if (regioesComAchado.has(regiao)) return '#f3d9bf'
    return '#f7f4ee'
  }

  return (
    <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label={`Figura da coluna e articulações, vista de ${orientacao === 'costas' ? 'costas' : 'frente'}`}>
      <image href={`/anatomia/coluna-${orientacao}.webp`} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" />
      {SEGMENTOS.map((s) =>
        segmento(
          s.regiao,
          VERTEBRAS.filter((v) => v.regiao === s.regiao).map((v) => (
            <rect key={v.nome} x={160 - v.w / 2} y={v.y} width={v.w} height={v.h} rx={Math.min(3, v.h / 2.5)} fill={corVertebra(s.regiao)} fillOpacity={selecionado === s.regiao ? 0.75 : 0.55} stroke={selecionado === s.regiao ? SELECAO : "#b9cfcf"} strokeWidth={selecionado === s.regiao ? 1.4 : 1} />
          )),
          NOME_SEGMENTO[s.regiao],
        ),
      )}
      {segmento(
        'sacral',
        <path d={`M146,${TOPO_SACRO} L174,${TOPO_SACRO} C174,${TOPO_SACRO + 22} 168,${TOPO_SACRO + 40} 160,${TOPO_SACRO + 50} C152,${TOPO_SACRO + 40} 146,${TOPO_SACRO + 22} 146,${TOPO_SACRO} Z`} fill={corVertebra('sacral')} fillOpacity={selecionado === 'sacral' ? 0.75 : 0.55} stroke={selecionado === 'sacral' ? SELECAO : '#b9cfcf'} />,
        NOME_SEGMENTO.sacral,
      )}

      {/* marcadores nos níveis citados */}
      {niveis.map(({ n, origem, historico }, i) => {
        const y = yDoNivel(n)
        if (y == null) return null
        const cor = historico ? '#9aa7ab' : origem === 'manual' ? SELECAO : ALERTA
        return (
          <g key={`${n}-${i}`} pointerEvents="none" opacity={historico ? 0.7 : 1}>
            <line x1={176} x2={206} y1={y} y2={y} stroke={cor} strokeWidth={1.2} strokeDasharray={historico ? '2 2' : undefined} />
            <circle cx={160} cy={y} r={origem === 'manual' ? 4.2 : 3.6} fill={cor} stroke="#fff" strokeWidth={1.2} />
            <text x={209} y={y + 3.5} fontSize={10} fontWeight={600} fill={historico ? '#5b7178' : '#17313a'}>
              {n}{historico ? ' (ant.)' : ''}
            </text>
          </g>
        )
      })}

      {ARTICULACOES.map((a) => {
        const ativo = selecionado === a.regiao
        const comAchado = regioesComAchado.has(a.regiao) && ladosComAchado(a.regiao).has(a.lado)
        const rotulo = `${a.regiao.replace('_', ' e ')} ${a.lado}`
        return (
          <circle
            key={`${a.regiao}-${a.lado}`}
            cx={orientacao === 'costas' ? espelharX(a.cx) : a.cx}
            cy={a.cy}
            r={a.r}
            fill={ativo ? '#8cc3bf' : comAchado ? '#f3d9bf' : '#f7f4ee'}
            fillOpacity={ativo || comAchado ? 0.7 : 0.4}
            stroke={ativo ? SELECAO : comAchado ? ALERTA : '#b9cfcf'}
            strokeWidth={ativo || comAchado ? 2 : 1}
            className="cursor-pointer focus:outline-none"
            role="button"
            tabIndex={0}
            aria-pressed={ativo}
            aria-label={`${rotulo}${comAchado ? ', com achados' : ''}`}
            onClick={() => onSelecionar(a.regiao)}
            onKeyDown={aoTeclar(() => onSelecionar(a.regiao))}
          >
            <title>{rotulo}</title>
          </circle>
        )
      })}
    </svg>
  )
}
