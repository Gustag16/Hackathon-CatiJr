import { createFileRoute } from "@tanstack/react-router";
import { Listing } from '@/features/auctions/listing';

// The home route ships no og:image, so serve-time hosting can inject the
// project's social preview (explicit og:image or latest screenshot).
export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: 'Katchau Leilões | O próximo grande achado é seu' },
    { name: 'description', content: 'Explore oportunidades únicas e participe de leilões online em tempo real no Katchau Leilões.' },
    { property: 'og:title', content: 'Katchau Leilões | Leilões em tempo real' },
    { property: 'og:description', content: 'Peças únicas, oportunidades reais. Encontre seu próximo achado.' },
    { property: 'og:type', content: 'website' },
    { name: 'twitter:card', content: 'summary_large_image' },
  ] }),
  component: Listing,
});
