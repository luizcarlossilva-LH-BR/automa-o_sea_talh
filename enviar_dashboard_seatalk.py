"""
Captura screenshot do Dashboard de Performance e envia para SeaTalk
Execute: python enviar_dashboard_seatalk.py

IMPORTANTE: O dashboard deve estar acessivel pela URL configurada!
"""

import asyncio
import os
import base64
import requests
from playwright.async_api import async_playwright

# ============================================
# CONFIGURACOES
# ============================================

# URL do dashboard Streamlit (Streamlit Cloud)
STREAMLIT_URL = os.getenv(
    "STREAMLIT_URL",
    "https://automa-oseatalh-cmvruckvldublahzfafxzz.streamlit.app/Resumo_Geral"
)

# URL do webhook do SeaTalk (obrigatorio via env/secrets)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Tempo de espera para o dashboard carregar (segundos)
WAIT_TIME = int(os.getenv("WAIT_TIME", "8"))

# Intervalo entre envios (segundos). Default: 1 hora
SEND_INTERVAL = int(os.getenv("SEND_INTERVAL", "3600"))

# Se True, executa apenas uma vez e encerra
RUN_ONCE = os.getenv("RUN_ONCE", "false").lower() == "true"

# Modo headless (True = nao mostra navegador)
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

# Viewport para capturar tela inteira (1920x2000)
VIEWPORT_WIDTH = 2500
VIEWPORT_HEIGHT = 2000


# ============================================
# FUNCOES
# ============================================

async def capture_single_page(
    streamlit_url: str,
    wait_time: int = 8,
    headless: bool = True
) -> bytes:
    """
    Captura screenshot da pagina do dashboard

    Args:
        streamlit_url: URL do dashboard Streamlit
        wait_time: Tempo de espera para carregar (segundos)
        headless: Se True, executa sem abrir janela

    Returns:
        bytes: screenshot_bytes
    """
    async with async_playwright() as p:
        print("🌐 Iniciando navegador...")

        browser = await p.chromium.launch(headless=headless)

        # Viewport grande para capturar dashboard completo em uma tela
        context = await browser.new_context(
            viewport={'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT},
            device_scale_factor=2
        )
        page = await context.new_page()

        try:
            print(f"📊 Acessando dashboard: {streamlit_url}")
            await page.goto(streamlit_url, wait_until='networkidle', timeout=60000)

            print(f"⏳ Aguardando {wait_time}s para dashboard carregar...")
            await asyncio.sleep(wait_time)

            # Aguarda elementos do Streamlit
            try:
                await page.wait_for_selector('[data-testid=\"stAppViewContainer\"]', timeout=10000)
                print("✅ Dashboard carregado!")
            except:
                print("⚠️ Elementos do Streamlit nao detectados, continuando...")

            # Scroll para o topo
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)

            print("📸 Capturando screenshot da pagina...")
            screenshot = await page.screenshot(
                full_page=True,
                type='png',
                timeout=30000
            )
            print(f"✅ Screenshot capturado! Tamanho: {len(screenshot)} bytes")

            # Salva screenshot
            with open("dashboard_resumo_geral.png", 'wb') as f:
                f.write(screenshot)
            print("💾 Salvo: dashboard_resumo_geral.png")

            return screenshot

        finally:
            await browser.close()
            print()
            print("🔒 Navegador fechado")


def send_to_seatalk(image_data: bytes, webhook_url: str, description: str = "") -> dict:
    """
    Envia imagem para o SeaTalk

    Args:
        image_data: Dados binarios da imagem
        webhook_url: URL do webhook do SeaTalk
        description: Descricao para log

    Returns:
        dict: Resultado da operacao
    """
    # Codifica em base64
    image_base64 = base64.b64encode(image_data).decode('utf-8')

    # Prepara payload
    payload = {
        "tag": "image",
        "image_base64": {
            "content": image_base64
        }
    }

    headers = {
        'Content-Type': 'application/json'
    }

    print(f"📤 Enviando {description}...")

    try:
        response = requests.post(
            webhook_url,
            headers=headers,
            json=payload,
            timeout=60
        )

        response.raise_for_status()
        result = response.json() if response.content else response.text

        if isinstance(result, dict) and result.get('code') == 0:
            print(f"✅ {description} enviada com sucesso!")
            print(f"📨 Message ID: {result.get('message_id', 'N/A')}")
            return {
                'success': True,
                'message_id': result.get('message_id'),
                'response': result
            }
        else:
            print(f"⚠️ Resposta: {result}")
            return {
                'success': False,
                'error': f"Resposta inesperada: {result}",
                'response': result
            }

    except requests.exceptions.RequestException as e:
        error_msg = str(e)
        print(f"❌ Erro ao enviar: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }


async def run_once():
    """Executa uma rodada de captura e envio"""
    print("=" * 70)
    print("🚀 Dashboard Performance 3PL → SeaTalk (Resumo Geral)")
    print("=" * 70)
    print(f"📊 Dashboard URL: {STREAMLIT_URL}")
    print(f"⏱️  Tempo de espera: {WAIT_TIME}s")
    print(f"⏲️  Intervalo de envio: {SEND_INTERVAL}s")
    print(f"🧩 Modo uma vez: {RUN_ONCE}")
    print(f"👁️  Headless: {HEADLESS}")
    print(f"📐 Viewport: {VIEWPORT_WIDTH}x{VIEWPORT_HEIGHT}")
    print("=" * 70)
    print()

    if not WEBHOOK_URL:
        print("❌ WEBHOOK_URL nao configurado. Defina a variavel de ambiente.")
        return

    # Verifica se o Streamlit esta acessivel
    try:
        response = requests.get(STREAMLIT_URL, timeout=10)
        if response.status_code == 200:
            print("✅ Dashboard Streamlit esta acessivel!")
        else:
            print(f"⚠️ Dashboard retornou status {response.status_code}")
            return
    except requests.exceptions.RequestException as e:
        print(f"❌ ERRO: Dashboard nao esta acessivel em {STREAMLIT_URL}")
        print(f"   Erro: {str(e)}")
        print()
        print("   💡 Verifique se a URL esta correta e acessivel")
        print()
        return

    print()

    # Captura screenshot da pagina
    try:
        screenshot = await capture_single_page(
            streamlit_url=STREAMLIT_URL,
            wait_time=WAIT_TIME,
            headless=HEADLESS
        )

        if screenshot:
            print()
            print("=" * 70)
            print("📤 ENVIANDO PARA SEATALK")
            print("=" * 70)

            result = send_to_seatalk(
                image_data=screenshot,
                webhook_url=WEBHOOK_URL,
                description="Resumo Geral"
            )

            # Resumo final
            print()
            print("=" * 70)
            print("📊 RESUMO DO ENVIO")
            print("=" * 70)

            success_count = 1 if result.get('success') else 0

            print(f"✅ Enviados com sucesso: {success_count}/1")
            print()
            print("📸 Screenshot salvo:")
            print("   - dashboard_resumo_geral.png")

            if success_count == 1:
                print()
                print("🎉 Tela enviada com sucesso!")
            else:
                print()
                print("❌ Nenhuma tela foi enviada. Verifique o webhook.")

            print("=" * 70)
        else:
            print("❌ Nao foi possivel capturar o screenshot")

    except Exception as e:
        print(f"❌ Erro durante execucao: {str(e)}")
        import traceback
        traceback.print_exc()


async def run_scheduler():
    """Executa o envio em loop no intervalo configurado"""
    while True:
        await run_once()
        if RUN_ONCE:
            break
        print()
        print(f"🕒 Aguardando {SEND_INTERVAL}s para o proximo envio...")
        await asyncio.sleep(SEND_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_scheduler())