"""
价格分析器模块 - 处理闲鱼比价功能
"""

import time
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from loguru import logger

# 是否使用随机用户代理
DYNAMIC_USERAGENT = True

try:
    from fake_useragent import UserAgent
except ImportError:
    DYNAMIC_USERAGENT = False
    logger.warning("未安装fake_useragent库，将使用默认用户代理")

def get_random_user_agent():
    """获取随机用户代理，包含桌面和移动设备"""
    try:
        ua = UserAgent()
        # 允许使用任何类型的用户代理
        return ua.random
    except Exception as e:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

class PriceAnalyzer:
    """闲鱼价格分析器类"""
    
    def __init__(self, headless=True):
        """
        初始化价格分析器
        
        Args:
            headless: 是否使用无头模式，默认为True
        """
        self.headless = headless
        self.playwright = None
        self.browser_type = None

    def _ensure_playwright_initialized(self):
        """确保 Playwright 实例已初始化"""
        if self.playwright is None:
            self.playwright = sync_playwright().start()
            self.browser_type = self.playwright.chromium

    def initialize_context(self):
        """启动浏览器并创建上下文"""
        self._ensure_playwright_initialized()
        browser = None
        context = None
        try:
            browser_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-gpu",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--start-maximized",
                "--disable-notifications"
            ]
            user_agent = get_random_user_agent() if DYNAMIC_USERAGENT else None
            
            browser = self.browser_type.launch(headless=self.headless, args=browser_args)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=user_agent,
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                permissions=["geolocation"],
                geolocation={"latitude": 39.9042, "longitude": 116.4074}
            )
            logger.info("浏览器上下文已初始化")
            return browser, context
        except Exception as e:
            logger.error(f"初始化浏览器上下文失败: {e}")
            # 清理可能已创建的部分资源
            if context:
                context.close()
            if browser:
                browser.close()
            raise # 将异常重新抛出，让调用者处理

    def close_context(self, browser, context):
        """关闭浏览器上下文和浏览器"""
        closed = False
        if context:
            try:
                context.close()
                logger.debug("浏览器上下文已关闭")
                closed = True
            except Exception as e:
                logger.error(f"关闭浏览器上下文时出错: {e}")
        if browser:
            try:
                browser.close()
                logger.debug("浏览器实例已关闭")
                closed = True
            except Exception as e:
                logger.error(f"关闭浏览器时出错: {e}")
        # 如果 Playwright 实例存在且没有其他浏览器在运行，则停止 Playwright
        # 注意：这里简化处理，假设一次只处理一个帖子的比价
        if closed and self.playwright:
             try:
                 self.playwright.stop()
                 self.playwright = None # 重置实例
                 logger.debug("Playwright 实例已停止")
             except Exception as e:
                 logger.error(f"停止 Playwright 时出错: {e}")
    
    def get_item_price_stats(self, context, search_term, wait_time=5, initial_wait=2, max_retries=3):
        """
        在现有上下文中获取单个商品的价格统计信息
        
        Args:
            context: 浏览器上下文对象
            search_term: 搜索关键词
            wait_time: 等待搜索执行的时间(秒)
            initial_wait: 初始停留在主页的时间(秒)
            max_retries: 查找搜索框的最大重试次数
            
        Returns:
            dict: 价格统计信息，包含均价、中位数等
        """
        logger.info(f"开始在现有上下文中获取商品 '{search_term}' 的价格信息")
        page = None # 初始化 page 变量
        try:
            page = context.new_page()
            page.set_default_timeout(30000)  # 30秒超时
            
            # 设置额外的页面属性来避免被检测
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            # 访问闲鱼主页
            logger.debug("正在访问闲鱼...")
            page.goto("https://www.goofish.com/")
            page.wait_for_load_state("networkidle")
            
            if initial_wait > 0:
                time.sleep(initial_wait)
            
            # 查找搜索框
            retry_count = 0
            search_input = None
            
            while retry_count < max_retries:
                try:
                    selectors = [
                        '//*[@id="header"]/header/div[2]/form/input',
                        '//input[@placeholder="搜索"]',
                        '//input[@type="search"]',
                        '//input[contains(@class, "search")]'
                    ]
                    for selector in selectors:
                        try:
                            search_input = page.locator(selector)
                            if search_input.count() > 0:
                                logger.debug(f"找到搜索框，使用选择器: {selector}")
                                search_input = search_input.element_handle()
                                break
                        except:
                            continue
                    if search_input:
                        break
                    else:
                        retry_count += 1
                        if retry_count < max_retries:
                            logger.debug(f"未找到搜索框，等待1秒后重试 ({retry_count}/{max_retries})")
                            time.sleep(1)
                        else:
                            logger.warning(f"尝试 {max_retries} 次后未找到搜索框")
                            return {"error": "未找到搜索框"}
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(1)
                    else:
                        logger.error(f"查找搜索框失败: {e}")
                        return {"error": f"查找搜索框失败: {e}"}
            
            if search_input:
                logger.debug(f"搜索: {search_term}")
                search_input.fill("")
                search_input.type(search_term, delay=100)
                search_input.press("Enter")
                
                try:
                    page.wait_for_url("**/search*", timeout=15000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                    
                    if wait_time > 0:
                        time.sleep(wait_time)
                        
                    # 手动获取价格信息
                    logger.info("开始手动获取价格信息")
                    price_elements = page.query_selector_all(".price, .number--NKh1vXWM")
                    prices = []
                    for price_elem in price_elements:
                        price_text = price_elem.inner_text()
                        price_str = price_text.strip().replace("¥", "").replace("￥", "").replace(",", "")
                        try:
                            price = float(price_str)
                            prices.append(price)
                        except ValueError:
                            continue
                    
                    if prices:
                        avg_price = sum(prices) / len(prices)
                        sorted_prices = sorted(prices)
                        mid = len(sorted_prices) // 2
                        if len(sorted_prices) % 2 == 0:
                            median = (sorted_prices[mid-1] + sorted_prices[mid]) / 2
                        else:
                            median = sorted_prices[mid]
                        logger.info(f"找到 {len(prices)} 个价格")
                        logger.info(f"均价: {avg_price:.2f} | 中位数: {median:.2f}")
                        return {"success": True, "average": avg_price, "median": median}
                    else:
                        logger.warning("未找到任何价格")
                        return {"error": "未找到价格"}
                        
                except PlaywrightTimeoutError:
                    logger.error("搜索结果页面加载超时")
                    return {"error": "搜索结果页面加载超时"}
        except Exception as e:
            logger.error(f"在现有上下文中获取价格信息时出错: {e}")
            return {"error": f"操作错误: {e}"}
        finally:
            # 确保页面被关闭
            if page:
                try:
                    page.close()
                    logger.debug("价格获取页面已关闭")
                except Exception as e:
                    logger.error(f"关闭价格获取页面时出错: {e}") 