import type { Classificacao, StatusDoc } from '../api'

const CLASSES: Record<Classificacao, { rotulo: string; estilo: string; seta?: string }> = {
  acima: { rotulo: 'Acima', estilo: 'bg-alto-soft text-alto', seta: '↑' },
  abaixo: { rotulo: 'Abaixo', estilo: 'bg-baixo-soft text-baixo', seta: '↓' },
  dentro: { rotulo: 'Dentro', estilo: 'bg-ok-soft text-ok' },
  'nao determinado': { rotulo: 'Sem referência', estilo: 'bg-canvas text-muted' },
}

export function BadgeClassificacao({ valor }: { valor: Classificacao }) {
  const c = CLASSES[valor] ?? CLASSES['nao determinado']
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${c.estilo}`}>
      {c.seta && <span aria-hidden>{c.seta}</span>}
      {c.rotulo}
    </span>
  )
}

const STATUS: Record<StatusDoc, { rotulo: string; estilo: string }> = {
  atencao: { rotulo: 'Atenção', estilo: 'bg-alto-soft text-alto' },
  normal: { rotulo: 'Dentro das referências', estilo: 'bg-ok-soft text-ok' },
  sem_valores: { rotulo: 'Sem valores extraídos', estilo: 'bg-canvas text-muted' },
  achados: { rotulo: 'Com achados', estilo: 'bg-teal-soft text-teal-deep' },
}

export function BadgeStatus({ valor, fora }: { valor: StatusDoc; fora?: number }) {
  const s = STATUS[valor]
  const rotulo = valor === 'atencao' && fora ? `${fora} fora da referência` : s.rotulo
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${s.estilo}`}>{rotulo}</span>
}

export const COR_SISTEMA: Record<string, string> = {
  tireoide: 'bg-[#e1f0ee] text-[#2d6f6a]',
  coracao: 'bg-[#f8e3df] text-[#a44c40]',
  figado: 'bg-[#f3e4dd] text-[#8a4b38]',
  pancreas: 'bg-[#f8eedb] text-[#8c6420]',
  rins: 'bg-[#f3e2dc] text-[#8f5140]',
  sangue: 'bg-[#f6dfe1] text-[#9b3743]',
  inflamacao: 'bg-[#f2e6f3] text-[#7b4a82]',
  vitaminas: 'bg-[#e9ecd9] text-[#5c6a25]',
  hormonios: 'bg-[#e4e6f6] text-[#43519a]',
  prostata: 'bg-[#e6eef6] text-[#35607f]',
  proteinas: 'bg-[#efe9df] text-[#6b5a3c]',
  outros: 'bg-canvas text-muted',
}

export function TagSistema({ id, nome }: { id: string; nome: string }) {
  return <span className={`rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap ${COR_SISTEMA[id] ?? COR_SISTEMA.outros}`}>{nome}</span>
}
