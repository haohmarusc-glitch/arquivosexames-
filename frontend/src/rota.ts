import { useEffect, useState } from 'react'

export type Pagina = 'visao-geral' | 'evolucao' | 'anatomia' | 'imagens' | 'documentos'
export interface Rota { pagina: Pagina; params: URLSearchParams }

const PAGINAS: Pagina[] = ['visao-geral', 'evolucao', 'anatomia', 'imagens', 'documentos']

function ler(): Rota {
  const [caminho, busca = ''] = window.location.hash.replace(/^#\/?/, '').split('?')
  const pagina = (PAGINAS as string[]).includes(caminho) ? (caminho as Pagina) : 'visao-geral'
  return { pagina, params: new URLSearchParams(busca) }
}

export function href(pagina: Pagina, params?: Record<string, string>) {
  const q = params ? `?${new URLSearchParams(params)}` : ''
  return `#/${pagina}${q}`
}

export function useRota(): Rota {
  const [rota, setRota] = useState(ler)
  useEffect(() => {
    const atualizar = () => {
      setRota(ler())
      window.scrollTo({ top: 0 })
    }
    window.addEventListener('hashchange', atualizar)
    return () => window.removeEventListener('hashchange', atualizar)
  }, [])
  return rota
}
