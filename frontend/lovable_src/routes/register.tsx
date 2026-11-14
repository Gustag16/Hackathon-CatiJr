import { createFileRoute } from '@tanstack/react-router';
import { AuthForm } from '@/features/auctions/auth-form';
export const Route=createFileRoute('/register')({head:()=>({meta:[{title:'Criar conta | Katchau Leilões'},{name:'description',content:'Crie sua conta no Katchau Leilões e descubra novas oportunidades.'},{property:'og:title',content:'Criar conta | Katchau Leilões'},{property:'og:description',content:'Sua próxima conquista começa aqui.'},{property:'og:type',content:'website'},{name:'twitter:card',content:'summary_large_image'}]}),component:Register});
function Register(){return <AuthForm register/>;}
