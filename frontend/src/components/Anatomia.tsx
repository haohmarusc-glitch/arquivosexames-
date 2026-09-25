import type { KeyboardEvent } from 'react'
import { ABREV_LADO, COR_PATOLOGIA, CURTO_PATOLOGIA, GRAVIDADE, faixasArtrodese, maisRecentesPorRegiao, marcasDosAchados, regiaoDoNivel, vertebrasDaFaixa, type MarcaPatologia } from '../patologias'
import {
  AORTA_CAMADAS, CORPO, DECORATIVOS_COSTAS_CAMADAS, DECORATIVOS_FRENTE_CAMADAS, ORGAOS_COSTAS,
  ORGAOS_COSTAS_CAMADAS, ORGAOS_FRENTE, ORGAOS_FRENTE_CAMADAS, PULMOES_FRENTE,
  type Caixa, type OrgaoCostasCamadas, type OrgaoImagem,
} from './formasCorpo'

const VIEWBOX = '40 8 240 640'
// As imagens "em camadas" (esqueleto, musculatura, vasos...) ocupam quase a
// altura toda; a imagem unica nova mostra o corpo inteiro (com as maos) menor.
// Para as duas vistas terem o mesmo tamanho, o grupo das camadas e reduzido
// alinhando topo da cabeca e planta dos pes (medidos no alfa das imagens):
// frente: camadas 13.2..591.2 -> imagem unica 80..572.7; costas: 13.1..630.4 -> 80..567.2.
// Tudo dentro do grupo (imagens, contorno CORPO, areas de clique) segue junto.
const escalaCamadas = (topo: number, base: number, topoAlvo: number, baseAlvo: number) => {
  const s = (baseAlvo - topoAlvo) / (base - topo)
  return `translate(${(160 * (1 - s)).toFixed(2)} ${(topoAlvo - topo * s).toFixed(2)}) scale(${s.toFixed(4)})`
}
const AJUSTE_CAMADAS_FRENTE = escalaCamadas(13.2, 591.2, 80, 572.7)
// Vista de costas em camadas: orgaos que ficam na FRENTE da coluna (tireoide,
// coracao, pancreas). Visto de costas, coluna, costelas e pulmoes ficam no meio
// do caminho: a imagem deles e desenhada antes do esqueleto; a area de clique
// e o contorno de selecao continuam por cima.
const ANTERIORES_COSTAS = ['tireoide', 'coracao', 'pancreas']
const AJUSTE_CAMADAS_COSTAS = escalaCamadas(13.1, 630.4, 80, 567.2)
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
        fill={o.arquivo ? 'transparent' : ativo ? 'rgba(29,91,90,.16)' : 'rgba(200,120,90,.14)'}
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
function OrganCostasCamadas({ o, ativo, alerta, esmaecido, onSelecionar, semImagem = false }: { o: OrgaoCostasCamadas; ativo: boolean; alerta: boolean; esmaecido: boolean; onSelecionar: (s: string) => void; semImagem?: boolean }) {
  const cx = o.caixa.x + o.caixa.w / 2
  const cy = o.caixa.y + o.caixa.h / 2
  const imgClasse = o.id === 'coracao' ? 'ms-coracao' : undefined
  const elipseClasse = ['cursor-pointer focus:outline-none']
  if (alerta && !ativo) elipseClasse.push('ms-alerta-contorno')
  return (
    <g opacity={esmaecido ? 0.45 : 1} className="transition-opacity">
      {!semImagem && <image href={`/anatomia/${o.arquivo}`} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" style={{ pointerEvents: 'none' }} className={imgClasse} />}
      {/* Orgao escondido atras da coluna (semImagem): selecionado, aparece em transparencia. */}
      {semImagem && ativo && <image href={`/anatomia/${o.arquivo}`} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" opacity={0.6} style={{ pointerEvents: 'none' }} className={imgClasse} />}
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
  // Sistemas sem orgao proprio na figura: selecionar um deles nao esmaece os orgaos.
  const naoOrgao = ['inflamacao', 'vitaminas', 'sorologias', 'outros']
  const destaca = (o: { sistema: string; tambem?: string[] }) => selecionado === o.sistema || Boolean(selecionado && o.tambem?.includes(selecionado))
  const esmaecer = (o: { sistema: string; tambem?: string[] }) => Boolean(selecionado) && !destaca(o) && !naoOrgao.includes(selecionado ?? '')

  if (orientacao === 'costas' && estiloCostas === 'composta') {
    return (
      <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label="Figura do corpo visto de costas, com órgãos selecionáveis">
        <DefsEAnimacoes />
        <image href="/anatomia/costas/orgaos-costas.webp" x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" />
        {ORGAOS_COSTAS.map((o) => {
          const ativo = destaca(o)
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
        <g transform={AJUSTE_CAMADAS_COSTAS}>
        <defs><clipPath id="clipCorpoCostas"><path d={CORPO} /></clipPath></defs>
        {ORGAOS_COSTAS_CAMADAS.filter((o) => ANTERIORES_COSTAS.includes(o.id)).map((o) => (
          <g key={o.id} opacity={esmaecer(o) ? 0.45 : 1} className="transition-opacity">
            <image href={`/anatomia/${o.arquivo}`} x={40} y={8} width={240} height={640} preserveAspectRatio="xMidYMid slice" style={{ pointerEvents: 'none' }} className={o.id === 'coracao' ? 'ms-coracao' : undefined} />
          </g>
        ))}
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
            semImagem={ANTERIORES_COSTAS.includes(o.id)}
            o={o}
            ativo={destaca(o)}
            alerta={comAlerta.has(o.sistema)}
            esmaecido={esmaecer(o)}
            onSelecionar={onSelecionar}
          />
        ))}
        </g>
      </svg>
    )
  }

  if (estiloFrente === 'camadas') {
    return (
      <svg viewBox={VIEWBOX} className="h-full w-full" role="group" aria-label="Figura do corpo visto de frente (em camadas), com órgãos selecionáveis">
        <DefsEAnimacoes />
        <g transform={AJUSTE_CAMADAS_FRENTE}>
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
            ativo={destaca(o)}
            alerta={comAlerta.has(o.sistema)}
            esmaecido={esmaecer(o)}
            onSelecionar={onSelecionar}
          />
        ))}
        </g>
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
          ativo={destaca(o)}
          alerta={comAlerta.has(o.sistema)}
          esmaecido={esmaecer(o)}
          onSelecionar={onSelecionar}
        />
      ))}
    </svg>
  )
}

/* ------------------------------------------------------ Coluna e articulações */

// Calibrado em 2026-09 numa grade do viewBox sobre coluna-frente.webp e
// coluna-costas.webp (as duas vistas ficam a no maximo ~3 unidades uma da outra):
// C1 ~72 (abaixo da mandibula/occipital), C7-T1 ~111 (base do pescoco),
// T12-L1 ~211 (12a costela), L5-S1 ~262 (topo do sacro), sacro 262..312.
const SEGMENTOS: { regiao: 'cervical' | 'toracica' | 'lombar'; letra: string; qtd: number; topo: number; altura: number; largura: [number, number] }[] = [
  { regiao: 'cervical', letra: 'C', qtd: 7, topo: 72, altura: 4.07, largura: [11, 14] },
  { regiao: 'toracica', letra: 'T', qtd: 12, topo: 111, altura: 6.83, largura: [15, 20] },
  { regiao: 'lombar', letra: 'L', qtd: 5, topo: 211, altura: 8.7, largura: [22, 28] },
]
const GAP = 1.5
const TOPO_SACRO = 262

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

// Posicoes calibradas em 2026-09 numa grade do viewBox (vx = 30.97 + px*0.36866,
// vy = 8 + py*0.36866) sobre coluna-frente.webp (cx, cy) e coluna-costas.webp
// (costas). A imagem de costas tem outra proporcao (corpo mais baixo), entao
// tem coordenadas proprias em vez de so espelhar a frente.
// cx: lado da pessoa na vista de FRENTE (direito = esquerda da tela);
// costas.cx ja e a posicao na tela de costas (direito = direita da tela).
export const ARTICULACOES: { regiao: string; lado: 'direito' | 'esquerdo'; cx: number; cy: number; r: number; costas: { cx: number; cy: number } }[] = [
  { regiao: 'ombro', lado: 'direito', cx: 102, cy: 123, r: 11, costas: { cx: 226, cy: 126 } },
  { regiao: 'ombro', lado: 'esquerdo', cx: 217, cy: 123, r: 11, costas: { cx: 91, cy: 126 } },
  { regiao: 'cotovelo', lado: 'direito', cx: 80, cy: 214, r: 8, costas: { cx: 244, cy: 230 } },
  { regiao: 'cotovelo', lado: 'esquerdo', cx: 239, cy: 214, r: 8, costas: { cx: 75, cy: 230 } },
  { regiao: 'punho_mao', lado: 'direito', cx: 60, cy: 299, r: 8, costas: { cx: 261, cy: 318 } },
  { regiao: 'punho_mao', lado: 'esquerdo', cx: 259, cy: 299, r: 8, costas: { cx: 59, cy: 318 } },
  { regiao: 'quadril', lado: 'direito', cx: 119, cy: 292, r: 11, costas: { cx: 204, cy: 314 } },
  { regiao: 'quadril', lado: 'esquerdo', cx: 200, cy: 292, r: 11, costas: { cx: 117, cy: 314 } },
  { regiao: 'joelho', lado: 'direito', cx: 129, cy: 438, r: 10, costas: { cx: 190, cy: 454 } },
  { regiao: 'joelho', lado: 'esquerdo', cx: 190, cy: 438, r: 10, costas: { cx: 130, cy: 454 } },
  { regiao: 'tornozelo_pe', lado: 'direito', cx: 133, cy: 568, r: 8, costas: { cx: 185, cy: 596 } },
  { regiao: 'tornozelo_pe', lado: 'esquerdo', cx: 187, cy: 568, r: 8, costas: { cx: 136, cy: 596 } },
]



export interface Marca {
  regiao: string
  niveis: string[]
  niveis_historicos?: string[]
  lado: string
  origem: string
  data?: string | null
  trecho?: string
  termos?: string[]
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
  // Estado atual: em cada regiao da coluna, so o laudo mais recente dela.
  const daColuna = marcas.filter((m) => REGIOES_COLUNA.includes(m.regiao))
  const niveis = [...maisRecentesPorRegiao(daColuna)].flatMap(([regiao, doExame]) =>
    doExame.flatMap((m) => m.niveis.filter((n) => regiaoDoNivel(n) === regiao).map((n) => ({ n, origem: m.origem, historico: (m.niveis_historicos ?? []).includes(n) }))),
  )
  const patologias = marcasDosAchados(daColuna)
  const faixas = faixasArtrodese(patologias)
  const rotulos = rotulosDaColuna(niveis, patologias, faixas)
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

      {/* patologias do laudo desenhadas na coluna (nivel e lado do texto) */}
      <GlifosColuna patologias={patologias} faixas={faixas} orientacao={orientacao} />

      {ARTICULACOES.map((a) => {
        const ativo = selecionado === a.regiao
        const comAchado = regioesComAchado.has(a.regiao) && ladosComAchado(a.regiao).has(a.lado)
        const rotulo = `${a.regiao.replace('_', ' e ')} ${a.lado}`
        return (
          <circle
            key={`${a.regiao}-${a.lado}`}
            cx={orientacao === 'costas' ? a.costas.cx : a.cx}
            cy={orientacao === 'costas' ? a.costas.cy : a.cy}
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
      {ARTICULACOES.map((a) => {
        const termos = termosDaArticulacao(marcas, a.regiao, a.lado)
        if (!termos.length) return null
        const cx = orientacao === 'costas' ? a.costas.cx : a.cx
        const cy = orientacao === 'costas' ? a.costas.cy : a.cy
        // Abaixo do circulo: ao lado, colidiria com as etiquetas da coluna (ombros).
        return (
          <text key={`t-${a.regiao}-${a.lado}`} x={cx} y={cy + a.r + 8} textAnchor="middle"
            fontSize={7.5} fontWeight={700} fill={ALERTA} stroke="#fff" strokeWidth={2.2} paintOrder="stroke" pointerEvents="none">
            {termos.map((t) => TERMO_CURTO[t] ?? t).join(', ')}
          </text>
        )
      })}
      {/* por ultimo: etiquetas por cima dos circulos dos ombros; etiquetas dos niveis citados, empilhadas para nao se sobreporem */}
      {rotulos.map((r) => (
        <g key={r.chave} pointerEvents="none" opacity={r.historico ? 0.7 : 1}>
          <polyline points={`176,${r.y} 196,${r.y} 204,${r.yRotulo}`} fill="none" stroke={r.cor} strokeWidth={1.1} strokeDasharray={r.historico ? '2 2' : undefined} />
          <circle cx={160} cy={r.y} r={r.manual ? 4.2 : 3.6} fill={r.cor} stroke="#fff" strokeWidth={1.2} />
          <text x={207} y={r.yRotulo + 3.5} fontSize={9.5} fontWeight={700} fill={r.historico ? '#5b7178' : '#17313a'} stroke="#fff" strokeWidth={2.4} paintOrder="stroke">
            {r.nivel}
            {r.extra && <tspan fontWeight={600} fontSize={8} fill={r.cor}>{` ${r.extra}`}</tspan>}
            {r.historico && <tspan fontWeight={400} fontSize={8}> (ant.)</tspan>}
          </text>
        </g>
      ))}

    </svg>
  )
}

const REGIOES_COLUNA = ['cervical', 'toracica', 'lombar', 'sacral']

// Nomes curtos dos termos (achados.py) para as etiquetas das articulacoes.
const TERMO_CURTO: Record<string, string> = {
  lesao: 'lesão', inflamatorio: 'inflamação', fratura: 'fratura', degenerativo: 'artrose', artrodese: 'fixação',
  estenose: 'estenose', cisto: 'cisto', radicular: 'raiz', hernia: 'hérnia', protrusao: 'protrusão',
}

/** Termos do laudo MAIS RECENTE de uma articulacao, do lado dela
 * ("bilateral"/sem lado vale para os dois): o que melhorou nao fica escrito. */
function termosDaArticulacao(marcas: Marca[], regiao: string, lado: string): string[] {
  const doLado = marcas.filter((m) => m.regiao === regiao && (!m.lado || m.lado === 'bilateral' || m.lado === lado))
  const ultima = doLado.reduce((d, m) => ((m.data ?? '') > d ? (m.data ?? '') : d), '')
  const out: string[] = []
  for (const m of doLado) {
    if ((m.data ?? '') !== ultima) continue
    for (const t of m.termos ?? []) if (!out.includes(t)) out.push(t)
  }
  return out.slice(0, 2)
}

/** y de um nivel na figura: disco ("C6-C7") ou vertebra ("T12"); S1 = topo do sacro. */
function yColuna(nivel: string): number | null {
  if (nivel === 'S1') return TOPO_SACRO + 7
  return yDoNivel(nivel)
}
const larguraVertebra = (v: string) => VERTEBRAS.find((x) => x.nome === v)?.w ?? 28

interface Rotulo { chave: string; nivel: string; y: number; yRotulo: number; cor: string; extra: string; historico: boolean; manual: boolean }

/** Uma etiqueta por nivel citado (ou com patologia); faixas de artrodese viram
 * uma etiqueta so. Empilhadas com espaco minimo para nao se sobreporem. */
function rotulosDaColuna(niveis: { n: string; origem: string; historico: boolean }[], patologias: MarcaPatologia[], faixas: string[][]): Rotulo[] {
  const emFaixa = new Set(faixas.flat())
  const porNivel = new Map<string, Rotulo>()
  const principal = (n: string) => {
    const ps = patologias.filter((p) => p.nivel === n && p.tipo !== 'artrodese')
    return GRAVIDADE.map((t) => ps.find((p) => p.tipo === t)).find(Boolean)
  }
  const nivelAdd = (n: string, origem: string, historico: boolean) => {
    const y = yColuna(n)
    if (y == null) return
    const p = principal(n)
    if (!p && emFaixa.has(n)) return // so artrodese: fica na etiqueta da faixa
    const atual = porNivel.get(n)
    const cor = historico ? '#9aa7ab' : p ? COR_PATOLOGIA[p.tipo] : origem === 'manual' ? SELECAO : ALERTA
    const extra = p ? [CURTO_PATOLOGIA[p.tipo], ABREV_LADO[p.lado]].filter(Boolean).join(' ') : ''
    if (!atual || (atual.historico && !historico)) {
      porNivel.set(n, { chave: n, nivel: n, y, yRotulo: y, cor, extra, historico, manual: origem === 'manual' })
    }
  }
  niveis.forEach(({ n, origem, historico }) => nivelAdd(n, origem, historico))
  patologias.filter((p) => p.tipo !== 'artrodese').forEach((p) => nivelAdd(p.nivel, 'laudo', p.historico))
  const rotulos = [...porNivel.values()]
  for (const f of faixas) {
    const vs = vertebrasDaFaixa(f)
    const y = yColuna(f[0])
    if (y == null) continue
    rotulos.push({ chave: `art-${f.join()}`, nivel: `${vs[0]}–${vs[vs.length - 1]}`, y, yRotulo: y, cor: COR_PATOLOGIA.artrodese, extra: 'artrodese', historico: false, manual: false })
  }
  rotulos.sort((a, b) => a.y - b.y)
  let ultimo = -Infinity
  for (const r of rotulos) {
    r.yRotulo = Math.max(r.y, ultimo + 10.5)
    ultimo = r.yRotulo
  }
  return rotulos
}

/** Desenho de cada patologia sobre a coluna. De FRENTE o lado esquerdo da
 * pessoa fica a direita da tela; de COSTAS, a esquerda. */
function GlifosColuna({ patologias, faixas, orientacao }: { patologias: MarcaPatologia[]; faixas: string[][]; orientacao: Orientacao }) {
  const sinal = (lado: string) => (lado === 'esquerdo' ? 1 : -1) * (orientacao === 'costas' ? -1 : 1)
  const lados = (lado: string) => (lado === 'bilateral' ? ['esquerdo', 'direito'] : lado === 'central' ? [] : [lado])
  return (
    <g pointerEvents="none">
      {faixas.map((f) => {
        const vs = vertebrasDaFaixa(f)
        const ys = vs.map((v) => yColuna(v)).filter((y): y is number => y != null)
        if (ys.length < 2) return null
        const meia = Math.max(...vs.map(larguraVertebra)) / 2 + 2.5
        return (
          <g key={f.join()} opacity={0.95}>
            {[-1, 1].map((sn) => (
              <g key={sn}>
                <line x1={160 + sn * meia} x2={160 + sn * meia} y1={ys[0]} y2={ys[ys.length - 1]} stroke={COR_PATOLOGIA.artrodese} strokeWidth={2.2} strokeLinecap="round" />
                {ys.map((y, i) => (
                  <g key={i}>
                    <line x1={160 + sn * (meia - 5)} x2={160 + sn * meia} y1={y} y2={y} stroke={COR_PATOLOGIA.artrodese} strokeWidth={1.4} />
                    <circle cx={160 + sn * meia} cy={y} r={2.1} fill="#ced4da" stroke={COR_PATOLOGIA.artrodese} strokeWidth={1} />
                  </g>
                ))}
              </g>
            ))}
          </g>
        )
      })}
      {patologias.map((p, i) => {
        if (p.tipo === 'artrodese') return null
        const y = yColuna(p.nivel)
        if (y == null) return null
        const cor = COR_PATOLOGIA[p.tipo]
        const op = p.historico ? 0.45 : 1
        const w = larguraVertebra(p.nivel.split('-')[0])
        if (p.tipo === 'fratura') {
          return (
            <g key={i} opacity={op}>
              <path d={`M${160 - w / 2 + 2},${y - 2.5} l4,4 l4,-4 l4,4 l4,-4`} transform={`translate(${w / 2 - 10},0)`} fill="none" stroke={cor} strokeWidth={1.6} />
            </g>
          )
        }
        if (p.tipo === 'estenose' || p.tipo === 'listese') {
          return <ellipse key={i} cx={160} cy={y} rx={w / 2 + 2} ry={3.2} fill="none" stroke={cor} strokeWidth={1.4} opacity={op} />
        }
        if (p.tipo === 'degenerativo') return null // o ponto do nivel ja tem a cor
        const [rx, ry] = p.tipo === 'hernia' ? [4.5, 2.6] : [3.5, 2]
        const xs = lados(p.lado)
        if (!xs.length) return <ellipse key={i} cx={160} cy={y + 2.5} rx={rx} ry={ry} fill={cor} stroke="#fff" strokeWidth={0.8} opacity={op} />
        return (
          <g key={i} opacity={op}>
            {xs.map((l) => (
              <ellipse key={l} cx={160 + sinal(l) * (w / 2 + rx - 1)} cy={y} rx={rx} ry={ry} fill={cor} stroke="#fff" strokeWidth={0.8} />
            ))}
          </g>
        )
      })}
    </g>
  )
}
