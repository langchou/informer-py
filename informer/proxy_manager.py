"""
代理管理模块 - 处理代理池
"""

import random
import time
import threading
import requests
from loguru import logger


class ProxyManager:
    """代理池管理器"""
    
    def __init__(self, proxy_api=None):
        """
        初始化代理池管理器
        
        Args:
            proxy_api: 代理API地址
        """
        self.proxy_api = proxy_api
        self.proxies = []  # 普通代理池
        self.preferred_proxies = {}  # 优选代理池，值为响应时间
        self.lock = threading.RLock()
        
        # 初始化时更新一次代理池
        if self.proxy_api:
            self.update_proxy_pool()
            
            # 启动定时更新任务
            self._start_pool_updater()
    
    def _start_pool_updater(self, interval=180):
        """
        启动定时更新代理池的线程
        
        Args:
            interval: 更新间隔（秒）
        """
        def updater():
            while True:
                time.sleep(interval)
                try:
                    self.update_proxy_pool()
                except Exception as e:
                    logger.error(f"定时更新代理池失败: {e}")
        
        thread = threading.Thread(target=updater, daemon=True)
        thread.start()
        logger.info(f"代理池定时更新器已启动，更新间隔: {interval}秒")
    
    def update_proxy_pool(self):
        """
        更新代理池
        
        Returns:
            bool: 是否更新成功
        """
        if not self.proxy_api:
            logger.warning("未设置代理API")
            return False
        
        try:
            # 使用session并禁用SSL验证
            session = requests.Session()
            session.verify = False
            
            response = session.get(self.proxy_api, timeout=10)
            if response.status_code != 200:
                logger.error(f"请求代理API失败，状态码: {response.status_code}")
                return False
            
            # 尝试解析JSON响应
            try:
                # 新API格式返回JSON数据
                data = response.json()
                
                # 检查返回格式是否正确
                if data.get("code") == 200 and "data" in data and "proxies" in data["data"]:
                    proxy_list = data["data"]["proxies"]
                    logger.debug(f"成功从API获取 {len(proxy_list)} 个代理")
                else:
                    # 尝试旧格式：如果不是JSON格式或JSON格式不符合预期，则尝试按文本格式处理
                    logger.warning("API返回格式不符合预期JSON结构，尝试按文本格式处理")
                    proxy_list = response.text.strip().split('\n')
            except (ValueError, AttributeError):
                # JSON解析失败，尝试旧格式
                logger.warning("无法解析API返回的JSON数据，尝试按文本格式处理")
                proxy_list = response.text.strip().split('\n')
            
            cleaned_proxies = []
            
            for proxy in proxy_list:
                if isinstance(proxy, str) and proxy.strip():
                    proxy = proxy.strip()
                    # 确保代理格式正确
                    if not proxy.startswith(('http://', 'https://', 'socks5://')):
                        proxy = f"socks5://{proxy}"
                    cleaned_proxies.append(proxy)
            
            with self.lock:
                self.proxies = cleaned_proxies
                logger.info(f"代理池更新完成，当前代理数量: {len(self.proxies)}")
            
            return True
        except Exception as e:
            logger.error(f"更新代理池失败: {e}")
            return False
    
    def check_proxy(self, proxy, timeout=3):
        """
        检查代理是否可用
        
        Args:
            proxy: 代理地址
            timeout: 超时时间
            
        Returns:
            tuple: (是否可用, 响应时间)
        """
        try:
            start_time = time.time()
            
            proxies = {
                "http": proxy,
                "https": proxy
            }
            
            session = requests.Session()
            session.verify = False  # 禁用SSL证书验证
            
            # 尝试访问百度
            response = session.get(
                "https://www.baidu.com", 
                proxies=proxies, 
                timeout=timeout
            )
            
            response_time = (time.time() - start_time) * 1000  # 毫秒
            
            if response.status_code == 200:
                logger.debug(f"代理 {proxy} 可用，响应时间: {response_time:.2f}ms")
                return True, response_time
            else:
                logger.debug(f"代理 {proxy} 不可用，状态码: {response.status_code}")
                return False, 0
        except Exception as e:
            logger.debug(f"代理 {proxy} 检查失败: {e}")
            return False, 0
    
    def start_proxy_checker(self, interval=120, max_check=20):
        """
        启动代理检查器
        
        Args:
            interval: 检查间隔（秒）
            max_check: 每次最多检查的代理数量
        """
        def checker():
            while True:
                try:
                    with self.lock:
                        preferred_count = len(self.preferred_proxies)
                    
                    if preferred_count > 10:
                        logger.info(f"当前优选代理数量充足: {preferred_count}，跳过检测")
                    else:
                        logger.info("开始检测代理池中的IP")
                        
                        with self.lock:
                            # 随机选择一些代理进行检测，而不是按顺序检测
                            proxies_to_check = self.proxies.copy()
                            if len(proxies_to_check) > max_check * 2:
                                proxies_to_check = random.sample(proxies_to_check, max_check * 2)
                        
                        checked_count = 0
                        for proxy in proxies_to_check:
                            valid, response_time = self.check_proxy(proxy)
                            if valid:
                                with self.lock:
                                    self.preferred_proxies[proxy] = response_time
                                logger.debug(f"添加新的优选代理: {proxy}, 响应时间: {response_time:.2f}ms")
                                checked_count += 1
                            
                            if checked_count >= max_check:
                                logger.info("已找到足够的优选代理，停止检测")
                                break
                            
                            # 避免检测过快
                            time.sleep(0.5)
                        
                        with self.lock:
                            logger.info(f"IP检测完成，当前优选代理数量: {len(self.preferred_proxies)}")
                
                except Exception as e:
                    logger.error(f"代理检测过程中出错: {e}")
                
                # 休眠指定间隔
                time.sleep(interval)
        
        # 启动检查线程
        thread = threading.Thread(target=checker, daemon=True)
        thread.start()
        logger.info("代理检查器已启动")
    
    def get_proxy(self):
        """
        获取一个代理
        
        Returns:
            str: 代理地址，如果没有可用代理则返回None
        """
        with self.lock:
            # 首先尝试从优选代理池中获取
            if self.preferred_proxies:
                # 选择响应时间最短的代理
                best_proxy = min(self.preferred_proxies.items(), key=lambda x: x[1])[0]
                return best_proxy
            
            # 如果没有优选代理，从普通代理池中随机获取一个
            if self.proxies:
                return random.choice(self.proxies)
        
        return None
    
    def remove_proxy(self, proxy):
        """
        从代理池中移除代理
        
        Args:
            proxy: 代理地址
        """
        with self.lock:
            if proxy in self.preferred_proxies:
                del self.preferred_proxies[proxy]
                logger.debug(f"从优选代理池中移除: {proxy}")
            
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                logger.debug(f"从普通代理池中移除: {proxy}")
    
    def get_proxy_count(self):
        """
        获取代理池中的代理数量
        
        Returns:
            tuple: (普通代理数量, 优选代理数量)
        """
        with self.lock:
            return len(self.proxies), len(self.preferred_proxies) 