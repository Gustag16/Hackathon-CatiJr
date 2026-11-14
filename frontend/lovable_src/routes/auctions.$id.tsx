import { createFileRoute } from '@tanstack/react-router';
import { AuctionDetail } from '@/features/auctions/detail';
export const Route=createFileRoute('/auctions/$id')({head:({params})=>({meta:[{title:`Leilão ${params.id} | Katchau Leilões`},{name:'description',content:'Confira o item, acompanhe lances e participe da sala de leilão em tempo real.'},{property:'og:title',content:`Leilão ${params.id} | Katchau Leilões`},{property:'og:description',content:'Acompanhe cada lance no Katchau Leilões.'},{property:'og:type',content:'website'},{name:'twitter:card',content:'summary_large_image'}]}),component:Detail});
function Detail(){const {id}=Route.useParams();return <AuctionDetail id={id}/>;}
