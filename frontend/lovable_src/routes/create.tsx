import { createFileRoute } from '@tanstack/react-router';
import { CreateAuction } from '@/features/auctions/create';
export const Route=createFileRoute('/create')({head:()=>({meta:[{title:'Anunciar item | Katchau Leilões'},{name:'description',content:'Publique seu item e crie um novo leilão no Katchau.'},{property:'og:title',content:'Anunciar item | Katchau Leilões'},{property:'og:description',content:'Um novo item. Uma nova disputa.'},{property:'og:type',content:'website'},{name:'twitter:card',content:'summary_large_image'}]}),component:CreateAuction});
