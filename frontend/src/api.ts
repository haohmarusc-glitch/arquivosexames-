import { useCallback, useEffect, useState } from 'react'

export type Classificacao = 'acima' | 'abaixo' | 'dentro' | 'nao determinado'
export type StatusDoc = 'atencao' | 'normal' | 'sem_valores' | 'achados'

export interface Resumo {
  titular: string
  total_documentos: number
  total_resultados: number
  total_marcadores: number
  sem_texto: number
  erros: number
  duplicados: number
  nome_divergente: number
  periodo: { inicio: string | null; fim: string | null }
  ultimo_exame: { data: string | null; marcadores: number; arquivos: string[] }
  atencao: { id: string; nome: string; valor: number; unidade: string; classificacao: Classificacao; data: string }[]
}

export interface Documento {
  arquivo: string
  data: string | null
  tipo: string
  paginas: number
  texto_extraido: boolean
  resultados: number
  fora: number
  sistemas: string[]
  regioes: string[]
  aviso: string
  origem?: 'analisador' | 'upload'
  pdf?: boolean
  status: StatusDoc
}

export interface Marcador {
  id: string
  nome: string
  sistema: string
  unidade: string
  medicoes: number
  ultimo_valor: number
  ultima_data: string | null
  classificacao: Classificacao
}

export interface Ponto {
  data: string
  valor: number
  valor_texto: string
  unidade: string
  ref_min: number | null
  ref_max: number | null
  referencia: string
  classificacao: Classificacao
  arquivo: string
  arquivos?: string[]
}

export interface Serie {
  id: string
  nome: string
  sistema: string
  pontos: Ponto[]
}

export interface Sistema {
  id: string
  nome: string
  marcadores: number
  fora: number
}

export interface EstudoImagem {
  id: string
  data: string | null
  descricao: string
  modalidades: string[]
  series: number
  imagens: number
  visualizador: string
  laudos: string[]
}

export interface SerieImagem {
  id: string
  numero: string
  modalidade: string
  descricao: string
  imagens: string[]
}

export interface EstudoSeries {
  id: string
  data: string | null
  descricao: string
  series: SerieImagem[]
}

export interface RespostaImagens {
  habilitado: boolean
  erro?: string
  estudos: EstudoImagem[]
}

export interface Estado<T> {
  dados: T | null
  erro: string | null
  carregando: boolean
  recarregar: () => void
}

export const EVENTO_DADOS = 'dados-atualizados'
export const avisarDadosMudaram = () => window.dispatchEvent(new Event(EVENTO_DADOS))

export interface EnvioSistema { id: string; nome: string; marcadores: string[] }
export interface Envio {
  arquivo: string
  status: 'adicionado' | 'duplicado' | 'erro' | 'info'
  tipo?: string
  data?: string | null
  resultados?: number
  fora?: number
  sistemas?: EnvioSistema[]
  regioes?: string[]
  aviso?: string
  erro?: string
  igual_a?: string
}

export function useApi<T>(caminho: string | null): Estado<T> {
  const [dados, setDados] = useState<T | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(Boolean(caminho))
  const [versao, setVersao] = useState(0)

  useEffect(() => {
    if (!caminho) return
    const ctrl = new AbortController()
    setCarregando(true)
    setErro(null)
    fetch(caminho, { signal: ctrl.signal })
      .then(async (r) => {
        const corpo = await r.json().catch(() => null)
        if (!r.ok) throw new Error(corpo?.detail ?? `A API respondeu ${r.status}.`)
        return corpo as T
      })
      .then(setDados)
      .catch((e: Error) => {
        if (e.name !== 'AbortError') setErro(e.message || 'Não foi possível falar com a API.')
      })
      .finally(() => setCarregando(false))
    return () => ctrl.abort()
  }, [caminho, versao])

  // Um envio de PDF pelo painel dispara "dados-atualizados": todas as telas recarregam.
  useEffect(() => {
    const ouvir = () => setVersao((v) => v + 1)
    window.addEventListener(EVENTO_DADOS, ouvir)
    return () => window.removeEventListener(EVENTO_DADOS, ouvir)
  }, [])

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])
  return { dados, erro, carregando, recarregar }
}

export interface Achado {
  arquivo: string
  data: string | null
  modalidade: string
  regiao: string
  niveis: string[]
  niveis_historicos: string[]
  termos: string[]
  lado: string
  titulo: string
  trecho: string
  origem: 'laudo' | 'manual'
}

export const REGIOES: Record<string, string> = {
  cervical: 'Coluna cervical',
  toracica: 'Coluna torácica',
  lombar: 'Coluna lombar',
  sacral: 'Sacro',
  ombro: 'Ombro',
  cotovelo: 'Cotovelo',
  punho_mao: 'Punho e mão',
  quadril: 'Quadril',
  joelho: 'Joelho',
  tornozelo_pe: 'Tornozelo e pé',
  outros: 'Outras regiões',
}

export const TERMOS: Record<string, string> = {
  hernia: 'Hérnia',
  protrusao: 'Protrusão/abaulamento',
  artrodese: 'Artrodese/fixação',
  estenose: 'Estenose/compressão',
  degenerativo: 'Degenerativo',
  listese: 'Listese',
  radicular: 'Contato radicular',
  fratura: 'Fratura',
  lesao: 'Lesão/tendinopatia',
  inflamatorio: 'Sinais inflamatórios',
}

export const MODALIDADES: Record<string, string> = {
  ressonancia: 'Ressonância',
  tomografia: 'Tomografia',
  radiografia: 'Radiografia',
  ultrassom: 'Ultrassom',
  cirurgia: 'Cirurgia',
  imagem: 'Exame de imagem',
}
