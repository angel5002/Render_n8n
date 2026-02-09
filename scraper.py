#!/usr/bin/env python3
"""
Scraper de Falabella para n8n
Extrae productos y envía a webhook
"""

import requests
from playwright.sync_api import sync_playwright
import json
from datetime import datetime
import os
import sys

# Configuración
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://api.n8nangelvargas.me/webhook-test/7b44142f-5ae5-4ce8-80ea-e241bd466ad9')
FALABELLA_URL = "https://www.falabella.com.pe/falabella-pe/collection/ver-todo-zapatillas-y-zapatos-hombre?sortBy=derived.price.search%2Casc"

def log(message):
    """Logger simple con timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")

def scrape_falabella():
    """
    Scrape productos de Falabella usando Playwright
    Returns: Lista de productos
    """
    log("🚀 Iniciando navegador...")
    
    try:
        with sync_playwright() as p:
            # Configurar navegador
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
            
            # Configurar contexto con headers realistas
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-PE'
            )
            
            page = context.new_page()
            
            log(f"📡 Navegando a: {FALABELLA_URL}")
            
            # Navegar a la página
            page.goto(FALABELLA_URL, wait_until='networkidle', timeout=60000)
            
            # Esperar que carguen productos (ajusta el selector según Falabella)
            log("⏳ Esperando productos...")
            page.wait_for_selector('.product-item, .search-results-item, .product-card', timeout=30000)
            
            # Scroll para cargar lazy-loading
            log("📜 Haciendo scroll...")
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(2000)
            
            # Extraer datos
            log("🔍 Extrayendo datos...")
            products = page.evaluate('''() => {
                const items = [];
                
                // Intentar múltiples selectores comunes
                const selectors = [
                    '.product-item',
                    '.search-results-item', 
                    '.product-card',
                    '[data-testid="product-card"]'
                ];
                
                let productElements = [];
                for (const selector of selectors) {
                    productElements = document.querySelectorAll(selector);
                    if (productElements.length > 0) break;
                }
                
                productElements.forEach((card, index) => {
                    try {
                        // Extraer datos (ajusta selectores según estructura real)
                        const nameEl = card.querySelector('.product-name, .search-results-4-grid__information__name, h3, .title');
                        const priceEl = card.querySelector('.price, .search-results-4-grid__pod-price, .price-value, [data-price]');
                        const originalPriceEl = card.querySelector('.original-price, .list-price, .price-old');
                        const discountEl = card.querySelector('.discount, .discount-percentage, .badge-discount');
                        const imageEl = card.querySelector('img');
                        const linkEl = card.querySelector('a');
                        const ratingEl = card.querySelector('.rating, .stars, .review-rating');
                        
                        items.push({
                            id: index + 1,
                            name: nameEl?.textContent?.trim() || 'N/A',
                            price: priceEl?.textContent?.trim() || 'N/A',
                            originalPrice: originalPriceEl?.textContent?.trim() || null,
                            discount: discountEl?.textContent?.trim() || null,
                            image: imageEl?.src || imageEl?.getAttribute('data-src') || null,
                            link: linkEl?.href || null,
                            rating: ratingEl?.textContent?.trim() || null
                        });
                    } catch (err) {
                        console.error('Error extrayendo producto:', err);
                    }
                });
                
                return items;
            }''')
            
            browser.close()
            log(f"✅ Extraídos {len(products)} productos")
            return products
            
    except Exception as e:
        log(f"❌ Error en scraping: {str(e)}")
        raise

def send_to_n8n(products):
    """
    Envía datos a n8n vía webhook
    Args: products (list): Lista de productos
    Returns: bool: True si exitoso
    """
    
    payload = {
        "timestamp": datetime.now().isoformat(),
        "source": "falabella",
        "category": "zapatillas-zapatos-hombre",
        "total_products": len(products),
        "products": products,
        "metadata": {
            "scraper_version": "1.0",
            "execution_time": datetime.now().isoformat()
        }
    }
    
    log(f"📤 Enviando {len(products)} productos a n8n...")
    
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Falabella-Scraper/1.0'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            log(f"✅ Datos enviados correctamente a n8n")
            return True
        else:
            log(f"❌ Error HTTP {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        log(f"❌ Timeout al enviar a n8n")
        return False
    except Exception as e:
        log(f"❌ Error enviando a n8n: {str(e)}")
        return False

def main():
    """Función principal"""
    log("=" * 50)
    log("🎯 SCRAPER FALABELLA → N8N")
    log("=" * 50)
    
    try:
        # 1. Scraping
        products = scrape_falabella()
        
        if not products:
            log("⚠️ No se encontraron productos")
            sys.exit(1)
        
        # 2. Enviar a n8n
        success = send_to_n8n(products)
        
        if success:
            log("=" * 50)
            log("✅ PROCESO COMPLETADO EXITOSAMENTE")
            log("=" * 50)
            sys.exit(0)
        else:
            log("❌ Error al enviar datos")
            sys.exit(1)
            
    except Exception as e:
        log(f"💥 Error fatal: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
