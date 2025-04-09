"""
获取器模块 - 处理网页内容获取
"""

import urllib.parse
import requests
from bs4 import BeautifulSoup
from loguru import logger


class Fetcher:
    """网页获取器"""
    
    def __init__(self, proxy_manager=None, cookies=None):
        """
        初始化获取器
        
        Args:
            proxy_manager: 代理管理器
            cookies: Cookies字符串
        """
        self.proxy_manager = proxy_manager
        self.cookies = cookies
    
    def fetch_with_proxies(self, url, max_retries=3):
        """
        使用代理获取网页内容
        
        Args:
            url: 目标URL
            max_retries: 最大重试次数
            
        Returns:
            str: 网页内容
        
        Raises:
            Exception: 获取失败
        """
        if self.proxy_manager:
            # 检查代理池数量
            normal_count, preferred_count = self.proxy_manager.get_proxy_count()
            if normal_count == 0 and preferred_count == 0:
                logger.warning("代理池为空，等待30秒后重试")
                raise Exception("代理池为空，请稍后重试")
            
            # 首先尝试使用优选代理
            if preferred_count > 0:
                proxy = self.proxy_manager.get_proxy()
                if proxy:
                    content = self._fetch_with_proxy(url, proxy)
                    if content:
                        logger.debug(f"使用优选代理 {proxy} 请求成功")
                        return content
                    else:
                        logger.warning(f"使用优选代理 {proxy} 请求失败")
                        self.proxy_manager.remove_proxy(proxy)
            
            # 如果优选代理都失败了，使用普通代理
            for i in range(max_retries):
                proxy = self.proxy_manager.get_proxy()
                if not proxy:
                    logger.warning("无法获取代理")
                    break
                
                content = self._fetch_with_proxy(url, proxy)
                if content:
                    return content
                else:
                    logger.warning(f"使用代理 {proxy} 请求失败")
                    self.proxy_manager.remove_proxy(proxy)
            
            raise Exception("所有重试都失败")
        else:
            # 不使用代理
            return self._fetch_without_proxy(url)
    
    def _fetch_with_proxy(self, url, proxy):
        """
        使用指定代理获取网页内容
        
        Args:
            url: 目标URL
            proxy: 代理地址
            
        Returns:
            str: 网页内容，如果失败则返回None
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Cookie": self.cookies or "",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            proxies = {
                "http": proxy,
                "https": proxy
            }
            
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False  # 禁用SSL证书验证
            
            # 设置重试次数和超时时间
            adapter = requests.adapters.HTTPAdapter(max_retries=2)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            response = session.get(url, proxies=proxies, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"请求失败，状态码: {response.status_code}")
                # 记录响应内容以便调试
                if response.status_code == 567:
                    logger.warning(f"567错误响应内容: {response.text[:200]}...")
                return None
            
            return response.text
        except Exception as e:
            logger.warning(f"请求过程中出错: {e}")
            return None
    
    def _fetch_without_proxy(self, url):
        """
        不使用代理获取网页内容
        
        Args:
            url: 目标URL
            
        Returns:
            str: 网页内容
        
        Raises:
            Exception: 获取失败
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Cookie": self.cookies or "",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False  # 禁用SSL证书验证
            
            # 设置重试次数和超时时间
            adapter = requests.adapters.HTTPAdapter(max_retries=2)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            response = session.get(url, timeout=15)
            
            if response.status_code != 200:
                raise Exception(f"无效的响应状态码: {response.status_code}")
            
            return response.text
        except Exception as e:
            raise Exception(f"请求失败: {e}")
    
    @staticmethod
    def parse_forum_content(html):
        """
        解析论坛页面内容
        
        Args:
            html: HTML内容
            
        Returns:
            list: 帖子列表，每个帖子包含标题和链接
        """
        soup = BeautifulSoup(html, 'html.parser')
        posts = []
        
        for thread in soup.select('tbody[id^="normalthread_"]'):
            post_link = thread.select_one('a.s.xst')
            if post_link:
                title = post_link.text
                href = post_link.get('href')
                if href:
                    # 确保链接是完整的URL
                    if not href.startswith('http'):
                        href = f"https://www.chiphell.com/{href}"
                    
                    posts.append({
                        'title': title,
                        'link': href
                    })
        
        return posts
    
    @staticmethod
    def parse_post_content(html):
        """
        解析帖子详情内容
        
        Args:
            html: HTML内容
            
        Returns:
            dict: 帖子详情
        """
        soup = BeautifulSoup(html, 'html.parser')
        details = {
            'qq': '-',
            'price': '-',
            'trade_range': '-',
            'address': '-',
            'phone': '-',
            'post_type': '未知'
        }
        
        # 获取帖子查看次数
        view_count_elem = soup.select_one('div.hm.ptn span.xi1')
        if view_count_elem:
            try:
                view_count = int(view_count_elem.text.strip())
                details['post_type'] = '新贴' if view_count < 50 else '老帖'
            except (ValueError, TypeError):
                pass
        
        # 获取帖子详情
        for row in soup.select('.typeoption tbody tr'):
            th = row.select_one('th')
            td = row.select_one('td')
            
            if th and td:
                key = th.text.strip()
                value = td.text.strip()
                
                if '所在地:' in key:
                    details['address'] = value
                elif '电话:' in key:
                    details['phone'] = value
                elif 'QQ:' in key:
                    details['qq'] = value
                elif '价格:' in key:
                    details['price'] = value
                elif '交易范围:' in key:
                    details['trade_range'] = value
        
        return details
    
    @staticmethod
    def extract_post_id(url):
        """
        从帖子URL中提取ID
        
        Args:
            url: 帖子链接
            
        Returns:
            str: 帖子ID
        """
        # 假设链接格式为 https://www.chiphell.com/thread-2646639-1-1.html
        if '-' in url:
            parts = url.split('-')
            if len(parts) > 1:
                return parts[1]
        return ""

    @staticmethod
    def extract_post_content(html):
        """
        提取帖子主楼的纯文本内容，并过滤掉无用字符
        
        Args:
            html: 帖子页面的HTML内容
            
        Returns:
            str: 处理后的纯文本内容
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 查找主楼内容元素 - 修改选择器
        content_elem = soup.select_one('td.t_f')
        if not content_elem:
            # 尝试备用选择器，兼容可能的变动
            content_elem = soup.select_one('div.pcb td.t_f') 
            if not content_elem:
                 logger.warning("无法找到帖子主楼内容元素 (尝试了 td.t_f 和 div.pcb td.t_f)")
                 return "无法提取帖子内容"

        # 移除所有隐藏的span元素
        for span in content_elem.select('span[style*="display:none"]'):
            span.decompose()
        
        # 移除所有无用的jammer字体
        for jammer in content_elem.select('font.jammer'):
            jammer.decompose()
        
        # 获取文本，保留换行
        content_lines = []
        for element in content_elem.descendants:
            if isinstance(element, str) and element.strip():
                content_lines.append(element.strip())
            elif element.name == 'br':
                content_lines.append('\\n')
        
        # 合并文本行，处理多余的换行和空格
        content = ' '.join(content_lines).strip()
        while '\\n \\n' in content or '  ' in content:
            content = content.replace('\\n \\n', '\\n')
            content = content.replace('  ', ' ')
        
        return content.strip() 