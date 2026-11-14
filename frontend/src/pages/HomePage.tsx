import { useEffect, useState } from 'react'
import { api } from '../api/api'
import { Button, Icon, Notice } from '../components/common/Ui'
import { LeilaoCard } from '../components/home/LeilaoCard'
import { ALL_CATEGORY_LABELS, categoryLabel } from '../utils/auctionRules'
import type { Auction, AuctionPage } from '../utils/interfaces/auctionInterface'

const PAGE_SIZE = 12
const SERVER_MAX_PAGE_SIZE = 48

export function HomePage() {
  const [tab, setTab] = useState<'running' | 'scheduled' | 'running,scheduled'>(
    'running',
  )
  const [page, setPage] = useState(1)
  const [data, setData] = useState<AuctionPage | null>(null)
  const [allForFilter, setAllForFilter] = useState<Auction[] | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('Todas as categorias')
  const [view, setView] = useState<'grid' | 'list'>('grid')

  const isFiltering =
    category !== 'Todas as categorias' || search.trim() !== ''

  useEffect(() => {
    let active = true

    const load = async () => {
      try {
        if (!isFiltering) {
          const response = await api.listAuctions({
            status: tab,
            page,
            page_size: PAGE_SIZE,
          })
          if (active) {
            setData(response)
            setAllForFilter(null)
            setError('')
          }
        } else {
          // Quando há filtro de categoria ou busca ativo, busca todos os lotes
          // do status atual (usando o lote máximo de 48 do servidor) para juntar
          // os resultados nas páginas sem buracos e remover páginas vazias.
          const firstPage = await api.listAuctions({
            status: tab,
            page: 1,
            page_size: SERVER_MAX_PAGE_SIZE,
          })
          let combined = [...firstPage.results]
          const totalPages = Math.ceil(
            firstPage.total / SERVER_MAX_PAGE_SIZE,
          )
          if (totalPages > 1) {
            const restPromises: Promise<AuctionPage>[] = []
            for (let p = 2; p <= totalPages; p++) {
              restPromises.push(
                api.listAuctions({
                  status: tab,
                  page: p,
                  page_size: SERVER_MAX_PAGE_SIZE,
                }),
              )
            }
            const restPages = await Promise.all(restPromises)
            for (const rp of restPages) {
              combined = combined.concat(rp.results)
            }
          }
          if (active) {
            setData(firstPage)
            setAllForFilter(combined)
            setError('')
          }
        }
      } catch (e) {
        if (active) {
          // Sem dados de reserva: a lista só mostra o que veio da API.
          setData(null)
          setAllForFilter(null)
          setError(
            (e as Error).message || 'Não foi possível carregar os leilões.',
          )
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    const timer = setInterval(load, 30000)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [tab, page, isFiltering, reload])

  const retry = () => {
    setLoading(true)
    setError('')
    setReload((n) => n + 1)
  }

  const changeTab = (nextTab: 'running' | 'scheduled' | 'running,scheduled') => {
    if (nextTab === tab && page === 1) return
    setLoading(true)
    setTab(nextTab)
    setPage(1)
  }

  const changePage = (nextPage: number) => {
    if (nextPage === page) return
    if (!isFiltering) {
      setLoading(true)
    }
    setPage(nextPage)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handleSearchChange = (value: string) => {
    setSearch(value)
    setPage(1)
  }

  const handleCategoryChange = (value: string) => {
    setCategory(value)
    setPage(1)
  }

  // Se estiver filtrando, filtra sobre todos os leilões da aba e reagrupa em páginas de 12
  const filteredPool = isFiltering
    ? (allForFilter ?? data?.results ?? []).filter(
        (a) =>
          (category === 'Todas as categorias' ||
            categoryLabel(a.category) === category ||
            a.category === category) &&
          a.name.toLowerCase().includes(search.trim().toLowerCase()),
      )
    : (data?.results ?? [])

  const totalCount = isFiltering ? filteredPool.length : (data?.total ?? 0)
  const pages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))
  const safePage = Math.min(page, pages)

  const results = isFiltering
    ? filteredPool.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
    : filteredPool

  const categoryOptions = [
    'Todas as categorias',
    ...new Set([
      ...ALL_CATEGORY_LABELS,
      ...(data?.results || []).map((a) => categoryLabel(a.category)),
    ]),
  ]

  return (
    <main>
      <section className="border-b border-border bg-card">
        <div className="page-width listing-intro py-12">
          <div className="mb-5 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[2px] text-success">
            <span className="live-dot" />O próximo grande achado é seu
          </div>
          <div className="flex flex-col justify-between gap-8 md:flex-row md:items-end">
            <div>
              <h1 className="listing-title text-4xl font-extrabold leading-tight md:text-5xl">
                Grandes oportunidades.
                <br />
                <span className="text-muted-foreground">
                  Lances que fazem a diferença.
                </span>
              </h1>
              <p className="mt-5 max-w-xl text-sm leading-relaxed text-muted-foreground">
                Peças únicas, oportunidades reais. Encontre seu próximo achado
                <br className="hidden md:block" /> e entre na disputa em tempo
                real.
              </p>
            </div>
            <div className="mb-1 hidden items-center gap-3 border-l border-border pl-5 md:flex">
              <span className="flex h-11 w-11 items-center justify-center rounded-full bg-success-soft text-success">
                <Icon name="shield" className="h-6 w-6" />
              </span>
              <div className="text-xs font-bold">
                Seu lance, com confiança.
                <p className="mt-1 text-[11px] font-normal text-muted-foreground">
                  Leilões transparentes. Disputas de verdade.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="page-width pt-9">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="flex items-center gap-2 text-xl font-extrabold">
              <Icon name="hammer" className="text-primary" />
              Explore os leilões
            </h2>
            <p className="mt-2 text-xs text-muted-foreground">
              Encontre algo extraordinário. Dê o seu próximo lance.
            </p>
          </div>
          <span className="hidden items-center gap-2 text-[11px] text-muted-foreground sm:flex">
            <span className="live-dot text-success" />
            Atualização a cada 30s
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-5 border-b border-border">
          <div
            role="tablist"
            aria-label="Status dos leilões"
            className="flex gap-6"
          >
            {(
              [
                ['running', 'Em andamento'],
                ['scheduled', 'Agendados'],
                ['running,scheduled', 'Todos'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                role="tab"
                aria-selected={tab === value}
                className={`tab ${tab === value ? 'active' : ''}`}
                onClick={() => changeTab(value)}
              >
                {value === 'running' && (
                  <span className="live-dot text-success" />
                )}
                {label}
                {tab === value && (
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[10px]">
                    {totalCount}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className="flex gap-1 py-2">
            <Button
              aria-label="Visualização em grade"
              title="Grade"
              variant="ghost"
              className={view === 'grid' ? 'bg-muted' : ''}
              onClick={() => setView('grid')}
            >
              <Icon name="grid" className="h-4 w-4" />
            </Button>
            <Button
              aria-label="Visualização em lista"
              title="Lista"
              variant="ghost"
              className={view === 'list' ? 'bg-muted' : ''}
              onClick={() => setView('list')}
            >
              <Icon name="list" className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="my-5 flex flex-col items-stretch justify-between gap-3 sm:flex-row">
          <label className="relative block sm:w-96">
            <span className="absolute left-3 top-3 text-muted-foreground">
              <Icon name="search" className="h-4 w-4" />
            </span>
            <input
              aria-label="Buscar leilões"
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="O que você está procurando?"
              className="field pl-10 text-xs"
            />
          </label>
          <select
            aria-label="Filtrar por categoria"
            value={category}
            onChange={(e) => handleCategoryChange(e.target.value)}
            className="field text-xs sm:w-52"
          >
            {categoryOptions.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </div>

        {error && (
          <div className="mb-5">
            <Notice>
              <span role="alert">
                Não foi possível carregar os leilões: {error}
              </span>
              <Button variant="outline" className="ml-3" onClick={retry}>
                Tentar de novo
              </Button>
            </Notice>
          </div>
        )}

        <div className="mb-4 text-[11px] text-muted-foreground">
          {loading
            ? 'Buscando leilões…'
            : error
              ? 'Lista indisponível no momento.'
              : `${totalCount} leilões ${tab === 'scheduled' ? 'agendados' : 'disponíveis'}`}
        </div>

        <div
          className={
            view === 'grid'
              ? 'grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4'
              : 'grid grid-cols-1 gap-5 sm:grid-cols-2'
          }
        >
          {results.map((auction, index) => (
            <LeilaoCard
              key={auction.id}
              auction={auction}
              first={index === 0}
            />
          ))}
        </div>
        {!loading && !error && results.length === 0 && (
          <div className="py-20 text-center text-sm text-muted-foreground">
            Nenhum leilão encontrado.
          </div>
        )}

        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6 text-xs text-muted-foreground">
          <span>
            Página {safePage} de {pages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              disabled={safePage <= 1}
              onClick={() => changePage(safePage - 1)}
            >
              Anterior
            </Button>
            {Array.from({ length: pages }, (_, i) => i + 1)
              .filter(
                (p) =>
                  p === 1 || p === pages || Math.abs(p - safePage) <= 2,
              )
              .map((p) => (
                <Button
                  key={p}
                  aria-label={`Página ${p}`}
                  variant={p === safePage ? 'primary' : 'outline'}
                  onClick={() => changePage(p)}
                >
                  {p}
                </Button>
              ))}
            <Button
              variant="outline"
              disabled={safePage >= pages}
              onClick={() => changePage(safePage + 1)}
            >
              Próxima
              <Icon name="chevron" className="h-3 w-3" />
            </Button>
          </div>
        </div>

        <div className="mt-12 grid gap-6 border-y border-border py-7 sm:grid-cols-3">
          {(
            [
              [
                'shield',
                'Transparência em primeiro lugar',
                'Cada lance registrado. Cada disputa às claras.',
              ],
              [
                'bolt',
                'A emoção acontece ao vivo',
                'Acompanhe cada lance, segundo a segundo.',
              ],
              [
                'hammer',
                'Oportunidades que valem a disputa',
                'De colecionáveis a grandes conquistas.',
              ],
            ] as const
          ).map(([icon, title, copy]) => (
            <div key={title} className="flex items-start gap-3">
              <span className="rounded-md bg-warning-soft p-2.5 text-primary">
                <Icon name={icon} />
              </span>
              <div>
                <h3 className="text-xs font-bold">{title}</h3>
                <p className="mt-1.5 text-[11px] text-muted-foreground">
                  {copy}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}
