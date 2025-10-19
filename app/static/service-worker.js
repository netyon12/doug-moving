// Service Worker para Go Mobi PWA
// Versão 1.0.0

const CACHE_NAME = 'go-mobi-v1.0.0';
const OFFLINE_URL = '/offline';

// Arquivos essenciais para cachear na instalação
const STATIC_CACHE_URLS = [
  '/',
  '/static/css/bootstrap.min.css',
  '/static/css/custom.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/manifest.json',
  '/offline'
];

// Instala o Service Worker e faz cache dos arquivos essenciais
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Instalando...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] Cache aberto, adicionando arquivos...');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => {
        console.log('[Service Worker] Instalação concluída');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('[Service Worker] Erro na instalação:', error);
      })
  );
});

// Ativa o Service Worker e limpa caches antigos
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Ativando...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== CACHE_NAME) {
              console.log('[Service Worker] Removendo cache antigo:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('[Service Worker] Ativação concluída');
        return self.clients.claim();
      })
  );
});

// Intercepta requisições e serve do cache quando possível
self.addEventListener('fetch', (event) => {
  // Ignora requisições que não são GET
  if (event.request.method !== 'GET') {
    return;
  }

  // Ignora requisições de API (deixa passar para o servidor)
  if (event.request.url.includes('/api/')) {
    return;
  }

  event.respondWith(
    caches.match(event.request)
      .then((cachedResponse) => {
        // Se encontrou no cache, retorna
        if (cachedResponse) {
          console.log('[Service Worker] Servindo do cache:', event.request.url);
          return cachedResponse;
        }

        // Se não encontrou, busca na rede
        return fetch(event.request)
          .then((response) => {
            // Verifica se a resposta é válida
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }

            // Clona a resposta para cachear
            const responseToCache = response.clone();

            caches.open(CACHE_NAME)
              .then((cache) => {
                // Cacheia apenas recursos estáticos
                if (event.request.url.includes('/static/') || 
                    event.request.url.endsWith('.css') || 
                    event.request.url.endsWith('.js') ||
                    event.request.url.endsWith('.png') ||
                    event.request.url.endsWith('.jpg') ||
                    event.request.url.endsWith('.svg')) {
                  cache.put(event.request, responseToCache);
                  console.log('[Service Worker] Adicionado ao cache:', event.request.url);
                }
              });

            return response;
          })
          .catch((error) => {
            console.error('[Service Worker] Erro ao buscar:', event.request.url, error);
            
            // Se falhou e é uma navegação, mostra página offline
            if (event.request.mode === 'navigate') {
              return caches.match(OFFLINE_URL);
            }
            
            return new Response('Offline', {
              status: 503,
              statusText: 'Service Unavailable',
              headers: new Headers({
                'Content-Type': 'text/plain'
              })
            });
          });
      })
  );
});

// Escuta mensagens do cliente
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => caches.delete(cacheName))
        );
      })
    );
  }
});

// Notificações Push (opcional - para implementação futura)
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push recebido:', event);
  
  const options = {
    body: event.data ? event.data.text() : 'Nova notificação do Go Mobi',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Ver detalhes'
      },
      {
        action: 'close',
        title: 'Fechar'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification('Go Mobi', options)
  );
});

// Clique em notificação
self.addEventListener('notificationclick', (event) => {
  console.log('[Service Worker] Notificação clicada:', event);
  
  event.notification.close();

  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

