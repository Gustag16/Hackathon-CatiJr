import car from '@/assets/porsche.jpg';
import watch from '@/assets/watch.jpg';
import camera from '@/assets/camera.jpg';
import chair from '@/assets/chair.jpg';
import type { Auction } from './domain';
export function sampleAuctions(): Auction[] { const now = Date.now(); return [
 ['porsche','Porsche 911 Carrera 2018','Veículos',car,38500000,24,'Premium Motors',14230,'running'],
 ['rolex','Rolex Cosmograph Daytona','Relógios',watch,6850000,18,'Tempo & Cia',87,'running'],
 ['sony','Câmera Sony Alpha A7 III + lente','Eletrônicos',camera,780000,12,'Studio Foto',7815,'running'],
 ['eames','Poltrona Eames com puff','Casa & Design',chair,450000,8,'Design Collection',20520,'running'],
 ['porsche-2','Porsche 911 — edição especial','Veículos',car,42000000,0,'Premium Motors',86400,'scheduled'],
 ['watch-2','Cronógrafo clássico em aço','Relógios',watch,3200000,0,'Tempo & Cia',172800,'scheduled']
 ].map(([id,name,category,image,price,bids,seller,seconds,status]) => ({id: String(id),item_id: String(id),name:String(name),category:String(category),cover_photo_url:String(image),current_price_cents:Number(price),start_price_cents:Number(price),min_next_bid_cents:Number(price)+10000,bid_count:Number(bids),seller:{id:'sample-seller',display_name:String(seller),created_at:'2025-01-01T00:00:00Z'},status:status as Auction['status'],starts_at:new Date(now + (status === 'scheduled' ? Number(seconds)*1000 : -3600000)).toISOString(),ends_at:new Date(now+Number(seconds)*1000).toISOString(),description:'Item de demonstração visual. As informações e imagens são ilustrativas; lances reais dependem da conexão com a API Django.',photos:[{id:'1',url:String(image)}],result:null})); }
