# explore_macromicro.py
import asyncio, json

async def main():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        page = await context.new_page()
        
        await page.goto(
            "https://en.macromicro.me/series/23955/nasdaq-100-pe",
            wait_until="domcontentloaded", timeout=60000
        )
        await page.wait_for_timeout(20000)
        
        # Try extracting data from Highcharts or any chart library
        result = await page.evaluate("""() => {
            const out = {};
            
            // Check Highcharts
            if (window.Highcharts) {
                out.highcharts = true;
                const charts = Highcharts.charts.filter(c => c);
                out.chartCount = charts.length;
                if (charts.length > 0) {
                    const c = charts[0];
                    out.seriesCount = c.series.length;
                    out.series = c.series.map(s => ({
                        name: s.name,
                        points: s.data.length,
                        firstX: s.data[0]?.x,
                        firstY: s.data[0]?.y,
                        lastX: s.data[s.data.length-1]?.x,
                        lastY: s.data[s.data.length-1]?.y,
                        sampleData: s.data.slice(0, 3).map(d => [d.x, d.y])
                    }));
                }
            }
            
            // Check Chart.js
            if (window.Chart) {
                out.chartjs = true;
            }
            
            // Check for Vue/Nuxt data
            const app = document.querySelector('#__nuxt') || document.querySelector('#app');
            if (app && app.__vue__) {
                out.vue = true;
                try {
                    const data = app.__vue__.$data || app.__vue__._data;
                    out.vueKeys = Object.keys(data || {});
                } catch(e) {}
            }
            
            // Check for any global chart data
            for (const key of ['chartData', 'seriesData', 'pageData', '__NUXT__', '__DATA__']) {
                if (window[key]) {
                    out[key] = typeof window[key];
                }
            }
            
            // Search all script content for data
            const scripts = document.querySelectorAll('script:not([src])');
            out.inlineScripts = scripts.length;
            
            return out;
        }""")
        
        print(json.dumps(result, indent=2, default=str))
        
        # If Highcharts found, extract full data
        if result.get("highcharts") and result.get("chartCount", 0) > 0:
            print("\nExtracting Highcharts data...")
            data = await page.evaluate("""() => {
                const charts = Highcharts.charts.filter(c => c);
                return charts[0].series.map(s => ({
                    name: s.name,
                    data: s.data.map(d => [d.x, d.y])
                }));
            }""")
            for s in data:
                print(f"\n  Series: {s['name']}, points: {len(s['data'])}")
                if s['data']:
                    print(f"  First: {s['data'][0]}")
                    print(f"  Last:  {s['data'][-1]}")
        
        await browser.close()

asyncio.run(main())