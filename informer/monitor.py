"""
监控器模块 - 处理论坛监控
"""

import queue
import random
import threading
import time
from loguru import logger

from informer.fetcher import Fetcher
from informer.llm_analyzer import LLMAnalyzer


class NotificationMessage:
    """通知消息类"""
    
    def __init__(self, post_data, at_phones=None):
        """
        初始化通知消息
        
        Args:
            post_data: 包含帖子所有信息的字典
            at_phones: 需要@的手机号列表
        """
        self.post_data = post_data
        self.at_phones = at_phones or []


class ChiphellMonitor:
    """Chiphell论坛监控器"""
    
    def __init__(self, cookies, user_keywords, notifier, database, 
                 wait_time_range, proxy_manager=None, llm_config=None):
        """
        初始化监控器
        
        Args:
            cookies: Cookies字符串
            user_keywords: 用户关键词字典，格式为 {手机号: [关键词列表]}
            notifier: 通知器对象
            database: 数据库对象
            wait_time_range: 等待时间范围，格式为 {min: 最小值, max: 最大值}
            proxy_manager: 代理管理器对象
            llm_config: LLM配置对象，用于内容分析
        """
        self.forum_name = "chiphell"
        self.cookies = cookies
        self.user_keywords = user_keywords
        self.notifier = notifier
        self.database = database
        self.wait_time_range = wait_time_range
        self.proxy_manager = proxy_manager
        self.message_queue = queue.Queue(maxsize=100)
        self.fetcher = Fetcher(proxy_manager, cookies)
        
        # 初始化LLM分析器
        self.llm_analyzer = LLMAnalyzer(llm_config) if llm_config else None
        if self.llm_analyzer and self.llm_analyzer.enabled:
            logger.info("LLM内容分析功能已启用")
        else:
            logger.info("LLM内容分析功能未启用")
            self.llm_analyzer = None # 确保未启用时为 None
            
        # 启动消息处理线程
        self._start_message_processor()
    
    def _start_message_processor(self):
        """启动消息处理线程"""
        def processor():
            while True:
                try:
                    # 收集消息，每3秒一批
                    messages = []
                    timeout = 3  # 等待时间
                    
                    # 获取第一条消息，最长等待3秒
                    try:
                        msg = self.message_queue.get(timeout=timeout)
                        messages.append(msg)
                        self.message_queue.task_done()
                    except queue.Empty:
                        # 队列为空，继续循环
                        continue
                    
                    # 尝试获取更多消息，不等待
                    try:
                        while True:
                            msg = self.message_queue.get_nowait()
                            messages.append(msg)
                            self.message_queue.task_done()
                    except queue.Empty:
                        # 没有更多消息了
                        pass
                    
                    # 批量处理消息
                    if messages:
                        self._batch_process_messages(messages)
                except Exception as e:
                    logger.error(f"处理消息队列时出错: {e}")
        
        # 启动处理线程
        thread = threading.Thread(target=processor, daemon=True)
        thread.start()
        logger.info("消息处理器已启动")
    
    def _batch_process_messages(self, messages):
        """
        批量处理消息
        
        Args:
            messages: 消息列表 (NotificationMessage 对象)
        """
        if not messages:
            return
        
        # 合并消息内容
        combined_message = []
        all_phones = set()
        
        for i, msg in enumerate(messages):
            post_data = msg.post_data
            details = post_data.get('details') or {}
            analysis_result = post_data.get('analysis_result')
            
            # 添加分隔线（除了第一条消息）
            if i > 0:
                combined_message.append("----------------------------------------")
            
            # 提取基本信息
            title = post_data.get('title', '无标题')
            link = post_data.get('link', '无链接')
            post_type = details.get('post_type', '未知') # 从details获取
            
            # 构建格式化消息
            combined_message.append(f"【{post_type}】{title}")
            combined_message.append(f"【链接】{link}")
            
            # 添加帖子详情
            qq = details.get('qq', '-')
            phone = details.get('phone', '-')
            price_field = details.get('price', '-') # 帖子字段的价格
            address = details.get('address', '-')
            trade_range = details.get('trade_range', '-')
            
            if qq != '-': combined_message.append(f"【QQ】{qq}")
            if phone != '-': combined_message.append(f"【电话】{phone}")
            if price_field != '-': combined_message.append(f"【价格】{price_field}")
            if address != '-': combined_message.append(f"【所在地】{address}")
            if trade_range != '-': combined_message.append(f"【交易范围】{trade_range}")
            
            # 添加商品分析信息 (移除闲鱼比价)
            if analysis_result and 'items' in analysis_result and analysis_result['items']:
                # 只有LLM分析结果
                combined_message.append("\n【商品分析】")
                for item in analysis_result['items']:
                    item_name = item.get('item_name', 'N/A')
                    current_price = item.get('price', '未指定')
                    combined_message.append(f"\n▎{item_name}")
                    combined_message.append(f"▎当前价格: {current_price}")
            
            # 收集需要@的手机号
            for phone in msg.at_phones:
                all_phones.add(phone)
        
        # 发送合并后的消息，使用单个换行符连接
        content = "\n".join(combined_message)
        content_preview = content[:100] + "..." if len(content) > 100 else content
        logger.debug(f"发送合并消息，内容预览: {content_preview}")
        
        # 发送通知
        success = self.notifier.send_text_notification(
            "",  # 移除"新帖子通知"标题
            content,
            list(all_phones)
        )
        
        if success:
            logger.debug(f"成功发送{len(messages)}条合并消息")
        else:
            logger.error("发送钉钉通知失败")
    
    def _enqueue_notification(self, post_data, at_phones=None):
        """
        将通知消息放入队列
        
        Args:
            post_data: 包含帖子所有信息的字典
            at_phones: 需要@的手机号列表
        """
        try:
            notification = NotificationMessage(post_data, at_phones)
            self.message_queue.put(notification, block=False)
        except queue.Full:
            logger.warning("消息队列已满，消息被丢弃")
    
    def _process_notification(self, post, details, analysis_result=None):
        """
        处理通知，将结构化数据放入队列
        
        Args:
            post: 帖子基本信息字典
            details: 帖子详细信息字典
            analysis_result: LLM分析结果字典
        """
        # 收集所有关注该帖子的手机号
        phones = []
        title = post['title'] # 获取标题用于匹配
        
        # 遍历用户关键词进行匹配
        for phone, keywords in self.user_keywords.items():
            for keyword in keywords:
                lower_keyword = keyword.lower()
                lower_title = title.lower()
                if lower_keyword in lower_title:
                    logger.debug(f"标题 '{title}' 匹配到关键词 '{keyword}'，将@手机号 {phone}")
                    phones.append(phone)
                    break
        
        # 记录匹配结果
        if phones:
            logger.debug(f"帖子 '{title}' 匹配到 {len(phones)} 个手机号需要@")
        else:
            logger.debug(f"帖子 '{title}' 没有匹配到任何关键词")
            
        # 准备要放入队列的数据字典
        post_data = {
            "title": title,
            "link": post.get('link', ''),
            "details": details, # 包含 qq, phone, price, address, trade_range, post_type, post_content
            "analysis_result": analysis_result, # LLM结果
        }
        
        # 发送通知 (将字典放入队列)
        self._enqueue_notification(post_data, phones)
    
    def _fetch_page_content(self):
        """
        获取论坛页面内容
        
        Returns:
            str: 页面内容
            
        Raises:
            Exception: 获取失败
        """
        try:
            url = "https://www.chiphell.com/forum-26-1.html"
            content = self.fetcher.fetch_with_proxies(url)
            return content
        except Exception as e:
            raise Exception(f"获取页面内容失败: {e}")
    
    def _fetch_post_content(self, post_url):
        """
        获取帖子内容
        
        Args:
            post_url: 帖子链接
            
        Returns:
            dict: 帖子详情
            
        Raises:
            Exception: 获取失败
        """
        try:
            content = self.fetcher.fetch_with_proxies(post_url)
            details = self.fetcher.parse_post_content(content)
            
            # 提取帖子正文内容
            post_content = self.fetcher.extract_post_content(content)
            details['post_content'] = post_content
            
            return details
        except Exception as e:
            raise Exception(f"获取帖子内容失败: {e}")
    
    def process_posts(self, posts):
        """
        处理帖子列表
        
        Args:
            posts: 帖子列表
        """
        for post in posts:
            # 从帖子链接中提取ID
            post_id = self.fetcher.extract_post_id(post['link'])
            if not post_id:
                logger.warning(f"无法从链接中提取帖子ID: {post['link']}")
                continue
            
            # 检查是否为新帖子
            if self.database.is_new_post(self.forum_name, post_id):
                # 存储帖子ID
                self.database.store_post(self.forum_name, post_id, post['title'], post['link'])
                logger.info(f"检测到新帖子: 标题: {post['title']} 链接: {post['link']}")
                
                # 构建基本消息
                basic_message = f"标题: {post['title']}\n链接: {post['link']}\n帖子类型: 未知"
                
                # 尝试获取帖子详情
                try:
                    # 获取帖子详情和正文内容
                    details = self._fetch_post_content(post['link'])
                    post_content = details.get('post_content', '-')
                    
                    # 记录主楼内容到日志
                    if post_content != '-':
                        logger.info(f"帖子正文内容:\n{post_content}")
                    
                    # 构建详细消息
                    detail_message = (
                        f"标题: {post['title']}\n"
                        f"链接: {post['link']}\n"
                        f"QQ: {details['qq']}\n"
                        f"电话: {details['phone']}\n"
                        f"价格: {details['price']}\n"
                        f"所在地: {details['address']}\n"
                        f"交易范围: {details['trade_range']}\n"
                        f"帖子类型: {details['post_type']}"
                    )
                    
                    # 使用LLM分析器提取商品信息（如果启用）
                    analysis_result = None
                    if self.llm_analyzer and self.llm_analyzer.enabled and post_content != '-':
                        try:
                            logger.debug(f"开始对帖子 '{post['title']}' 进行LLM分析...")
                            analysis_result = self.llm_analyzer.analyze_post(
                                post['title'], 
                                details.get('price', '-'), # 从详情获取价格字段
                                post_content
                            )
                            logger.info(f"LLM分析完成，帖子: '{post['title']}'")
                            logger.trace(f"LLM分析结果: {analysis_result}")
                        except Exception as e:
                            logger.error(f"处理帖子 '{post['title']}' 的LLM分析时出错: {e}")
                    
                    # 将所有信息（基础、详情、LLM）传递给通知处理函数
                    self._process_notification(post, details, analysis_result)
                except Exception as e:
                    logger.error(f"获取帖子详情或进行分析时失败: {e}")
                    # 即使获取详情失败，也发送基本信息（details 为 None）
                    self._process_notification(post, None, None)
    
    def monitor(self):
        """开始监控"""
        failed_attempts = 0
        max_failed_attempts = 5
        
        while True:
            try:
                # 获取页面内容
                content = self._fetch_page_content()
                
                # 解析帖子列表
                posts = self.fetcher.parse_forum_content(content)
                logger.info(f"成功获取论坛内容，解析到 {len(posts)} 个帖子")
                
                # 处理帖子
                self.process_posts(posts)
                
                # 重置失败计数
                failed_attempts = 0
                
                # 等待一段时间后再进行下一次监控
                min_wait = self.wait_time_range.min
                max_wait = self.wait_time_range.max
                
                # 确保最小等待时间不少于10秒
                min_wait = max(min_wait, 10)
                max_wait = max(max_wait, min_wait + 5)
                
                wait_time = random.randint(min_wait, max_wait)
                logger.debug(f"等待 {wait_time} 秒后继续监控")
                time.sleep(wait_time)
            
            except Exception as e:
                failed_attempts += 1
                logger.error(f"监控过程中出错: {e}")
                
                # 如果是代理池为空的错误，增加等待时间
                if "代理池为空" in str(e):
                    logger.warning("代理池为空，等待3分钟后重试")
                    time.sleep(180)
                    continue
                
                # 如果连续失败次数过多，增加等待时间
                if failed_attempts >= max_failed_attempts:
                    wait_time = failed_attempts * 30
                    # 限制最大等待时间为10分钟
                    wait_time = min(wait_time, 600)
                    logger.warning(f"连续失败{failed_attempts}次，等待{wait_time}秒后重试")
                    time.sleep(wait_time)
                    
                    # 尝试报告错误
                    try:
                        self.notifier.report_error("监控失败", str(e))
                    except Exception as notify_err:
                        logger.error(f"发送错误通知失败: {notify_err}")
                    
                    # 重置失败计数
                    if failed_attempts >= max_failed_attempts * 2:
                        failed_attempts = 0
                        logger.info("重置失败计数")
                else:
                    # 简单等待时间随失败次数增加
                    wait_time = 5 * (2 ** (failed_attempts - 1))
                    logger.info(f"等待 {wait_time} 秒后重试")
                    time.sleep(wait_time) 