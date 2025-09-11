# Альтернативная функция take_screenshot для использования с системным Chrome
# Замените функцию take_screenshot в main.py на эту версию, если используете Dockerfile.chrome

async def take_screenshot(url: str) -> BytesIO:
    try:
        logging.info(f"Starting screenshot for URL: {url}")
        
        async with async_playwright() as p:
            # Запускаем системный Chrome с опциями для контейнера
            browser = await p.chromium.launch(
                headless=True,
                executable_path="/usr/bin/google-chrome",
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-images',
                    '--disable-javascript-harmony-promises',
                    '--disable-wake-on-wifi',
                    '--disable-ipc-flooding-protection',
                    '--enable-unsafe-swiftshader',
                    '--single-process',  # Для контейнеров
                    '--disable-software-rasterizer',
                    '--run-all-compositor-stages-before-draw',
                    '--disable-background-mode',
                    '--disable-client-side-phishing-detection',
                    '--disable-crash-reporter',
                    '--disable-default-apps',
                    '--disable-extensions',
                    '--disable-hang-monitor',
                    '--disable-infobars',
                    '--disable-notifications',
                    '--disable-popup-blocking',
                    '--disable-prompt-on-repost',
                    '--disable-sync',
                    '--force-color-profile=srgb',
                    '--metrics-recording-only',
                    '--no-pings',
                    '--password-store=basic',
                    '--use-mock-keychain',
                    '--disable-field-trial-config',
                    '--disable-logging',
                    '--disable-breakpad',
                    '--disable-component-update',
                    '--disable-domain-reliability',
                    '--disable-background-sync',
                    '--disable-shader-cache',
                    '--max_old_space_size=256'
                ]
            )
            
            logging.info("Chrome browser launched successfully")
            
            page = await browser.new_page(
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True,
                ignore_https_errors=True,
                bypass_csp=True
            )
            
            logging.info("Page created successfully")
            
            # Устанавливаем таймауты
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)
            
            # Устанавливаем пользовательский агент
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Загружаем страницу
            try:
                response = await page.goto(
                    url, 
                    wait_until='domcontentloaded',
                    timeout=25000
                )
                
                if response:
                    logging.info(f"Page loaded with status: {response.status}")
                else:
                    logging.warning(f"No response received for {url}")
                    
            except Exception as nav_error:
                logging.warning(f"Navigation warning for {url}: {nav_error}")
            
            # Ждем для рендеринга
            await page.wait_for_timeout(3000)
            
            # Делаем скриншот
            screenshot = await page.screenshot(
                full_page=False,
                type='png',
                timeout=15000,
                animations='disabled',
                caret='hide'
            )
            
            logging.info(f"Screenshot captured successfully for {url}")
            await browser.close()
            return BytesIO(screenshot)
            
    except Exception as e:
        logging.error(f"Error in take_screenshot for {url}: {str(e)}")
        logging.error(f"Error type: {type(e).__name__}")
        
        # Дополнительная отладочная информация
        if hasattr(e, 'args'):
            logging.error(f"Error args: {e.args}")
            
        return None
