import { useApi, type Resumo } from './api'
import { href, useRota, type Pagina } from './rota'
import { VisaoGeral } from './pages/VisaoGeral'
import { Evolucao } from './pages/Evolucao'
import { AnatomiaPage } from './pages/AnatomiaPage'
import { Documentos } from './pages/Documentos'
import { Imagens } from './pages/Imagens'
import { ImprimirImagens } from './pages/ImprimirImagens'

const NAV: { id: Pagina; rotulo: string; icone: string }[] = [
  { id: 'visao-geral', rotulo: 'Visão geral', icone: 'M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z' },
  { id: 'evolucao', rotulo: 'Evolução', icone: 'M3 17l5-5 4 4 8-9M15 7h5v5' },
  { id: 'anatomia', rotulo: 'Anatomia', icone: 'M12 4a2.2 2.2 0 1 0 0 .01M8 21l1.5-8L6 9.5 8 7h8l2 2.5-3.5 3.5L16 21' },
  { id: 'imagens', rotulo: 'Imagens', icone: 'M4 5h16v14H4zM4 15l4-4 4 4 3-3 5 5M15.5 8.5h.01' },
  { id: 'documentos', rotulo: 'Documentos', icone: 'M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h6' },
]

function Icone({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  )
}

function Marca() {
  return (
    <a href={href('visao-geral')} className="flex items-center gap-2.5 text-lg font-bold tracking-tight text-ink">
      <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden>
        <rect width="32" height="32" rx="9" fill="#2b7a78" />
        <path d="M6 17h5l2.5-6 4 11 2.5-5H26" fill="none" stroke="#fff" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      Minha Saúde
    </a>
  )
}

export default function App() {
  const rota = useRota()
  const resumo = useApi<Resumo>('/api/resumo')

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr] print:!block print:!bg-none lg:bg-[linear-gradient(to_right,#fff_247px,#dce5e6_247px,#dce5e6_248px,transparent_248px)]">
      {/* Barra lateral (desktop) */}
      <aside className="sticky top-0 hidden h-screen print:!hidden flex-col bg-white px-4 py-6 lg:flex">
        <div className="px-2"><Marca /></div>
        <nav className="mt-8 flex flex-col gap-1" aria-label="Seções">
          {NAV.map((n) => {
            const ativo = rota.pagina === n.id
            return (
              <a key={n.id} href={href(n.id)} aria-current={ativo ? 'page' : undefined}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors ${ativo ? 'bg-teal-soft text-teal-deep' : 'text-muted hover:bg-canvas hover:text-ink'}`}>
                <Icone d={n.icone} />
                {n.rotulo}
              </a>
            )
          })}
        </nav>
        <div className="mt-auto rounded-2xl bg-teal-deep p-4 text-sm leading-relaxed text-teal-soft">
          <p className="font-semibold text-white">Para conferência</p>
          <p className="mt-1">Valores e achados são extraídos automaticamente dos laudos. Confirme sempre no documento original.</p>
        </div>
      </aside>

      {/* Topo (celular e tablet) */}
      <header className="sticky top-0 z-20 print:hidden border-b border-line bg-white/95 backdrop-blur lg:hidden">
        <div className="px-4 pt-3"><Marca /></div>
        <nav className="flex gap-1 overflow-x-auto px-3 py-2" aria-label="Seções">
          {NAV.map((n) => {
            const ativo = rota.pagina === n.id
            return (
              <a key={n.id} href={href(n.id)} aria-current={ativo ? 'page' : undefined}
                className={`flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-medium ${ativo ? 'bg-teal text-white' : 'text-muted'}`}>
                {n.rotulo}
              </a>
            )
          })}
        </nav>
      </header>

      <main className="min-w-0">
        {rota.pagina === 'visao-geral' && <VisaoGeral resumo={resumo} />}
        {rota.pagina === 'evolucao' && <Evolucao marcadorInicial={rota.params.get('m')} />}
        {rota.pagina === 'anatomia' && <AnatomiaPage vistaInicial={rota.params.get('vista')} regiaoInicial={rota.params.get('r')} />}
        {rota.pagina === 'imagens' && <Imagens />}
        {rota.pagina === 'imprimir' && <ImprimirImagens estudo={rota.params.get('estudo')} />}
        {rota.pagina === 'documentos' && <Documentos />}
      </main>
    </div>
  )
}
