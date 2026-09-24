import type { ReactNode } from 'react'

export function Painel({ titulo, acoes, children, className = '' }: { titulo?: ReactNode; acoes?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-line bg-white ${className}`}>
      {(titulo || acoes) && (
        <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-2">
          {titulo && <h2 className="text-base font-semibold">{titulo}</h2>}
          {acoes}
        </header>
      )}
      <div className="px-5 pb-5">{children}</div>
    </section>
  )
}

export function Aviso({ tom = 'neutro', children }: { tom?: 'neutro' | 'erro'; children: ReactNode }) {
  const estilo = tom === 'erro' ? 'border-alto/30 bg-alto-soft text-alto' : 'border-line bg-white text-muted'
  return <div className={`rounded-xl border px-4 py-3 text-sm ${estilo}`}>{children}</div>
}

export function Carregando() {
  return <div className="h-40 animate-pulse rounded-2xl bg-white/70" aria-label="Carregando" />
}
